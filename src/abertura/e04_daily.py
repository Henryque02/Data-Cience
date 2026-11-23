"""Monta a tabela diária: uma linha por pregão e alvo, com variáveis e rótulos.

Uso: uv run --locked python -m abertura.e04_daily

Lê os Parquets de data/tratamento/ e grava data/processed/daily.parquet; no fim imprime
quantos pregões e rolagens há em cada alvo e a contagem de cada rótulo.

- Para cada alvo (targets em config/params.yaml), resume os pregões e marca as
  rolagens com e02_tratamento.py, e junta as variáveis e os rótulos de e03_feat_labels.py
  (externos de externals; limiar do gap de cada alvo em labels.gap_threshold).
- Todos os dias com dados no período entram, inclusive Cinzas, janelas incompletas e
  rolagens. Só o primeiro dia do histórico de cada alvo não vira linha, porque pode
  começar no meio do pregão; no período, isso tira apenas o WIN de 15/10/2020. Gap e
  rótulos usam os preços disponíveis, sem ajuste de contrato; sem fechamento anterior, o
  gap fica ausente.
- Metadado: is_roll_day identifica rolagens; serve para tirar esses dias de cada modelo
  (na pergunta 1 eles saem do treino e do teste).
- O gap aparece duas vezes, com o mesmo valor: y_gap é a resposta da pergunta 1 (com a
  classe em y_gap_class) e x_open_gap é variável das perguntas 2 e 3, quando o gap já
  aconteceu.
- O calendário cobre os meses inteiros em volta do período de análise (sample), para a
  rolagem do WDO e o pregão anterior ao primeiro dia; a tabela final só guarda os
  pregões entre sample.start e sample.end.

Toda variável passa por build_target: a conferência contra vazamento descrita em
e03_feat_labels.py vale para qualquer mudança aqui.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .e03_feat_labels import (
    external_features, labels, last_price, open_features, opening_window,
    range_labels, session_moments, target_features, without_roll_jumps,
)
from .e02_tratamento import b3_sessions, daily_sessions, roll_dates

PROJECT = Path(__file__).resolve().parents[2]


def build_target(
    asset: str,
    candles: pd.DataFrame,
    externals: dict[str, pd.DataFrame],
    calendar: pd.DataFrame,
    params: dict,
) -> pd.DataFrame:
    """Monta cada dia do alvo, sem excluir pregões nem corrigir rolagens."""
    pre = params['features']['pre_open']
    label = params['labels']
    minutes = label['post_open_minutes']
    sessions = daily_sessions(candles, calendar)
    moments = session_moments(
        sessions, calendar.index, pre['cutoff_brt'], pre['special_cutoff_brt'],
    )
    window = opening_window(candles, sessions, minutes).reindex(sessions.index)
    prev_close = last_price(candles, moments.prev_close_utc)
    roll = sessions.index.isin(roll_dates(asset, calendar.index))
    is_roll = pd.Series(roll, index=sessions.index)
    metadata = pd.DataFrame({'asset': asset, 'is_roll_day': is_roll})
    opening = open_features(window.open, prev_close)
    answers = labels(
        window, prev_close, opening.x_open_gap, label['gap_threshold'][asset],
        label['behavior']['trend_margin'],
    )
    external = [external_features(name, frame, moments, pre) for name, frame in externals.items()]
    table = pd.concat(
        [metadata, target_features(candles, sessions.index), *external,
         opening, answers, range_labels(window)],
        axis=1,
    )
    # O histórico pode começar no meio do pregão (WIN do professor: 15/10/2020, 11:49):
    # o primeiro dia só serve de D-1 para o seguinte e não vira linha.
    return table.drop(index=sessions.index.min())


def build_daily(project_root: str | Path = PROJECT) -> pd.DataFrame:
    """Grava data/processed/daily.parquet com uma linha por pregão e alvo."""
    root = Path(project_root).resolve()
    params = yaml.safe_load((root / 'config/params.yaml').read_text())
    tratamento = root / 'data/tratamento'
    externals = {
        asset_id: pd.read_parquet(tratamento / f'{asset_id}_m1.parquet', columns=['datetime', 'open', 'close'])
        for asset_id in params['externals']
    }
    for asset_id, pauses in params['features']['pre_open']['roll_pause_minutes'].items():
        externals[asset_id] = without_roll_jumps(externals[asset_id], pauses)
    start, end = pd.Timestamp(params['sample']['start']), pd.Timestamp(params['sample']['end'])
    # Meses inteiros: a rolagem do WDO é o último pregão do mês, e o pregão anterior
    # ao primeiro dia precisa existir para o gap. O corte no período vem no final.
    calendar = b3_sessions(start.replace(day=1), end + pd.offsets.MonthEnd(0))
    tables = []
    for asset_id in params['targets']:
        candles = pd.read_parquet(tratamento / f'{asset_id}_m1.parquet')
        tables.append(build_target(asset_id, candles, externals, calendar, params))
    result = pd.concat(tables).rename_axis('date_brt').reset_index()
    result = result[result.date_brt.between(start, end)].reset_index(drop=True)
    output = root / 'data/processed/daily.parquet'
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, engine='pyarrow', index=False)
    return result


def main() -> int:
    """Gera a tabela e resume a amostra de cada alvo."""
    result = build_daily()
    print(result.groupby('asset').is_roll_day.agg(pregoes='size', rolagens='sum').to_string())
    print(result.groupby('asset').y_gap_class.value_counts().to_string())
    print(result.groupby('asset').y_behavior.value_counts().to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
