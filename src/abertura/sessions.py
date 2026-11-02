"""Datas de referência B3 e horários efetivamente observados nos futuros."""

from __future__ import annotations

import exchange_calendars as xcals
import pandas as pd

LOCAL_TIMEZONE = 'America/Sao_Paulo'


def b3_sessions(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DataFrame:
    """Usa datas BVMF e aberturas especiais; futuros regulares abrem às 09h."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if start > end:
        raise ValueError('Início posterior ao fim do calendário.')
    calendar = xcals.get_calendar('BVMF', start=start - pd.Timedelta(days=10), end=end + pd.Timedelta(days=10))
    reference = calendar.schedule.loc[start:end]
    result = pd.DataFrame(index=reference.index.copy())
    result.index.name = 'date_brt'
    result['is_special_open'] = result.index.isin(calendar.late_opens)
    regular = (result.index.tz_localize(LOCAL_TIMEZONE) + pd.Timedelta(hours=9)).tz_convert('UTC')
    result['expected_open_utc'] = pd.Series(regular, index=result.index, dtype='datetime64[ns, UTC]')
    special = result.is_special_open
    result.loc[special, 'expected_open_utc'] = reference.loc[special, 'open']
    return result


def local_dates(frame: pd.DataFrame) -> pd.Series:
    """Retorna datas civis brasileiras, mantendo timestamps originais intactos."""
    return frame.datetime.dt.tz_convert(LOCAL_TIMEZONE).dt.tz_localize(None).dt.normalize()


def daily_sessions(
    frame: pd.DataFrame,
    calendar: pd.DataFrame | None = None,
    *,
    window_minutes: int = 60,
    max_open_delay_minutes: int = 15,
) -> pd.DataFrame:
    """Resume horários reais; a abertura do dia é o primeiro candle observado."""
    if frame.empty or window_minutes < 1 or max_open_delay_minutes < 0:
        raise ValueError('Dados vazios, janela ou atraso inválidos.')
    dates = local_dates(frame)
    calendar = b3_sessions(dates.min(), dates.max()) if calendar is None else calendar
    observed = pd.DataFrame({'date_brt': dates, 'datetime': frame.datetime})
    result = observed.groupby('date_brt').datetime.agg(first_utc='min', last_utc='max', candle_count='size')
    result = result.join(calendar)
    result['is_expected_session'] = result.index.isin(calendar.index)
    result['is_special_open'] = result.is_special_open.astype('boolean').fillna(False).astype(bool)
    result['first_brt'] = result.first_utc.dt.tz_convert(LOCAL_TIMEZONE).dt.strftime('%H:%M')
    result['last_brt'] = result.last_utc.dt.tz_convert(LOCAL_TIMEZONE).dt.strftime('%H:%M')
    result['minutes_without_candle_between_first_last'] = (
        (result.last_utc - result.first_utc).dt.total_seconds().div(60).astype('int64') + 1 - result.candle_count
    )
    delay = (result.first_utc - result.expected_open_utc).dt.total_seconds().div(60)
    result['open_delay_minutes'] = delay.astype('Int64')
    opens = frame.datetime.eq(dates.map(calendar.expected_open_utc)).groupby(dates).any()
    window_end = dates.map(result.first_utc) + pd.Timedelta(minutes=window_minutes)
    counts = (frame.datetime < window_end).groupby(dates).sum()
    result['has_expected_open'] = opens.reindex(result.index, fill_value=False)
    result['opening_window_observed'] = counts.reindex(result.index, fill_value=0).astype('int64')
    result['opening_window_missing'] = (window_minutes - result.opening_window_observed).astype('Int64')
    result.loc[~result.is_expected_session, 'opening_window_missing'] = pd.NA
    result['opening_window_complete'] = result.is_expected_session & result.opening_window_missing.eq(0)
    # Atraso acima do limite indica dia truncado na fonte, não abertura tardia.
    on_time = result.open_delay_minutes.between(0, max_open_delay_minutes)
    result['eligible_regular_opening'] = result.opening_window_complete & ~result.is_special_open & on_time
    return result


def missing_session_dates(frame: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Separa pregões ausentes dentro do histórico dos limites da fonte."""
    if frame.empty:
        raise ValueError('Sem observações para delimitar a cobertura da fonte.')
    dates = local_dates(frame)
    missing = calendar.loc[~calendar.index.isin(dates.unique())].copy()
    missing['reason'] = 'missing_session_internal'
    missing.loc[missing.index < dates.min(), 'reason'] = 'before_history'
    missing.loc[missing.index > dates.max(), 'reason'] = 'after_history'
    return missing
