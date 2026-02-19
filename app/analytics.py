from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class GlucoseSummary:
    avg_7d: float | None
    avg_14d: float | None
    avg_30d: float | None
    minimum: float | None
    maximum: float | None
    in_range_pct: float
    hypo_count: int
    hyper_count: int


def _mean_or_none(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.mean())


def summarize_glucose(
    glucose_df: pd.DataFrame,
    target_low: int,
    target_high: int,
    hypo_threshold: int,
    hyper_threshold: int,
) -> GlucoseSummary:
    if glucose_df.empty:
        return GlucoseSummary(None, None, None, None, None, 0.0, 0, 0)

    df = glucose_df.copy()
    df["recorded_at"] = pd.to_datetime(df["recorded_at"])
    df = df.sort_values("recorded_at")
    now = pd.Timestamp.now()

    def within_days(days: int) -> pd.Series:
        start = now - pd.Timedelta(days=days)
        return df.loc[df["recorded_at"] >= start, "value_mg_dl"]

    values = df["value_mg_dl"]
    in_range = values.between(target_low, target_high, inclusive="both")

    return GlucoseSummary(
        avg_7d=_mean_or_none(within_days(7)),
        avg_14d=_mean_or_none(within_days(14)),
        avg_30d=_mean_or_none(within_days(30)),
        minimum=float(values.min()),
        maximum=float(values.max()),
        in_range_pct=float(in_range.mean() * 100.0),
        hypo_count=int((values < hypo_threshold).sum()),
        hyper_count=int((values > hyper_threshold).sum()),
    )


def build_timeline(glucose_df: pd.DataFrame, hba1c_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    if not glucose_df.empty:
        g = glucose_df.copy()
        g["evento"] = "Glucosa"
        g["detalle"] = g["value_mg_dl"].astype(str) + " mg/dL" + " | " + g.get("context", "")
        frames.append(g[["recorded_at", "evento", "detalle", "notes"]])

    if not hba1c_df.empty:
        h = hba1c_df.copy()
        h["evento"] = "HbA1c"
        h["detalle"] = h["value_pct"].astype(str) + " %"
        frames.append(h[["recorded_at", "evento", "detalle", "notes"]])

    if not events_df.empty:
        e = events_df.copy()
        e["evento"] = e.get("title", "Evento")
        e["detalle"] = e.get("notes", "")
        e["notes"] = e.get("notes", "")
        frames.append(e[["recorded_at", "evento", "detalle", "notes"]])

    if not frames:
        return pd.DataFrame(columns=["recorded_at", "evento", "detalle", "notes"])

    timeline = pd.concat(frames, ignore_index=True)
    timeline["recorded_at"] = pd.to_datetime(timeline["recorded_at"])
    return timeline.sort_values("recorded_at", ascending=False)
