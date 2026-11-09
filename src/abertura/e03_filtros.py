"""Filtros dos pregões: calendário da B3, pregões elegíveis e dias de rolagem.

Não tem comando próprio: quem chama é o e06_daily.py. Aqui ficam as regras que tiram
dias da amostra ou invalidam o gap.

- b3_sessions monta o calendário oficial BVMF (biblioteca exchange_calendars): os dias
  de pregão, com feriados, e a Quarta-feira de Cinzas, que abre às 13:00. Ele bate com os
  dados nos feriados de São Paulo em que a B3 mudou de regra: houve pregão em 20/11/2020
  e 25/01/2022, não em 09/07/2021.
  
- local_dates diz a que data de Brasília (pregão) pertence cada vela.

- daily_sessions resume cada dia com dados (primeira e última vela, se é pregão, se é a
  Cinzas) e marca os elegíveis: pregão do calendário, fora a Cinzas, que não seja o
  primeiro dia do histórico (o arquivo do professor começa no meio do pregão) e com os
  60 min a partir da primeira vela completos. A janela vem de config/params.yaml. Não há
  limite de atraso da abertura: em 31/07/2026 uma falha da B3 adiou a abertura em mais
  de 2 h, e a janela parte da primeira vela (12:34).

- roll_dates lista os dias de troca de contrato, em que o gap fica vazio porque o salto
  entre contratos não é movimento de mercado. WIN: quarta-feira mais próxima do dia 15
  dos meses pares; se for feriado, o pregão seguinte (12/10/2022 passou para 13/10/2022).
  WDO: último pregão de cada mês, véspera do vencimento; o calendário recebido precisa
  cobrir o mês inteiro, senão o último dia de um mês cortado viraria falsa rolagem. A
  evidência das regras está na seção 2.4 do AGENTS.md.
"""

from __future__ import annotations

import exchange_calendars as xcals
import pandas as pd

LOCAL_TIMEZONE = 'America/Sao_Paulo'


def b3_sessions(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DataFrame:
    """Dias de pregão da B3 entre as datas, com a marcação da Quarta-feira de Cinzas."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    calendar = xcals.get_calendar(
        'BVMF', start=start - pd.Timedelta(days=10), end=end + pd.Timedelta(days=10)
    )
    result = pd.DataFrame(index=calendar.schedule.loc[start:end].index.copy())
    result.index.name = 'date_brt'
    result['is_special_open'] = result.index.isin(calendar.late_opens)
    return result


def local_dates(frame: pd.DataFrame) -> pd.Series:
    """Retorna datas civis brasileiras, mantendo timestamps originais intactos."""
    return frame.datetime.dt.tz_convert(LOCAL_TIMEZONE).dt.tz_localize(None).dt.normalize()


def daily_sessions(
    frame: pd.DataFrame,
    calendar: pd.DataFrame,
    *,
    window_minutes: int,
) -> pd.DataFrame:
    """Resume cada dia com dados; a abertura do dia é o primeiro candle observado."""
    dates = local_dates(frame)
    result = frame.datetime.groupby(dates).agg(first_utc='min', last_utc='max')
    result.index.name = 'date_brt'
    result = result.join(calendar)
    result['is_expected_session'] = result.index.isin(calendar.index)
    result['is_special_open'] = result.is_special_open.astype('boolean').fillna(False).astype(bool)
    # A janela parte do primeiro candle observado, não de 09:00.
    window_end = dates.map(result.first_utc) + pd.Timedelta(minutes=window_minutes)
    in_window = (frame.datetime < window_end).groupby(dates).sum()
    complete = result.is_expected_session & in_window.reindex(result.index).eq(window_minutes)
    # O primeiro dia do histórico pode começar no meio do pregão (professor: WIN às 11:49).
    after_first = result.index > result.index.min()
    result['eligible_regular_opening'] = complete & ~result.is_special_open & after_first
    return result


def _win_roll_dates(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Quarta mais próxima do dia 15 dos meses pares; feriado passa ao pregão seguinte."""
    months = pd.period_range(sessions.min(), sessions.max(), freq='M')
    dates = []
    for month in months[months.month % 2 == 0]:
        day15 = pd.Timestamp(month.year, month.month, 15)
        nearest = day15 + pd.Timedelta(days=(5 - day15.dayofweek) % 7 - 3)
        position = sessions.searchsorted(nearest)
        if sessions.min() <= nearest and position < len(sessions):
            dates.append(sessions[position])
    return pd.DatetimeIndex(dates)


def _wdo_roll_dates(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Último pregão do mês: a série troca de contrato na véspera do vencimento."""
    last = pd.Series(sessions, index=sessions).groupby(sessions.to_period('M')).last()
    return pd.DatetimeIndex(last.to_numpy())


def roll_dates(asset: str, sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Pregões em que o gap do ativo contém a diferença entre contratos."""
    rules = {'win': _win_roll_dates, 'wdo': _wdo_roll_dates}
    return rules[asset](sessions)

