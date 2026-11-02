"""Rótulos do pregão; usam dados futuros por definição e ficam em colunas y_."""

from __future__ import annotations

import pandas as pd

from .sessions import local_dates


def opening_window(candles: pd.DataFrame, sessions: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Resume cada pregão na janela que começa no primeiro candle observado."""
    dates = local_dates(candles)
    inside = candles.datetime < dates.map(sessions.first_utc) + pd.Timedelta(minutes=minutes)
    return candles[inside].groupby(dates[inside]).agg(
        open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))


def gap_class(gap: pd.Series, threshold: float) -> pd.Series:
    """Classifica o gap; sem gap válido o rótulo fica ausente."""
    labels = pd.Series('normal', index=gap.index, dtype='object')
    labels[gap > threshold] = 'alta'
    labels[gap < -threshold] = 'baixa'
    return labels.where(gap.notna())


def behavior(window: pd.DataFrame, prev_close: pd.Series, classes: pd.Series, trend_margin: float) -> pd.Series:
    """Só existe em dia com gap relevante; reversão tem prioridade sobre tendência."""
    up, down = classes.eq('alta'), classes.eq('baixa')
    move = window.close / window.open - 1
    aligned_move = move.where(up, -move)
    touched = (up & window.low.le(prev_close)) | (down & window.high.ge(prev_close))
    labels = pd.Series('lateral', index=window.index, dtype='object')
    labels[aligned_move > trend_margin] = 'tendencia'
    labels[touched] = 'reversao'
    return labels.where(up | down)


def range_labels(window: pd.DataFrame) -> pd.DataFrame:
    """Máxima e mínima da janela relativas à abertura."""
    return pd.DataFrame({'y_range_high': window.high / window.open - 1,
                         'y_range_low': window.low / window.open - 1})
