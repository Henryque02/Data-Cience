"""Datas de referência B3 e horários efetivamente observados nos futuros.

Este projeto não tem testes automatizados. Um erro aqui decide quais dias entram na amostra e
onde começa a janela pós-abertura. Se o calendário ou a regra da abertura errar, dias truncados
passam como válidos, ou dias bons saem da amostra, sem erro nenhum. Ao alterar este módulo,
confira as garantias abaixo.

CALENDÁRIO (b3_sessions)

- Segue o calendário BVMF, com os feriados da época. Existem como pregão 2020-11-20 e 2022-01-25.
  Não existe 2021-07-09.
- Quarta-feira de Cinzas é pregão especial (is_special_open = True), e a abertura esperada é às
  13:00 de Brasília. Em 2026, segunda 02-16 e terça 02-17 (Carnaval) não são pregão. Quarta
  02-18 abre às 16:00 UTC. Quinta 02-19 abre às 12:00 UTC (09:00 de Brasília).
- A abertura esperada de um dia regular é 09:00 BRT convertida para UTC, não 09:00 UTC.

ABERTURA PELO PRIMEIRO CANDLE (daily_sessions)

- A abertura do dia é o primeiro candle observado. Nenhum horário de fechamento é fixo: last_brt
  vem dos dados. Com 60 candles a partir de 09:00, last_brt = '09:59'.
- A janela pós-abertura conta a partir do primeiro candle, não de 09:00. Com o primeiro candle
  às 09:03 e 90 candles: open_delay_minutes = 3, has_expected_open = False,
  opening_window_observed = 60, opening_window_missing = 0 e o dia é elegível.
- O atraso máximo vale por limite fechado: com max_open_delay_minutes = 15, abrir às 09:15 é
  elegível e abrir às 09:16 não é. Nos dois casos opening_window_missing = 0. Atraso grande
  indica dia truncado na fonte, não abertura tardia.
- Primeiro candle antes da referência (08:59) dá open_delay_minutes = -1. O dia não é
  elegível.
- Falta de minuto dentro da janela tira o dia: 60 candles a partir de 09:03, com o 11º removido,
  dá opening_window_missing = 1. Dia que acaba antes de completar a janela também sai: abrir às
  09:01 e ter só 59 candles (último às 09:59) dá opening_window_missing = 1.
- Quarta-feira de Cinzas, com primeiro candle às 13:00, não é marcada como "sem 09:00":
  has_expected_open = True e opening_window_missing = 0. Mesmo assim eligible_regular_opening
  = False, porque o dia especial sai da amostra.
- Dia fora do calendário (sábado 2026-03-14, por exemplo): is_expected_session = False,
  opening_window_missing e open_delay_minutes ficam ausentes (NA), e o dia não é elegível.
  Nunca declarar abertura regular nesse dia.

PREGÕES AUSENTES (missing_session_dates)

- Separa três motivos: 'before_history' (antes do 1º dado), 'missing_session_internal' (buraco
  no meio) e 'after_history' (depois do último dado). Com dados em 03-10 e 03-12, a ausência de
  03-09 é before_history, a de 03-11 é missing_session_internal e a de 03-13 é after_history.
- Fim de semana e feriado não são pregão ausente. Com dados em sexta 2026-09-04 e terça
  2026-09-08 (segunda 09-07 é feriado), a tabela de ausentes sai vazia.
"""

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
    # 09h de Brasília convertidas para UTC (muda se o fuso for tratado como UTC).
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
    # A janela parte do primeiro candle observado, não de 09:00.
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
