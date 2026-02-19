import json
import os
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from cryptography.fernet import Fernet
from streamlit.errors import StreamlitSecretNotFoundError

from app.analytics import build_timeline, summarize_glucose
from app.db import (
    create_user,
    delete_record,
    get_setting,
    get_user,
    has_duplicate,
    init_db,
    load_records,
    save_record,
    set_setting,
)
from app.exporters import (
    build_encrypted_share_payload,
    build_pdf_report,
    dataframe_to_csv_bytes,
    dataframe_to_excel_bytes,
)
from app.security import build_fernet, generate_salt, hash_pin, verify_pin
from app.validation import validate_glucose_value, validate_pin

st.set_page_config(page_title="¿Cómo va mi glucosa?", layout="wide")
init_db()


def get_app_pepper() -> str:
    env_pepper = os.getenv("APP_PEPPER")
    if env_pepper:
        return env_pepper

    try:
        return st.secrets.get("APP_PEPPER", "change-me-before-production")
    except StreamlitSecretNotFoundError:
        return "change-me-before-production"


def to_dataframe(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    return df.sort_values("recorded_at", ascending=False)


def setting_json(key: str, default, owner: str):
    raw = get_setting(key, owner=owner)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def glucose_recommendation(
    value_mg_dl: float,
    target_low: int,
    target_high: int,
    hypo_threshold: int,
    hyper_threshold: int,
) -> tuple[str, str]:
    if value_mg_dl < 54:
        return (
            "error",
            "Glucosa muy baja. Toma carbohidrato de acción rápida y busca atención médica si no mejora pronto.",
        )
    if value_mg_dl < hypo_threshold:
        return (
            "warning",
            "Glucosa baja. Toma carbohidrato de acción rápida, vuelve a medir en 15 minutos y contacta a tu médico si persiste.",
        )
    if target_low <= value_mg_dl <= target_high:
        return ("success", "Valor en rango objetivo. Continúa con tu plan indicado por tu médico.")
    if value_mg_dl <= hyper_threshold:
        return (
            "info",
            "Valor elevado. Hidrátate, revisa tus indicaciones de tratamiento y vuelve a medir según recomendación médica.",
        )
    return (
        "error",
        "Glucosa muy elevada. Contacta a tu médico para orientación y considera atención urgente si tienes síntomas.",
    )


def ensure_authentication() -> None:
    st.title("Control de glucosa para compartir con tu doctor")
    st.caption("Cada paciente usa su propio código y PIN para que sus datos queden separados.")

    with st.expander("Guía rápida para pacientes y doctores", expanded=True):
        st.markdown(
            """
            **Pacientes**
            - Crea tu cuenta con un código de paciente (puede ser numérico o alfanumérico).
            - El PIN debe ser de 4 números.
            - Registra tus mediciones y comparte tu paquete cifrado cuando tu doctor lo solicite.

            **Doctores**
            - Para valorar las cifras de un paciente se necesita:
              - Código del paciente.
              - Archivo cifrado `.cmg` compartido por el paciente.
              - Clave de cifrado temporal (enviada por canal separado).
            - Ejemplo de clave: `bt65lYn_O4-K3bK-GgKE3nYRiey9j8hf9v7O-5ShTj8=`

            Esta app busca que el paciente tenga un registro digital continuo y evitar pérdidas de datos por hojas en papel.
            """
        )

    if (
        st.session_state.get("authenticated")
        and st.session_state.get("fernet") is not None
        and st.session_state.get("patient_code")
    ):
        return

    tab_login, tab_create = st.tabs(["Ingresar", "Crear cuenta paciente"])

    with tab_login:
        with st.form("login_form"):
            patient_code = st.text_input("Código de paciente", help="Ejemplo: juanperez01").strip().lower()
            pin = st.text_input("PIN", type="password")
            submitted = st.form_submit_button("Entrar")

        if submitted:
            user = get_user(patient_code)
            if not user:
                st.error("No existe ese código de paciente. Puedes crear una cuenta nueva en la otra pestaña.")
                st.stop()

            if verify_pin(pin, user["pin_salt"], user["pin_hash"]):
                pepper = get_app_pepper()
                st.session_state["fernet"] = build_fernet(pin, user["pin_salt"], pepper)
                st.session_state["authenticated"] = True
                st.session_state["patient_code"] = user["patient_code"]
                st.session_state["patient_name"] = user["patient_name"]
                st.success("Acceso correcto.")
                st.rerun()
            st.error("PIN incorrecto.")

    with tab_create:
        with st.form("create_patient_form"):
            patient_code = st.text_input(
                "Código único de paciente",
                help="Puede ser numérico o alfanumérico. Se permiten guion (-) y guion bajo (_), sin espacios.",
            ).strip().lower()
            patient_name = st.text_input("Nombre del paciente")
            pin = st.text_input("Crear PIN (4 dígitos)", type="password")
            pin_confirm = st.text_input("Confirmar PIN", type="password")
            accepted = st.checkbox("Acepto el uso y almacenamiento de mis datos de salud.")
            created = st.form_submit_button("Crear cuenta")

        if created:
            code_valid = patient_code and all(ch.isalnum() or ch in "_-" for ch in patient_code)
            if not code_valid:
                st.error("El código de paciente debe contener solo letras, números, guion (-) o guion bajo (_).")
                st.stop()
            if get_user(patient_code):
                st.error("Ese código ya existe. Usa otro código o entra con tu PIN.")
                st.stop()

            valid_pin, pin_message = validate_pin(pin)
            if not valid_pin:
                st.error(pin_message)
                st.stop()
            if pin != pin_confirm:
                st.error("El PIN y su confirmación no coinciden.")
                st.stop()
            if not accepted:
                st.error("Debes aceptar el consentimiento para continuar.")
                st.stop()

            salt = generate_salt()
            create_user(patient_code, patient_name.strip() or patient_code, salt, hash_pin(pin, salt), consent="true")
            set_setting("doctor_targets", json.dumps({"target_low": 70, "target_high": 180, "hypo": 70, "hyper": 250}), owner=patient_code)
            set_setting("reminders", json.dumps({"glucose_time": "08:00", "hba1c_day": 90}), owner=patient_code)
            set_setting("medications", json.dumps([]), owner=patient_code)
            set_setting("age", "30", owner=patient_code)

            pepper = get_app_pepper()
            st.session_state["fernet"] = build_fernet(pin, salt, pepper)
            st.session_state["authenticated"] = True
            st.session_state["patient_code"] = patient_code
            st.session_state["patient_name"] = patient_name.strip() or patient_code
            st.success("Cuenta creada. Ya puedes registrar información clínica.")
            st.rerun()
    st.stop()


ensure_authentication()
fernet = st.session_state["fernet"]
patient_code = st.session_state["patient_code"]

if st.sidebar.button("Cambiar de paciente / Crear otro"):
    st.session_state.pop("authenticated", None)
    st.session_state.pop("fernet", None)
    st.session_state.pop("patient_code", None)
    st.session_state.pop("patient_name", None)
    st.rerun()

if st.sidebar.button("Cerrar sesión"):
    st.session_state.pop("authenticated", None)
    st.session_state.pop("fernet", None)
    st.session_state.pop("patient_code", None)
    st.session_state.pop("patient_name", None)
    st.rerun()

patient_name = st.session_state.get("patient_name") or get_user(patient_code)["patient_name"]
doctor_targets = setting_json("doctor_targets", {"target_low": 70, "target_high": 180, "hypo": 70, "hyper": 250}, owner=patient_code)
reminders = setting_json("reminders", {"glucose_time": "08:00", "hba1c_day": 90}, owner=patient_code)
medications = setting_json("medications", [], owner=patient_code)

st.sidebar.header("Perfil del paciente")
st.sidebar.caption(f"Código: {patient_code}")
patient_name = st.sidebar.text_input("Nombre", value=patient_name)
age = int(get_setting("age", "30", owner=patient_code))
age = st.sidebar.number_input("Edad", min_value=0, max_value=120, value=age)
medications = st.sidebar.multiselect(
    "Medicamentos habituales",
    ["Insulina", "Metformina", "Glibenclamida", "Vildagliptina", "Otros"],
    default=medications,
)
st.session_state["patient_name"] = patient_name
set_setting("age", str(age), owner=patient_code)
set_setting("medications", json.dumps(medications), owner=patient_code)

st.sidebar.header("Rangos definidos por el doctor")
target_low = st.sidebar.number_input("Objetivo mínimo (mg/dL)", min_value=40, max_value=160, value=int(doctor_targets.get("target_low", 70)))
target_high = st.sidebar.number_input("Objetivo máximo (mg/dL)", min_value=100, max_value=300, value=int(doctor_targets.get("target_high", 180)))
hypo_threshold = st.sidebar.number_input("Umbral hipoglucemia", min_value=40, max_value=100, value=int(doctor_targets.get("hypo", 70)))
hyper_threshold = st.sidebar.number_input("Umbral hiperglucemia", min_value=150, max_value=500, value=int(doctor_targets.get("hyper", 250)))
set_setting(
    "doctor_targets",
    json.dumps(
        {
            "target_low": target_low,
            "target_high": target_high,
            "hypo": hypo_threshold,
            "hyper": hyper_threshold,
        }
    ),
    owner=patient_code,
)

tabs = st.tabs([
    "Registro",
    "Resumen",
    "Historial",
    "Exportar y compartir",
    "Recordatorios",
])

with tabs[0]:
    st.subheader("Registro clínico")
    st.markdown("Registra glucosa, HbA1c y eventos relevantes para consulta médica.")
    st.caption("La fecha y hora se registran automáticamente al guardar.")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.form("glucose_form"):
            st.markdown("**Nuevo registro de glucosa**")
            value_mg_dl = st.number_input("Valor de glucosa (mg/dL)", min_value=20, max_value=600, value=110)
            context = st.selectbox("Tipo de medición", ["Antes de la comida", "Después de la comida", "Glucosa al azar"])
            symptoms = st.text_input("Síntomas")
            meds_taken = st.multiselect("Medicamentos tomados", ["Insulina", "Metformina", "Glibenclamida", "Vildagliptina", "Otros"], default=[])
            insulin_units = None
            if "Insulina" in meds_taken:
                insulin_units = st.number_input("Unidades de insulina (UI)", min_value=0.0, max_value=150.0, value=0.0, step=0.5)
            dose = st.text_input("Dosis/ajuste")
            notes = st.text_area("Notas clínicas")
            submitted = st.form_submit_button("Guardar glucosa")

        if submitted:
            valid, message = validate_glucose_value(float(value_mg_dl))
            recorded_at = datetime.now().isoformat(timespec="seconds")
            if not valid:
                st.error(message)
            else:
                payload = {
                    "value_mg_dl": float(value_mg_dl),
                    "context": context,
                    "symptoms": symptoms,
                    "meds_taken": meds_taken,
                    "insulin_units": float(insulin_units) if insulin_units is not None else None,
                    "dose": dose,
                    "notes": notes,
                }
                save_record(patient_code, "glucose", recorded_at, payload, fernet)
                st.success("Registro de glucosa guardado.")
                recommendation_level, recommendation_text = glucose_recommendation(
                    float(value_mg_dl),
                    target_low,
                    target_high,
                    hypo_threshold,
                    hyper_threshold,
                )
                getattr(st, recommendation_level)(recommendation_text)

    with col_b:
        with st.form("hba1c_form"):
            st.markdown("**Nuevo registro de HbA1c**")
            hba_value = st.number_input("Valor HbA1c (%)", min_value=3.0, max_value=20.0, value=6.0, step=0.1)
            hba_notes = st.text_area("Notas HbA1c")
            hba_submit = st.form_submit_button("Guardar HbA1c")

        if hba_submit:
            recorded_at = datetime.now().isoformat(timespec="seconds")
            save_record(patient_code, "hba1c", recorded_at, {"value_pct": float(hba_value), "notes": hba_notes}, fernet)
            st.success("Registro HbA1c guardado.")

        with st.form("event_form"):
            st.markdown("**Evento relevante**")
            event_title = st.text_input("Tipo de evento", value="Actividad / síntoma / ajuste")
            event_notes = st.text_area("Detalle del evento")
            event_submit = st.form_submit_button("Guardar evento")

        if event_submit:
            recorded_at = datetime.now().isoformat(timespec="seconds")
            save_record(patient_code, "event", recorded_at, {"title": event_title, "notes": event_notes}, fernet)
            st.success("Evento guardado.")

with tabs[1]:
    st.subheader("Resumen automático para consulta")
    glucose_df = to_dataframe(load_records(patient_code, fernet, "glucose"))
    hba1c_df = to_dataframe(load_records(patient_code, fernet, "hba1c"))
    events_df = to_dataframe(load_records(patient_code, fernet, "event"))

    if glucose_df.empty:
        st.info("Aún no hay datos de glucosa.")
    else:
        summary = summarize_glucose(glucose_df, target_low, target_high, hypo_threshold, hyper_threshold)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Promedio 7 días", f"{summary.avg_7d:.1f} mg/dL" if summary.avg_7d else "N/A")
        m2.metric("Promedio 14 días", f"{summary.avg_14d:.1f} mg/dL" if summary.avg_14d else "N/A")
        m3.metric("Promedio 30 días", f"{summary.avg_30d:.1f} mg/dL" if summary.avg_30d else "N/A")
        m4.metric("% en rango", f"{summary.in_range_pct:.1f}%")

        r1, r2, r3 = st.columns(3)
        r1.metric("Mínimo", f"{summary.minimum:.1f} mg/dL")
        r2.metric("Máximo", f"{summary.maximum:.1f} mg/dL")
        r3.metric("Episodios", f"Hipo: {summary.hypo_count} | Hiper: {summary.hyper_count}")

        chart_df = glucose_df.sort_values("recorded_at").copy()
        base = alt.Chart(chart_df).encode(x=alt.X("recorded_at:T", title="Fecha/hora"))
        line = base.mark_line(point=True).encode(y=alt.Y("value_mg_dl:Q", title="Glucosa (mg/dL)"))

        rules_df = pd.DataFrame(
            {
                "threshold": [target_low, target_high, hypo_threshold, hyper_threshold],
                "label": ["Objetivo mínimo", "Objetivo máximo", "Hipo", "Hiper"],
            }
        )
        rules = alt.Chart(rules_df).mark_rule(strokeDash=[6, 4]).encode(y="threshold:Q", color="label:N")
        st.altair_chart((line + rules).properties(height=350), use_container_width=True)

        if summary.hypo_count > 0 or summary.hyper_count > 0:
            st.warning("Se detectaron episodios fuera de umbral. Contacta a tu médico para revisión del tratamiento.")

    if not hba1c_df.empty:
        st.markdown("**Tendencia HbA1c**")
        st.line_chart(hba1c_df.sort_values("recorded_at").set_index("recorded_at")["value_pct"])

with tabs[2]:
    st.subheader("Historial editable")
    all_records = load_records(patient_code, fernet)
    all_df = to_dataframe(all_records)
    glucose_df = to_dataframe(load_records(patient_code, fernet, "glucose"))
    hba1c_df = to_dataframe(load_records(patient_code, fernet, "hba1c"))
    events_df = to_dataframe(load_records(patient_code, fernet, "event"))

    timeline = build_timeline(glucose_df, hba1c_df, events_df)
    st.markdown("**Vista cronológica unificada**")
    st.dataframe(timeline, use_container_width=True)

    if all_df.empty:
        st.info("Sin registros para editar o eliminar.")
    else:
        st.markdown("**Editar registro de glucosa**")
        if not glucose_df.empty:
            glucose_options = {
                f"{row['id']} | {row['recorded_at']} | {row['value_mg_dl']} mg/dL": int(row["id"])
                for _, row in glucose_df.iterrows()
            }
            selected_label = st.selectbox("Selecciona registro", list(glucose_options.keys()))
            selected_id = glucose_options[selected_label]
            selected_row = glucose_df.loc[glucose_df["id"] == selected_id].iloc[0]

            with st.form("edit_glucose_form"):
                edit_value = st.number_input("Glucosa (mg/dL)", min_value=20, max_value=600, value=int(selected_row["value_mg_dl"]))
                context_options = ["Antes de la comida", "Después de la comida", "Glucosa al azar"]
                current_context = selected_row.get("context", "Glucosa al azar")
                edit_context = st.selectbox(
                    "Tipo de medición",
                    context_options,
                    index=context_options.index(current_context) if current_context in context_options else 2,
                )
                edit_notes = st.text_area("Notas", value=selected_row.get("notes", ""))
                edit_submit = st.form_submit_button("Guardar cambios")

            if edit_submit:
                edit_recorded_at = selected_row["recorded_at"].isoformat()
                if has_duplicate(patient_code, "glucose", edit_recorded_at, exclude_id=selected_id):
                    st.error("Ya existe otra medición de glucosa con esa fecha/hora.")
                else:
                    payload = {
                        "value_mg_dl": float(edit_value),
                        "context": edit_context,
                        "symptoms": selected_row.get("symptoms", ""),
                        "meds_taken": selected_row.get("meds_taken", []),
                        "insulin_units": selected_row.get("insulin_units", None),
                        "dose": selected_row.get("dose", ""),
                        "notes": edit_notes,
                    }
                    save_record(patient_code, "glucose", edit_recorded_at, payload, fernet, record_id=selected_id)
                    st.success("Registro actualizado.")
                    st.rerun()

        st.markdown("**Eliminar registro**")
        delete_options = {
            f"{row['id']} | {row['recorded_at']} | {row['record_type']}": int(row["id"])
            for _, row in all_df.iterrows()
        }
        delete_label = st.selectbox("Selecciona registro a eliminar", list(delete_options.keys()))
        if st.button("Eliminar seleccionado", type="secondary"):
            delete_record(delete_options[delete_label], owner=patient_code)
            st.success("Registro eliminado.")
            st.rerun()

with tabs[3]:
    st.subheader("Exportación clínica y compartición segura")
    glucose_df = to_dataframe(load_records(patient_code, fernet, "glucose"))
    hba1c_df = to_dataframe(load_records(patient_code, fernet, "hba1c"))
    events_df = to_dataframe(load_records(patient_code, fernet, "event"))

    st.markdown("**Exportar en 1 clic**")
    st.download_button(
        "Descargar glucosa CSV",
        data=dataframe_to_csv_bytes(glucose_df),
        file_name="glucosa.csv",
        mime="text/csv",
    )

    excel_bytes = dataframe_to_excel_bytes(
        {
            "Glucosa": glucose_df,
            "HbA1c": hba1c_df,
            "Eventos": events_df,
        }
    )
    st.download_button(
        "Descargar Excel clínico",
        data=excel_bytes,
        file_name="reporte_clinico.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    summary_lines = []
    if not glucose_df.empty:
        summary = summarize_glucose(glucose_df, target_low, target_high, hypo_threshold, hyper_threshold)
        summary_lines = [
            f"Promedio 7 días: {summary.avg_7d:.1f} mg/dL" if summary.avg_7d else "Promedio 7 días: N/A",
            f"Promedio 14 días: {summary.avg_14d:.1f} mg/dL" if summary.avg_14d else "Promedio 14 días: N/A",
            f"Promedio 30 días: {summary.avg_30d:.1f} mg/dL" if summary.avg_30d else "Promedio 30 días: N/A",
            f"% en rango objetivo: {summary.in_range_pct:.1f}%",
            f"Episodios hipo/hiper: {summary.hypo_count}/{summary.hyper_count}",
        ]

    pdf_bytes = build_pdf_report(patient_name, summary_lines, glucose_df, hba1c_df)
    st.download_button(
        "Descargar PDF para consulta",
        data=pdf_bytes,
        file_name="reporte_consulta.pdf",
        mime="application/pdf",
    )

    st.markdown("**Compartir cifrado con el doctor**")
    valid_hours = st.slider("Validez del paquete (horas)", min_value=1, max_value=168, value=24)
    if st.button("Generar paquete cifrado"):
        glucose_share_df = glucose_df.copy()
        hba1c_share_df = hba1c_df.copy()
        events_share_df = events_df.copy()
        if not glucose_share_df.empty:
            glucose_share_df["recorded_at"] = glucose_share_df["recorded_at"].astype(str)
        if not hba1c_share_df.empty:
            hba1c_share_df["recorded_at"] = hba1c_share_df["recorded_at"].astype(str)
        if not events_share_df.empty:
            events_share_df["recorded_at"] = events_share_df["recorded_at"].astype(str)

        payload = {
            "patient_name": patient_name,
            "age": age,
            "glucose": glucose_share_df.to_dict(orient="records"),
            "hba1c": hba1c_share_df.to_dict(orient="records"),
            "events": events_share_df.to_dict(orient="records"),
        }
        share_key, token = build_encrypted_share_payload(payload, valid_hours=valid_hours)
        st.code(f"Clave para doctor (enviar por canal separado): {share_key}")
        st.download_button(
            "Descargar paquete cifrado",
            data=token,
            file_name="compartir_doctor.cmg",
            mime="application/octet-stream",
        )
        st.info("Comparte el archivo y la clave por canales distintos para mayor seguridad.")

    st.markdown("**Abrir paquete recibido (modo doctor/prueba)**")
    uploaded_file = st.file_uploader("Sube archivo .cmg", type=["cmg"])
    input_key = st.text_input("Clave del paquete")
    if st.button("Descifrar paquete") and uploaded_file and input_key:
        try:
            token_data = uploaded_file.read()
            decrypted = Fernet(input_key.encode("utf-8")).decrypt(token_data)
            unpacked = json.loads(decrypted.decode("utf-8"))
            expires_at = datetime.fromisoformat(unpacked["expires_at"])
            if datetime.utcnow() > expires_at:
                st.error("El paquete compartido ha expirado.")
            else:
                st.success("Paquete válido y descifrado.")
                st.json({"patient_name": unpacked["data"].get("patient_name", ""), "expires_at": unpacked["expires_at"]})
        except Exception:
            st.error("No fue posible descifrar. Verifica archivo y clave.")

with tabs[4]:
    st.subheader("Recordatorios configurables")
    reminder_time_default = datetime.strptime(reminders.get("glucose_time", "08:00"), "%H:%M").time()
    reminder_hba1c_default = int(reminders.get("hba1c_day", 90))

    with st.form("reminders_form"):
        glucose_time = st.time_input("Hora diaria recomendada para glucosa", value=reminder_time_default)
        hba1c_day = st.number_input("Frecuencia sugerida de HbA1c (días)", min_value=30, max_value=365, value=reminder_hba1c_default)
        submitted = st.form_submit_button("Guardar recordatorios")

    if submitted:
        set_setting("reminders", json.dumps({"glucose_time": glucose_time.strftime("%H:%M"), "hba1c_day": int(hba1c_day)}), owner=patient_code)
        st.success("Recordatorios guardados.")

    st.info(
        "En versión web, los recordatorios son informativos dentro de la app. "
        "Para móvil futuro, se podrán convertir en notificaciones push."
    )

st.markdown(
    """
    <div style="background-color: #f3f4f6; padding: 16px; border-radius: 8px; margin-top: 20px;">
        <p><strong>Nota de seguridad clínica:</strong> Esta aplicación no realiza diagnóstico ni reemplaza atención médica.
        Ante valores extremos o síntomas, contacta a tu médico o servicio de urgencias.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
