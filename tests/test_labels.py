"""Rótulos seguem as definições da seção 5, inclusive nos limites."""

import numpy as np
import pandas as pd

from abertura.labels import behavior, gap_class, opening_window, range_labels
from abertura.sessions import daily_sessions


def days(count):
    return pd.date_range('2026-03-10', periods=count, freq='D')


def window(rows):
    return pd.DataFrame(rows, columns=['open', 'high', 'low', 'close'], index=days(len(rows)))


def test_gap_class_is_strict_at_threshold_and_keeps_missing():
    gap = pd.Series([0.004, -0.004, 0.003, -0.003, np.nan], index=days(5))
    result = gap_class(gap, 0.003)
    assert result.iloc[:4].tolist() == ['alta', 'baixa', 'normal', 'normal']
    assert pd.isna(result.iloc[4])


def test_behavior_after_gap_up():
    frame = window([[101, 102.5, 99.9, 102], [101, 102.5, 100.5, 102], [101, 101.5, 100.5, 101.05],
                    [101, 101.5, 100.5, 100.2]])
    classes = pd.Series(['alta'] * 4, index=frame.index)
    result = behavior(frame, pd.Series(100.0, index=frame.index), classes, 0.001)
    assert result.tolist() == ['reversao', 'tendencia', 'lateral', 'lateral']


def test_behavior_after_gap_down_is_mirrored():
    frame = window([[99, 100.1, 98, 98.5], [99, 99.5, 98, 98.5], [99, 99.5, 98.5, 98.95]])
    classes = pd.Series(['baixa'] * 3, index=frame.index)
    result = behavior(frame, pd.Series(100.0, index=frame.index), classes, 0.001)
    assert result.tolist() == ['reversao', 'tendencia', 'lateral']


def test_touching_previous_close_exactly_counts_as_reversal():
    frame = window([[101, 102, 100, 101.5]])
    classes = pd.Series(['alta'], index=frame.index)
    assert behavior(frame, pd.Series(100.0, index=frame.index), classes, 0.001).iloc[0] == 'reversao'


def test_behavior_is_missing_without_relevant_gap():
    frame = window([[100.1, 101, 99, 100.5], [100, 101, 99, 100.5]])
    classes = pd.Series(['normal', np.nan], index=frame.index)
    assert behavior(frame, pd.Series(100.0, index=frame.index), classes, 0.001).isna().all()


def test_range_is_relative_to_open():
    result = range_labels(window([[100, 102, 99, 101]]))
    assert np.isclose(result.y_range_high.iloc[0], 0.02)
    assert np.isclose(result.y_range_low.iloc[0], -0.01)


def test_opening_window_starts_at_first_candle_and_stops_at_limit():
    times = pd.date_range('2026-03-10 09:03', periods=5, freq='min', tz='America/Sao_Paulo').tz_convert('UTC')
    candles = pd.DataFrame({'datetime': times, 'open': [10.0, 11, 12, 13, 14], 'high': [10.5, 11, 12, 13, 99],
                            'low': [9.0, 11, 12, 13, 1], 'close': [10.0, 11, 12, 13, 14], 'volume': 1.0})
    result = opening_window(candles, daily_sessions(candles), 4).loc['2026-03-10']
    assert result.tolist() == [10.0, 13.0, 9.0, 13.0]
