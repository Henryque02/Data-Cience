"""Datas de troca de contrato nas séries contínuas de WIN e WDO.

Este projeto não tem testes automatizados. Em dia de rolagem, o gap contém a
diferença de preço entre dois contratos. Uma data errada deixa um gap falso
entrar em x_open_ e nos rótulos, sem erro nenhum. Ao alterar este módulo, ou ao
trocar a fonte de WIN e WDO, confira:

- WIN: quarta mais próxima do dia 15 dos meses pares. Em 2025, isso dá 02-12,
  04-16, 06-18, 08-13, 10-15 e 12-17.
- Feriado passa a troca ao pregão seguinte: 2022-10-12 vira 2022-10-13.
- WDO: último pregão do mês, um pregão antes do vencimento. No 1º trimestre de
  2026, isso dá 01-30, 02-27 e 03-31.
- Ativo sem regra levanta ValueError. Devolver lista vazia esconderia gaps falsos.
- O calendário precisa cobrir o mês inteiro: `_wdo_roll_dates` trata o último
  pregão recebido como fim de mês. Com dados até o meio do mês, esse dia seria
  marcado como rolagem por engano.
- gap_event_study: com fechamentos 100 e aberturas 110 e 95 nos dois pregões
  seguintes, os gaps são +10% e -5%. Pregão anterior ausente não gera gap.

Conferência nos dados: no notebook 02, `gap_event_study` precisa mostrar o pico só
no offset 0, com cerca de +1,6% e 100% de dias positivos no WIN, e +0,44% e 87% no
WDO. Pico em outro offset indica que a regra não vale para aquela série.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .sessions import local_dates


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
    if asset not in rules:
        raise ValueError(f'Ativo sem regra de rolagem: {asset}')
    return rules[asset](sessions)


def gap_event_study(
    candles: pd.DataFrame, calendar: pd.DatetimeIndex, rolls: pd.DatetimeIndex, span: int = 3,
) -> pd.DataFrame:
    """Gap bruto médio (%) nos pregões ao redor de cada rolagem, de -span a +span."""
    day = candles.assign(date=local_dates(candles)).sort_values('datetime').groupby('date')
    first_open, last_close = day.open.first(), day.close.last()
    previous = last_close.reindex(calendar).shift(1)  # fechamento do pregão anterior do calendário
    gaps = (first_open.reindex(calendar) / previous - 1).to_numpy()
    rows = []
    for offset in range(-span, span + 1):
        positions = [calendar.get_loc(roll) + offset for roll in rolls if roll in calendar]
        values = pd.Series([gaps[i] for i in positions if 0 <= i < len(calendar)], dtype=float).dropna()
        rows.append({'offset': offset, 'n': len(values),
                     'media_pct': values.mean() * 100 if len(values) else np.nan,
                     'positivos_pct': (values > 0).mean() * 100 if len(values) else np.nan})
    return pd.DataFrame(rows)
