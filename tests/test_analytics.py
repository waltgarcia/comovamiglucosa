import pandas as pd

from app.analytics import summarize_glucose


def test_summarize_glucose_basic_metrics():
    now = pd.Timestamp.now()
    df = pd.DataFrame(
        {
            "recorded_at": [
                (now - pd.Timedelta(days=1)).isoformat(),
                (now - pd.Timedelta(days=3)).isoformat(),
                (now - pd.Timedelta(days=10)).isoformat(),
            ],
            "value_mg_dl": [90.0, 210.0, 65.0],
        }
    )

    summary = summarize_glucose(df, target_low=70, target_high=180, hypo_threshold=70, hyper_threshold=200)

    assert summary.minimum == 65.0
    assert summary.maximum == 210.0
    assert summary.hypo_count == 1
    assert summary.hyper_count == 1
    assert summary.in_range_pct > 0
