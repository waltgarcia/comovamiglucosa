# ¿Cómo va mi glucosa? (Web MVP)

Aplicación web en Streamlit para pacientes con diabetes que necesitan registrar información clínica y compartirla con su médico.

## Funcionalidades principales

- Persistencia real en SQLite (`data/app.db`).
- Cuentas por paciente (código + PIN) y consentimiento explícito.
- Aislamiento de datos por paciente (cada usuario ve solo sus registros).
- Registro clínico ampliado:
   - Glucosa con fecha/hora, contexto, relación con comida, síntomas, medicación, dosis y notas.
   - HbA1c.
   - Eventos relevantes (síntomas/actividad/ajustes).
- Validaciones de captura (incluye control de duplicados por fecha/hora y tipo).
- Resumen médico automático:
   - Promedios 7/14/30 días.
   - Mínimo/máximo.
   - % de mediciones en rango objetivo.
   - Conteo de episodios hipo/hiper.
- Gráficas de tendencia con rangos personalizados por el médico.
- Historial editable y eliminación de registros.
- Vista cronológica unificada.
- Exportación clínica en 1 clic:
   - CSV, Excel y PDF.
- Compartición segura:
   - Paquete cifrado temporal para enviar al doctor.
- Recordatorios configurables (base web preparada para futura versión móvil con push).

## Estructura del proyecto

- `streamlit_app.py`: interfaz principal.
- `app/db.py`: persistencia SQLite.
- `app/security.py`: hashing de PIN y cifrado.
- `app/validation.py`: validaciones de datos.
- `app/analytics.py`: métricas y línea de tiempo.
- `app/exporters.py`: exportaciones CSV/Excel/PDF y paquete cifrado.
- `tests/`: pruebas básicas.

## Instalación y ejecución

1. Instala dependencias:

    ```bash
    pip install -r requirements.txt
    ```

2. Ejecuta la app:

    ```bash
    streamlit run streamlit_app.py
    ```

3. Primer uso:

   - En la pestaña **Crear cuenta paciente**, define un código único y tu PIN.
   - El código puede ser alfanumérico o numérico (ejemplo: `12345` o `paciente01`).
   - El PIN debe tener 4 números.
   - Luego ingresa con ese código y PIN en **Ingresar**.

## Flujo paciente-doctor

Esta app está pensada para dos objetivos prácticos:

- Que los pacientes tengan un registro digital continuo de sus mediciones de glucosa.
- Evitar depender de hojas en papel que se pueden recortar, extraviar o deteriorar.
- Que el doctor pueda valorar tendencias, episodios y cumplimiento con información más ordenada.

### Para pacientes

- Registra tus cifras de glucosa y eventos clínicos en la app.
- Descarga y comparte un paquete cifrado desde la sección **Exportar y compartir**.
- Comparte el archivo cifrado por un canal y la clave por otro canal diferente para mayor seguridad.

### Para doctores

Para revisar información de un paciente se requieren:

- Código del paciente.
- Archivo cifrado compartido (`.cmg`).
- Clave de cifrado temporal (ejemplo):

  `bt65lYn_O4-K3bK-GgKE3nYRiey9j8hf9v7O-5ShTj8=`

Con estos elementos, el doctor puede usar la opción de descifrado en la app para valorar las cifras de glucosa y su contexto clínico.

## Seguridad y despliegue recomendado

- En producción, define `APP_PEPPER` en `st.secrets`.
- Despliega siempre con HTTPS para proteger datos en tránsito.
- El paquete compartido cifrado se recomienda enviarlo con la clave por un canal distinto.

## Roadmap hacia móvil

La lógica ya está desacoplada en módulos para facilitar migración futura a API + app móvil (Flutter/React Native), manteniendo reglas clínicas, seguridad y exportación.
