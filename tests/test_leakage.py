"""Nenhuma variável enxerga mais do que estaria disponível no seu horário."""

import numpy as np
import pandas as pd
import pytest

from abertura.daily import build_target
from abertura.models import check_features
from abertura.sessions import LOCAL_TIMEZONE, b3_sessions

DAY = pd.Timestamp('2026-03-11')
CUTOFF = pd.Timestamp('2026-03-11 08:58', tz=LOCAL_TIMEZONE).tz_convert('UTC')
PARAMS = {
    'sample': {'max_open_delay_minutes': 15},
    'features': {'pre_open': {'cutoff_brt': '08:58', 'recent_windows_minutes': [60, 180],
                              'max_price_age_minutes': 60, 'reference_max_age_minutes': 240,
                              'asia_sessions': {'nikkei': {'timezone': 'Asia/Tokyo', 'start': '09:00',
                                                           'end': '15:30'}}}},
    'labels': {'post_open_minutes': 60, 'gap_threshold': {'value': 0.003},
               'behavior': {'trend_margin': 0.001}},
}


def candles(times, seed):
    closes = 100 * np.exp(np.random.default_rng(seed).normal(0, 0.001, len(times)).cumsum())
    return pd.DataFrame({'datetime': times, 'open': closes * 1.0001, 'high': closes * 1.002,
                         'low': closes * 0.998, 'close': closes, 'volume': 1.0})


def target_candles():
    days = ['2026-03-09', '2026-03-10', '2026-03-11']
    times = [pd.date_range(f'{day} 09:00', f'{day} 18:24', freq='min', tz=LOCAL_TIMEZONE) for day in days]
    return candles(times[0].append(times[1:]).tz_convert('UTC'), 1)


def external_candles(seed=2):
    return candles(pd.date_range('2026-03-06', '2026-03-12', freq='min', tz='UTC'), seed)


def build(target, external, nikkei=None):
    calendar = b3_sessions('2026-03-02', '2026-03-13')
    externals = {'spx': external, 'nikkei': external if nikkei is None else nikkei}
    return build_target('win', target, externals, calendar, PARAMS).loc[DAY]


def columns(row, prefix):
    return row[[name for name in row.index if name.startswith(prefix)]].astype(float)


def day_rows(target):
    return target.datetime.dt.tz_convert(LOCAL_TIMEZONE).dt.normalize().dt.tz_localize(None).eq(DAY)


def test_pre_open_ignores_candles_after_cutoff_and_the_whole_target_day():
    base = build(target_candles(), external_candles())
    external = external_candles()
    later = external.datetime > CUTOFF
    external.loc[later, ['open', 'high', 'low', 'close']] *= 2
    target = target_candles()
    target.loc[day_rows(target), ['open', 'high', 'low', 'close']] *= 3
    changed = build(target, external)
    assert len(columns(base, 'x_pre_')) > 8
    pd.testing.assert_series_equal(columns(base, 'x_pre_'), columns(changed, 'x_pre_'))


def test_pre_open_does_use_the_candle_opened_at_cutoff():
    base = build(target_candles(), external_candles())
    external = external_candles()
    external.loc[external.datetime.eq(CUTOFF), 'close'] *= 1.1
    assert build(target_candles(), external).x_pre_spx_overnight != base.x_pre_spx_overnight


def test_open_variables_ignore_everything_but_first_open():
    base = build(target_candles(), external_candles())
    target = target_candles()
    rows = target.index[day_rows(target)]
    target.loc[rows, ['high', 'low', 'close', 'volume']] *= 2
    target.loc[rows[1:], 'open'] *= 2
    changed = build(target, external_candles())
    assert len(columns(base, 'x_open_')) >= 2
    pd.testing.assert_series_equal(columns(base, 'x_open_'), columns(changed, 'x_open_'))


def test_open_variables_do_use_first_open():
    base = build(target_candles(), external_candles())
    target = target_candles()
    target.loc[target.index[day_rows(target)][0], 'open'] *= 1.05
    assert build(target, external_candles()).x_open_gap != base.x_open_gap


@pytest.mark.parametrize('name', ['x_open_gap', 'x_open_aligned_spx_overnight', 'y_gap_class'])
def test_gap_model_only_accepts_pre_open_variables(name):
    with pytest.raises(ValueError):
        check_features('y_gap_class', ['x_pre_spx_overnight', name])


def test_behavior_model_accepts_open_variables_but_not_labels():
    check_features('y_behavior', ['x_pre_spx_overnight', 'x_open_gap'])
    with pytest.raises(ValueError):
        check_features('y_behavior', ['x_open_gap', 'y_gap_class'])
