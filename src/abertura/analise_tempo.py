"""Análise exploratória: quanto tempo duram os movimentos depois de um gap.

Uso: uv run --locked python -m abertura.analise_tempo

Não alimenta o modelo; só descreve, para ajudar a decidir a janela de 60 min. Lê
data/processed/daily.parquet (dias elegíveis com gap acima do limiar, os mesmos do
y_behavior) e as velas de data/tratamento/, e imprime um resumo por alvo e direção.

- Minuto 0 é a primeira vela do dia (a abertura); tudo é medido até o fim do pregão.
- Fechamento do gap: primeiro minuto em que o preço toca o fechamento de D-1 (mínima
  abaixo dele no gap de alta, máxima acima no de baixa). Fechar no minuto 0 significa
  fechar dentro da primeira vela, antes da entrada (vela seguinte).
- Pico a favor: o ponto mais longe da abertura na direção do gap (máxima no gap de alta,
  mínima no de baixa) e o minuto em que ele acontece, nos dias em que o gap não fecha.

O fechamento de D-1 é o close da última vela antes da abertura; o gap recalculado com ele
é conferido contra o x_open_gap da tabela diária.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .e03_filtros import local_dates

PROJECT = Path(__file__).resolve().parents[2]
CLOSE_MARKS = [15, 30, 60, 120]


def gap_day_timing(candles: pd.DataFrame, daily: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Uma linha por dia de gap: minuto em que o gap fecha e pico a favor do gap."""
    dates = local_dates(candles)
    days = daily[daily.x_open_gap.abs() > threshold].set_index('date_brt')
    rows = []
    for date, day in candles.groupby(dates):
        if date not in days.index:
            continue
        first = candles.index.get_loc(day.index[0])
        prev_close = candles.close.iat[first - 1]
        opening = day.open.iat[0]
        gap = days.x_open_gap[date]
        if not np.isclose(opening / prev_close - 1, gap, rtol=0, atol=1e-9):
            raise ValueError(f'Gap recalculado difere da tabela diária em {date:%Y-%m-%d}.')
        up = gap > 0
        minutes = (day.datetime - day.datetime.iat[0]).dt.total_seconds().div(60).to_numpy()
        touched = (day.low <= prev_close) if up else (day.high >= prev_close)
        favor = (day.high / opening - 1) if up else (1 - day.low / opening)
        close_minute = minutes[touched.to_numpy().argmax()] if touched.any() else np.nan
        rows.append({
            'date_brt': date,
            'direction': 'alta' if up else 'baixa',
            'close_minute': close_minute,
            'peak_minute': minutes[favor.to_numpy().argmax()],
            'peak_size': favor.max(),
        })
    return pd.DataFrame(rows)


def summarize(timing: pd.DataFrame) -> pd.DataFrame:
    """Resumo por direção: quando o gap fecha e, quando não fecha, onde fica o pico."""
    result = {}
    for direction, group in timing.groupby('direction'):
        closed = group.close_minute
        never = group[closed.isna()]
        summary = {'dias': len(group)}
        summary['% fecha na 1ª vela'] = 100 * closed.eq(0).mean()
        for mark in CLOSE_MARKS:
            # "Nos primeiros 60 min" são os minutos 0 a 59, como a janela do y_behavior.
            summary[f'% fecha nos primeiros {mark} min'] = 100 * closed.lt(mark).mean()
        summary['% fecha no pregão'] = 100 * closed.notna().mean()
        summary['mediana min p/ fechar'] = closed.median()
        summary['não fecha: dias'] = len(never)
        summary['não fecha: pico mediano %'] = 100 * never.peak_size.median()
        summary['não fecha: minuto mediano do pico'] = never.peak_minute.median()
        summary['não fecha: % pico depois dos 60 min'] = 100 * never.peak_minute.ge(60).mean()
        result[direction] = summary
    return pd.DataFrame(result).round(1)


def main() -> int:
    """Imprime o resumo de cada alvo."""
    params = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    threshold = params['labels']['gap_threshold']['value']
    daily = pd.read_parquet(PROJECT / 'data/processed/daily.parquet')
    daily = daily[daily.is_eligible & daily.x_open_gap.notna()]
    for asset in params['targets']:
        candles = pd.read_parquet(PROJECT / 'data/tratamento' / f'{asset}_m1.parquet')
        timing = gap_day_timing(candles, daily[daily.asset == asset], threshold)
        print(f'\n== {asset.upper()} (gap acima de {threshold:.1%})')
        print(summarize(timing).to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
