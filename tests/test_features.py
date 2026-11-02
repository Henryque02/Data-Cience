"""Variáveis usam instantes em UTC, preço conhecido e só pregões anteriores."""

import numpy as np
import pandas as pd

from abertura.features import (asia_session_return, last_price, realized_vol, session_moments,
                               target_features)
from abertura.sessions import b3_sessions, daily_sessions


def m1(start, closes):
    times = pd.date_range(start, periods=len(closes), freq='min', tz='UTC')
    return pd.DataFrame({'datetime': times, 'open': closes, 'high': closes, 'low': closes,
                         'close': closes, 'volume': 1.0})


def moments(*values):
    return pd.Series(pd.to_datetime(list(values), utc=True, format='ISO8601'))


def test_last_price_uses_candle_opened_at_moment_and_ignores_later_ones():
    candles = m1('2026-03-10 11:56', [1.0, 2.0, 3.0, 4.0])
    result = last_price(candles, moments('2026-03-10 11:58', '2026-03-10 11:58:30'), 60)
    assert result.tolist() == [3.0, 3.0]


def test_last_price_treats_old_or_absent_price_as_missing():
    candles = m1('2026-03-10 10:00', [1.0])
    result = last_price(candles, moments('2026-03-10 11:00', '2026-03-10 11:01', '2026-03-10 09:00'), 60)
    assert result.iloc[0] == 1.0
    assert result.iloc[1:].isna().all()


def test_realized_vol_sums_only_returns_inside_interval():
    candles = m1('2026-03-10 00:00', np.exp([0.0, 0.5, 0.51, 0.54, 2.0]))
    result = realized_vol(candles, moments('2026-03-10 00:01'), moments('2026-03-10 00:03'))
    assert np.isclose(result.iloc[0], np.sqrt(0.01 ** 2 + 0.03 ** 2))


def test_session_moments_use_cutoff_in_utc_and_previous_session_close():
    calendar = b3_sessions('2026-03-09', '2026-03-12')
    frame = pd.concat([m1('2026-03-09 12:00', [1.0, 1.0]), m1('2026-03-10 12:00', [1.0, 1.0, 1.0]),
                       m1('2026-03-11 12:00', [1.0])], ignore_index=True)
    sessions = daily_sessions(frame, calendar)
    result = session_moments(sessions, calendar.index, '08:58')
    assert result.loc['2026-03-11', 'cutoff_utc'] == pd.Timestamp('2026-03-11 11:58', tz='UTC')
    assert result.loc['2026-03-11', 'prev_close_utc'] == pd.Timestamp('2026-03-10 12:02', tz='UTC')
    assert result.loc['2026-03-11', 'prev2_close_utc'] == pd.Timestamp('2026-03-09 12:01', tz='UTC')


def test_session_moments_leave_previous_close_empty_after_missing_session():
    calendar = b3_sessions('2026-03-09', '2026-03-12')
    frame = pd.concat([m1('2026-03-09 12:00', [1.0]), m1('2026-03-11 12:00', [1.0])], ignore_index=True)
    result = session_moments(daily_sessions(frame, calendar), calendar.index, '08:58')
    assert pd.isna(result.loc['2026-03-11', 'prev_close_utc'])


def test_target_features_use_only_previous_sessions():
    frame = pd.concat([m1(f'2026-03-{day:02d} 12:00', [100.0, 110.0]) for day in range(2, 8)], ignore_index=True)
    frame = pd.concat([frame, m1('2026-03-08 12:00', [100.0, 500.0])], ignore_index=True)
    dates = pd.date_range('2026-03-02', '2026-03-08', freq='D', name='date_brt')
    result = target_features(frame, dates)
    assert np.isclose(result.loc['2026-03-08', 'x_pre_target_range_5d'], 0.10)
    assert np.isclose(result.loc['2026-03-08', 'x_pre_target_return_prev'], 0.10)
    assert pd.isna(result.loc['2026-03-06', 'x_pre_target_range_5d'])


def test_asia_session_is_defined_in_market_time():
    closes = np.full(391, 100.0)
    closes[-1] = 110.0
    candles = m1('2026-03-10 00:00', closes)
    dates = pd.DatetimeIndex(['2026-03-10'], name='date_brt')
    session = {'timezone': 'Asia/Tokyo', 'start': '09:00', 'end': '15:30'}
    assert np.isclose(asia_session_return(candles, dates, session, 60).iloc[0], 0.10)
