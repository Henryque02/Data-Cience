"""Rótulos do pregão; usam dados futuros por definição e ficam em colunas y_.

Este projeto não tem testes automatizados. Rótulo errado não gera erro: o modelo
apenas aprende a resposta errada. Ao alterar este módulo, confira os exemplos
abaixo à mão. As definições vêm da seção 5 do AGENTS.md.

- Rótulos nunca entram como variável. `models.check_features` bloqueia isso.
- opening_window: começa no primeiro candle observado, não às 09:00. Com primeiro
  candle às 09:03 e janela de 4 minutos, vai de 09:03 a 09:06; o candle das 09:07
  fica fora, mesmo que tenha máxima ou mínima extrema.
- gap_class: a comparação é estrita. Com limite de 0,3%, gap de 0,4% é alta, de
  -0,4% é baixa, e de exatamente 0,3% ou -0,3% é normal. Gap ausente continua
  ausente, nunca vira normal.
- range_labels: abertura 100, máxima 102 e mínima 99 dão +2% e -1%.

behavior, com fechamento anterior 100 e margem de 0,1%:

    Gap de alta, abertura 101      Mínima   Fecha    Rótulo
    Toca o fechamento anterior     99,9     102      reversão (tem prioridade)
    Toca exatamente                100      101,5    reversão
    Segue além da margem           100,5    102      tendência
    Sobe menos que a margem        100,5    101,05   lateral
    Cai sem fechar o gap           100,5    100,2    lateral

    Gap de baixa, abertura 99      Máxima   Fecha    Rótulo
    Toca o fechamento anterior     100,1    98,5     reversão
    Segue além da margem           99,5     98,5     tendência
    Cai menos que a margem         99,5     98,95    lateral

Gap normal ou ausente não tem rótulo de comportamento: sem gap relevante não há
direção a seguir nem gap a fechar.
"""

from __future__ import annotations

import pandas as pd

from .sessions import local_dates


def opening_window(candles: pd.DataFrame, sessions: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Resume cada pregão na janela que começa no primeiro candle observado."""
    dates = local_dates(candles)
    inside = candles.datetime < dates.map(sessions.first_utc) + pd.Timedelta(minutes=minutes)
    return candles[inside].groupby(dates[inside]).agg(
        open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))


def gap_class(gap: pd.Series, threshold: float) -> pd.Series:
    """Classifica o gap; sem gap válido o rótulo fica ausente."""
    labels = pd.Series('normal', index=gap.index, dtype='object')
    labels[gap > threshold] = 'alta'
    labels[gap < -threshold] = 'baixa'
    return labels.where(gap.notna())


def behavior(window: pd.DataFrame, prev_close: pd.Series, classes: pd.Series, trend_margin: float) -> pd.Series:
    """Só existe em dia com gap relevante; reversão tem prioridade sobre tendência."""
    up, down = classes.eq('alta'), classes.eq('baixa')
    move = window.close / window.open - 1
    aligned_move = move.where(up, -move)
    touched = (up & window.low.le(prev_close)) | (down & window.high.ge(prev_close))
    labels = pd.Series('lateral', index=window.index, dtype='object')
    labels[aligned_move > trend_margin] = 'tendencia'
    # A ordem define a prioridade: inverter estas linhas muda o rótulo de dias que fazem os dois.
    labels[touched] = 'reversao'
    return labels.where(up | down)


def range_labels(window: pd.DataFrame) -> pd.DataFrame:
    """Máxima e mínima da janela relativas à abertura."""
    return pd.DataFrame({'y_range_high': window.high / window.open - 1,
                         'y_range_low': window.low / window.open - 1})
