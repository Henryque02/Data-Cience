"""Diagnósticos distinguem calendário, horário especial e ausência de candles."""

import pandas as pd

from abertura.sessions import b3_sessions, daily_sessions, missing_session_dates
from abertura.quality import candle_gaps, cutoff_staleness, late_opens_by_quarter, missing_runs


def candles(start, periods, tz='America/Sao_Paulo'):
    """Cria apenas timestamps controlados para os testes de calendário."""
    return pd.DataFrame({'datetime': pd.date_range(start, periods=periods, freq='min', tz=tz).tz_convert('UTC')})


def test_calendar_respects_historical_holiday_changes_and_ash_wednesday():
    assert pd.Timestamp('2020-11-20') in b3_sessions('2020-11-19', '2020-11-23').index
    assert pd.Timestamp('2021-07-09') not in b3_sessions('2021-07-08', '2021-07-12').index
    assert pd.Timestamp('2022-01-25') in b3_sessions('2022-01-24', '2022-01-26').index
    schedule = b3_sessions('2026-02-16', '2026-02-19')
    assert pd.Timestamp('2026-02-16') not in schedule.index
    assert pd.Timestamp('2026-02-17') not in schedule.index
    assert schedule.loc['2026-02-18', 'is_special_open']
    assert schedule.loc['2026-02-18', 'expected_open_utc'] == pd.Timestamp('2026-02-18T16:00:00Z')
    assert schedule.loc['2026-02-19', 'expected_open_utc'] == pd.Timestamp('2026-02-19T12:00:00Z')


def test_daily_sessions_detects_missing_open_without_fixed_close():
    frame = pd.concat([candles('2026-03-10 09:00', 60), candles('2026-03-11 09:01', 59)], ignore_index=True)
    result = daily_sessions(frame)
    assert result.loc['2026-03-10', 'opening_window_missing'] == 0
    assert result.loc['2026-03-10', 'eligible_regular_opening']
    assert result.loc['2026-03-10', 'last_brt'] == '09:59'
    assert result.loc['2026-03-11', 'opening_window_missing'] == 1
    assert not result.loc['2026-03-11', 'has_expected_open']
    assert not result.loc['2026-03-11', 'eligible_regular_opening']


def test_late_first_candle_anchors_window_and_stays_eligible():
    result = daily_sessions(candles('2026-03-10 09:03', 90))
    assert result.loc['2026-03-10', 'open_delay_minutes'] == 3
    assert not result.loc['2026-03-10', 'has_expected_open']
    assert result.loc['2026-03-10', 'opening_window_observed'] == 60
    assert result.loc['2026-03-10', 'opening_window_missing'] == 0
    assert result.loc['2026-03-10', 'eligible_regular_opening']


def test_open_at_delay_limit_stays_eligible():
    result = daily_sessions(candles('2026-03-10 09:15', 60), max_open_delay_minutes=15)
    assert result.loc['2026-03-10', 'eligible_regular_opening']


def test_open_after_delay_limit_is_not_eligible():
    result = daily_sessions(candles('2026-03-10 09:16', 60), max_open_delay_minutes=15)
    assert result.loc['2026-03-10', 'opening_window_missing'] == 0
    assert not result.loc['2026-03-10', 'eligible_regular_opening']


def test_first_candle_before_reference_is_not_eligible():
    result = daily_sessions(candles('2026-03-10 08:59', 60))
    assert result.loc['2026-03-10', 'open_delay_minutes'] == -1
    assert not result.loc['2026-03-10', 'eligible_regular_opening']


def test_hole_after_late_open_removes_day():
    frame = candles('2026-03-10 09:03', 60).drop(index=10).reset_index(drop=True)
    result = daily_sessions(frame)
    assert result.loc['2026-03-10', 'opening_window_missing'] == 1
    assert not result.loc['2026-03-10', 'eligible_regular_opening']


def test_ash_wednesday_is_not_flagged_missing_0900():
    result = daily_sessions(candles('2026-02-18 13:00', 60))
    assert result.loc['2026-02-18', 'has_expected_open']
    assert result.loc['2026-02-18', 'opening_window_missing'] == 0
    assert not result.loc['2026-02-18', 'eligible_regular_opening']


def test_missing_dates_separates_internal_holes_from_outside_history():
    schedule = b3_sessions('2026-03-09', '2026-03-13')
    frame = pd.concat([candles('2026-03-10 09:00', 2), candles('2026-03-12 09:00', 2)], ignore_index=True)
    result = missing_session_dates(frame, schedule)
    assert result.loc['2026-03-09', 'reason'] == 'before_history'
    assert result.loc['2026-03-11', 'reason'] == 'missing_session_internal'
    assert result.loc['2026-03-13', 'reason'] == 'after_history'


def test_weekend_and_holiday_are_not_missing_sessions():
    schedule = b3_sessions('2026-09-04', '2026-09-08')
    frame = pd.concat([candles('2026-09-04 09:00', 2), candles('2026-09-08 09:00', 2)], ignore_index=True)
    assert missing_session_dates(frame, schedule).empty
    gaps = candle_gaps(frame, min_missing_minutes=1, calendar=schedule)
    assert len(gaps) == 1
    assert gaps.iloc[0]['classification'] == 'between_sessions'


def test_intraday_gap_counts_missing_minutes_without_filling():
    frame = candles('2026-03-10 09:00', 5).drop(index=2).reset_index(drop=True)
    result = candle_gaps(frame, min_missing_minutes=1, calendar=b3_sessions('2026-03-10', '2026-03-10'))
    assert len(result) == 1
    assert result.iloc[0].missing_minutes == 1
    assert result.iloc[0].classification == 'intraday_investigate'
    assert len(frame) == 4


def test_missing_runs_join_consecutive_sessions_across_weekend():
    schedule = b3_sessions('2026-03-05', '2026-03-10')
    missing = schedule.loc[['2026-03-06', '2026-03-09']].copy()
    missing['reason'] = 'missing_session_internal'
    runs = missing_runs(missing, schedule)
    assert len(runs) == 1
    assert runs.iloc[0].missing_sessions == 2
    assert runs.iloc[0].first_date == pd.Timestamp('2026-03-06')
    assert runs.iloc[0].last_date == pd.Timestamp('2026-03-09')


def test_external_gap_is_not_claimed_as_confirmed_failure():
    frame = candles('2026-03-10 09:00', 5).drop(index=2).reset_index(drop=True)
    result = candle_gaps(frame, min_missing_minutes=1)
    assert result.iloc[0].classification == 'intraday_without_source_calendar'


def test_observation_outside_calendar_is_flagged_without_claiming_regular_open():
    result = daily_sessions(candles('2026-03-14 09:00', 2))
    assert not result.iloc[0].is_expected_session
    assert pd.isna(result.iloc[0].opening_window_missing)
    assert pd.isna(result.iloc[0].open_delay_minutes)
    assert not result.iloc[0].eligible_regular_opening


def test_late_opens_by_quarter_ignores_special_and_outside_calendar_days():
    frame = pd.concat([
        candles('2026-02-18 13:00', 2),  # Cinzas: referência própria, fora da conta.
        candles('2026-03-10 09:00', 2),
        candles('2026-03-11 09:03', 2),
        candles('2026-03-14 09:03', 2),  # Sábado: fora do calendário.
        candles('2026-04-07 09:00', 2),
    ], ignore_index=True)
    result = late_opens_by_quarter(daily_sessions(frame))
    assert result.loc['2026Q1'].to_dict() == {'pregoes': 2, 'com_atraso': 1, 'pct': 50.0}
    assert result.loc['2026Q2'].to_dict() == {'pregoes': 1, 'com_atraso': 0, 'pct': 0.0}


def test_cutoff_staleness_idade_em_minutos():
    times = pd.Series(pd.to_datetime(['2024-01-02 10:00', '2024-01-02 10:10'], utc=True))
    cutoffs = pd.Series(pd.to_datetime(
        ['2024-01-02 10:10', '2024-01-02 10:07', '2024-01-02 10:09', '2024-01-02 09:00'], utc=True))
    result = cutoff_staleness(times, cutoffs)
    assert result.iloc[0] == 0  # candle exatamente no corte
    assert result.iloc[1] == 7  # candle anterior
    assert result.iloc[2] == 9  # candle posterior (10:10) ignorado
    assert pd.isna(result.iloc[3])  # sem candle anterior
