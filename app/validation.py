from datetime import datetime


def validate_pin(pin: str) -> tuple[bool, str]:
    if len(pin) < 4:
        return False, "El PIN debe tener al menos 4 dígitos."
    if not pin.isdigit():
        return False, "El PIN debe contener solo números."
    return True, ""


def parse_datetime(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)


def validate_glucose_value(value: float) -> tuple[bool, str]:
    if value < 20 or value > 600:
        return False, "El valor de glucosa parece fuera de rango fisiológico (20-600 mg/dL)."
    return True, ""


def ensure_required(text: str, label: str) -> tuple[bool, str]:
    if not text.strip():
        return False, f"El campo {label} es obligatorio."
    return True, ""
