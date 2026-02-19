from __future__ import annotations

import io
import json
from datetime import datetime, timedelta

import pandas as pd
from cryptography.fernet import Fernet
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def dataframe_to_excel_bytes(df_map: dict[str, pd.DataFrame]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in df_map.items():
            safe_sheet = sheet_name[:31] if sheet_name else "Sheet1"
            df.to_excel(writer, sheet_name=safe_sheet, index=False)
    output.seek(0)
    return output.read()


def build_pdf_report(
    patient_name: str,
    summary_lines: list[str],
    glucose_df: pd.DataFrame,
    hba1c_df: pd.DataFrame,
) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Reporte clínico de glucosa")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Paciente: {patient_name or 'No especificado'}")
    y -= 16
    c.drawString(50, y, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 20

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Resumen")
    y -= 16
    c.setFont("Helvetica", 10)
    for line in summary_lines:
        c.drawString(60, y, f"- {line}")
        y -= 14
        if y < 80:
            c.showPage()
            y = height - 50

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Últimos registros de glucosa")
    y -= 16
    c.setFont("Helvetica", 9)
    for _, row in glucose_df.head(15).iterrows():
        c.drawString(60, y, f"{row['recorded_at']} | {row['value_mg_dl']} mg/dL | {row.get('context', '')}")
        y -= 12
        if y < 80:
            c.showPage()
            y = height - 50

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Registros HbA1c")
    y -= 16
    c.setFont("Helvetica", 9)
    for _, row in hba1c_df.head(10).iterrows():
        c.drawString(60, y, f"{row['recorded_at']} | {row['value_pct']}%")
        y -= 12
        if y < 80:
            c.showPage()
            y = height - 50

    c.save()
    buffer.seek(0)
    return buffer.read()


def build_encrypted_share_payload(data: dict, valid_hours: int = 24) -> tuple[str, bytes]:
    key = Fernet.generate_key()
    fernet = Fernet(key)
    payload = {
        "expires_at": (datetime.utcnow() + timedelta(hours=valid_hours)).isoformat(),
        "data": data,
    }
    token = fernet.encrypt(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return key.decode("utf-8"), token
