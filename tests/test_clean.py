"""Datas de rolagem seguem a regra do contrato e o calendário real."""

import pandas as pd
import pytest

from abertura import clean

from abertura.clean import roll_dates
from abertura.sessions import b3_sessions


def test_win_rolls_on_wednesday_nearest_the_15th_of_even_months():
    dates = roll_dates('win', b3_sessions('2025-01-01', '2025-12-31').index)
    assert [date.strftime('%Y-%m-%d') for date in dates] == [
        '2025-02-12', '2025-04-16', '2025-06-18', '2025-08-13', '2025-10-15', '2025-12-17']


def test_win_roll_on_holiday_moves_to_next_session():
    dates = roll_dates('win', b3_sessions('2022-10-01', '2022-10-31').index)
    assert list(dates) == [pd.Timestamp('2022-10-13')]


def test_wdo_rolls_on_last_session_of_each_month():
    dates = roll_dates('wdo', b3_sessions('2026-01-01', '2026-03-31').index)
    assert [date.strftime('%Y-%m-%d') for date in dates] == ['2026-01-30', '2026-02-27', '2026-03-31']


def test_unknown_asset_is_rejected():
    try:
        roll_dates('spx', b3_sessions('2026-01-01', '2026-01-31').index)
    except ValueError as error:
        assert 'spx' in str(error)
    else:
        raise AssertionError('Ativo sem rolagem deveria falhar.')


def _candles(days: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """Dois candles por dia (09:00 e 17:00 BRT); open do primeiro, close do último."""
    rows = []
    for day, (open_, close) in days.items():
        base = pd.Timestamp(day, tz='UTC')
        rows.append((base + pd.Timedelta(hours=12), open_, open_))
        rows.append((base + pd.Timedelta(hours=20), close, close))
    return pd.DataFrame(rows, columns=['datetime', 'open', 'close']).assign(high=0.0, low=0.0)


def test_gap_event_study_averages_gap_around_roll_days():
    calendar = pd.DatetimeIndex(pd.to_datetime(['2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09']))
    candles = _candles({'2025-01-06': (100, 100), '2025-01-07': (110, 100),
                        '2025-01-08': (95, 100), '2025-01-09': (101, 100)})
    table = clean.gap_event_study(candles, calendar, pd.DatetimeIndex([calendar[1]]), span=1)
    # offset -1: sem pregão anterior (NaN); 0: 110/100-1 = +10%; +1: 95/100-1 = -5%.
    assert table.offset.tolist() == [-1, 0, 1]
    assert table.n.tolist() == [0, 1, 1]
    assert pd.isna(table.media_pct[0])
    assert table.media_pct[1] == pytest.approx(10.0)
    assert table.media_pct[2] == pytest.approx(-5.0)
    assert table.positivos_pct.tolist()[1:] == [100.0, 0.0]


def test_gap_event_study_skips_gap_when_previous_session_is_missing():
    calendar = pd.DatetimeIndex(pd.to_datetime(['2025-01-06', '2025-01-07', '2025-01-08']))
    candles = _candles({'2025-01-06': (100, 100), '2025-01-08': (120, 100)})  # falta 07
    table = clean.gap_event_study(candles, calendar, pd.DatetimeIndex([calendar[1]]), span=1)
    assert table.n.tolist() == [0, 0, 0]  # 06 sem anterior; 07 ausente; 08 sem anterior nos dados


def test_gap_event_study_two_rolls_mean_and_positive_share():
    calendar = pd.DatetimeIndex(pd.to_datetime(['2025-01-06', '2025-01-07', '2025-01-08', '2025-01-09']))
    candles = _candles({'2025-01-06': (100, 100), '2025-01-07': (110, 100),
                        '2025-01-08': (90, 100), '2025-01-09': (100, 100)})
    table = clean.gap_event_study(candles, calendar, calendar[[1, 2]], span=0)
    # gaps no offset 0: +10% e -10%.
    assert table.n.tolist() == [2]
    assert table.media_pct[0] == pytest.approx(0.0)
    assert table.positivos_pct[0] == 50.0
