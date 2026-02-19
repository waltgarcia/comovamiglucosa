from app.validation import validate_glucose_value, validate_pin


def test_validate_pin_rules():
    ok, _ = validate_pin("1234")
    assert ok

    ok_short, _ = validate_pin("123")
    assert not ok_short

    ok_alpha, _ = validate_pin("12ab")
    assert not ok_alpha


def test_validate_glucose_value_rules():
    valid, _ = validate_glucose_value(110)
    assert valid

    low, _ = validate_glucose_value(10)
    assert not low

    high, _ = validate_glucose_value(700)
    assert not high
