"""Cobertura e intervalos observados, sem inventar preços ou calendários CFD."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .sessions import LOCAL_TIMEZONE


def missing_runs(missing: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Agrupa ausências consecutivas pelo calendário, atravessando fins de semana."""
    columns = ['first_date', 'last_date', 'missing_sessions', 'reason']
    if missing.empty:
        return pd.DataFrame(columns=columns)
    missing = missing.sort_index()
    positions = calendar.index.get_indexer(missing.index)
    if (positions < 0).any():
        raise ValueError('Data ausente fora do calendário informado.')
    starts = np.r_[True, np.diff(positions) != 1] | missing.reason.ne(missing.reason.shift()).to_numpy()
    rows = []
    for _, group in missing.groupby(np.cumsum(starts)):
        rows.append({'first_date': group.index[0], 'last_date': group.index[-1],
                     'missing_sessions': len(group), 'reason': group.reason.iloc[0]})
    return pd.DataFrame(rows, columns=columns)


def cutoff_staleness(times: pd.Series, cutoffs: pd.Series) -> pd.Series:
    """Minutos desde o último candle com datetime <= corte (NaN se não houver)."""
    ordered = np.sort(times.dropna().to_numpy(dtype='datetime64[ns]'))
    cut = cutoffs.to_numpy(dtype='datetime64[ns]')
    pos = np.searchsorted(ordered, cut, side='right') - 1
    last = ordered[np.clip(pos, 0, None)] if len(ordered) else cut
    age = (cut - last) / np.timedelta64(1, 'm')
    return pd.Series(np.where(pos >= 0, age, np.nan), index=cutoffs.index, dtype='float64')


def candle_gaps(
    frame: pd.DataFrame,
    *,
    min_missing_minutes: int = 15,
    calendar: pd.DataFrame | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Lista intervalos vazios; externos sem calendário não são falhas confirmadas."""
    if min_missing_minutes < 1 or (limit is not None and limit < 1):
        raise ValueError('Limiar e limite devem ser positivos.')
    times = frame.datetime.sort_values().reset_index(drop=True)
    empty_minutes = times.diff().dt.total_seconds().div(60).sub(1)
    indexes = empty_minutes[empty_minutes >= min_missing_minutes].sort_values(ascending=False).index
    if limit is not None:
        indexes = indexes[:limit]
    rows = []
    zone = LOCAL_TIMEZONE if calendar is not None else 'UTC'
    for index in indexes:
        previous, following = times.iloc[index - 1], times.iloc[index]
        previous_date = previous.tz_convert(zone).tz_localize(None).normalize()
        next_date = following.tz_convert(zone).tz_localize(None).normalize()
        if previous_date == next_date:
            classification = 'intraday_investigate' if calendar is not None else 'intraday_without_source_calendar'
        elif calendar is None:
            classification = 'between_dates_without_source_calendar'
        elif previous_date not in calendar.index or next_date not in calendar.index:
            classification = 'outside_calendar_investigate'
        else:
            has_missing = calendar.index.searchsorted(previous_date, side='right') < calendar.index.searchsorted(next_date, side='left')
            classification = 'missing_sessions' if has_missing else 'between_sessions'
        rows.append({'previous_utc': previous, 'next_utc': following,
                     'missing_minutes': int(empty_minutes.iloc[index]), 'classification': classification})
    return pd.DataFrame(rows, columns=['previous_utc', 'next_utc', 'missing_minutes', 'classification'])


def late_opens_by_quarter(sessions: pd.DataFrame) -> pd.DataFrame:
    """Conta por trimestre os pregões regulares abertos depois da referência."""
    regular = sessions[sessions.is_expected_session & ~sessions.is_special_open]
    late = regular.open_delay_minutes.gt(0).astype(bool)
    quarters = regular.index.to_period('Q').astype(str)
    result = late.groupby(quarters).agg(pregoes='size', com_atraso='sum')
    result['pct'] = (100 * result.com_atraso / result.pregoes).round(1)
    return result


def coverage_tables(interim_dir: str | Path, assets: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resume cobertura observada e contagens mensais em UTC, por ativo."""
    summaries, monthly = [], {}
    for asset_id, asset in assets.items():
        path = Path(interim_dir) / f'{asset_id}_m1.parquet'
        times = pd.read_parquet(path, columns=['datetime']).datetime
        dates = times.dt.tz_localize(None).dt.normalize()
        months = dates.dt.to_period('M').astype(str)
        monthly[asset_id] = months.value_counts().sort_index()
        summaries.append({'asset': asset_id, 'source': asset['source'], 'rows': len(times),
                          'first_utc': times.min(), 'last_utc': times.max(),
                          'utc_dates_with_data': dates.nunique(), 'parquet_mb': path.stat().st_size / 1e6})
    return pd.DataFrame(summaries), pd.DataFrame(monthly).fillna(0).astype('int64').sort_index()
