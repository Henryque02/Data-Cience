"""Variáveis pré-abertura (x_pre_) e de abertura observada (x_open_)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .sessions import LOCAL_TIMEZONE, local_dates

NANOSECONDS_PER_MINUTE = 60_000_000_000


def _nanoseconds(values: pd.Series) -> np.ndarray:
    """Converte instantes para inteiros UTC; ausentes ficam negativos."""
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit('ns').asi8


def last_price(candles: pd.DataFrame, moments: pd.Series, max_age_minutes: int) -> pd.Series:
    """Último close com candle aberto até cada instante; preço antigo vira NaN."""
    times = _nanoseconds(candles.datetime)
    stamps = _nanoseconds(moments)
    position = np.searchsorted(times, stamps, side='right') - 1
    known = position.clip(0)
    prices = candles.close.to_numpy()[known].astype(float)
    too_old = stamps - times[known] > max_age_minutes * NANOSECONDS_PER_MINUTE
    prices[moments.isna().to_numpy() | (position < 0) | too_old] = np.nan
    return pd.Series(prices, index=moments.index)


def realized_vol(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Raiz da soma dos retornos quadráticos de 1 min dentro de cada intervalo."""
    times = _nanoseconds(candles.datetime)
    squared = np.r_[0.0, np.diff(np.log(candles.close.to_numpy())) ** 2].cumsum()
    first = np.searchsorted(times, _nanoseconds(starts), side='right').clip(1)
    last = np.searchsorted(times, _nanoseconds(ends), side='right').clip(1)
    result = pd.Series(np.sqrt(squared[last - 1] - squared[first - 1]), index=starts.index)
    return result.where(starts.notna() & ends.notna())


def session_moments(sessions: pd.DataFrame, calendar: pd.DatetimeIndex, cutoff_brt: str) -> pd.DataFrame:
    """Instantes de referência de cada pregão, em UTC; sem D-1 nos dados fica vazio."""
    previous = pd.Series(calendar[:-1], index=calendar[1:])
    prev_date = sessions.index.to_series().map(previous)
    hours, minutes = (int(part) for part in cutoff_brt.split(':'))
    cutoff = sessions.index.tz_localize(LOCAL_TIMEZONE) + pd.Timedelta(hours=hours, minutes=minutes)
    return pd.DataFrame({'prev_close_utc': prev_date.map(sessions.last_utc),
                         'prev2_close_utc': prev_date.map(previous).map(sessions.last_utc),
                         'cutoff_utc': cutoff.tz_convert('UTC')}, index=sessions.index)


def asia_session_return(candles: pd.DataFrame, dates: pd.DatetimeIndex, session: dict, max_age: int) -> pd.Series:
    """Retorno do pregão asiático de cada data, definido no horário local do mercado."""
    midnight = dates.tz_localize(session['timezone'])
    moments = {key: pd.Series(midnight + pd.Timedelta(f'{session[key]}:00'), index=dates).dt.tz_convert('UTC')
               for key in ('start', 'end')}
    return last_price(candles, moments['end'], max_age) / last_price(candles, moments['start'], max_age) - 1


def external_features(name: str, candles: pd.DataFrame, moments: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Retornos e volatilidade de um ativo externo, só com preços até o corte."""
    reference_age = settings['reference_max_age_minutes']
    cutoff = last_price(candles, moments.cutoff_utc, settings['max_price_age_minutes'])
    previous = last_price(candles, moments.prev_close_utc, reference_age)
    earlier = last_price(candles, moments.prev2_close_utc, reference_age)
    result = pd.DataFrame(index=moments.index)
    result[f'x_pre_{name}_overnight'] = cutoff / previous - 1
    for minutes in settings['recent_windows_minutes']:
        start = moments.cutoff_utc - pd.Timedelta(minutes=minutes)
        result[f'x_pre_{name}_last_{minutes}m'] = cutoff / last_price(candles, start, reference_age) - 1
    result[f'x_pre_{name}_night_vol'] = realized_vol(candles, moments.prev_close_utc, moments.cutoff_utc)
    result[f'x_pre_{name}_prev_day'] = previous / earlier - 1
    if name in settings['asia_sessions']:
        session = settings['asia_sessions'][name]
        result[f'x_pre_{name}_session'] = asia_session_return(candles, moments.index, session, reference_age)
    return result


def target_features(candles: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Histórico do alvo até D-1, medido dentro dos pregões para ignorar a rolagem."""
    daily = candles.groupby(local_dates(candles)).agg(
        open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))
    result = pd.DataFrame({
        'x_pre_target_range_5d': (daily.high / daily.low - 1).rolling(5).mean().shift(1),
        'x_pre_target_return_prev': (daily.close / daily.open - 1).shift(1)})
    return result.reindex(dates)


def open_features(first_open: pd.Series, prev_close: pd.Series, is_roll_day: pd.Series) -> pd.DataFrame:
    """Gap observado: do dia D, só o open do primeiro candle; rolagem o invalida."""
    gap = (first_open / prev_close - 1).where(~is_roll_day)
    return pd.DataFrame({'x_open_gap': gap, 'x_open_gap_abs': gap.abs()})
