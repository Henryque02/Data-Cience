"""Monta a tabela diária: uma linha por pregão e alvo, com variáveis e rótulos.

Uso: uv run --locked python -m abertura.e06_daily

Lê os Parquets de data/tratamento/ e grava data/processed/daily.parquet; no fim imprime
quantos pregões são elegíveis e a contagem de cada rótulo.

- Para cada alvo (targets em config/params.yaml), resume os pregões e marca as
  rolagens com e03_filtros.py, e junta as variáveis de e04_features.py (externos de
  externals) e os rótulos de e05_labels.py.
- Metadados: is_roll_day, is_eligible e has_gap_in_data (sem fechamento de D-1). O gap
  e os rótulos só existem nos pregões elegíveis; em dia de rolagem o gap fica vazio.
- O calendário cobre os meses inteiros em volta do período de análise (sample), para a
  rolagem do WDO e o pregão anterior ao primeiro dia; a tabela final só guarda os
  pregões entre sample.start e sample.end.

Toda variável passa por build_target: a conferência contra vazamento descrita em
e04_features.py vale para qualquer mudança aqui.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .e04_features import external_features, last_price, open_features, session_moments, target_features
from .e05_labels import behavior, opening_window, range_labels
from .e03_filtros import b3_sessions, daily_sessions, roll_dates

PROJECT = Path(__file__).resolve().parents[2]


def build_target(
    asset: str,
    candles: pd.DataFrame,
    externals: dict[str, pd.DataFrame],
    calendar: pd.DataFrame,
    params: dict,
) -> pd.DataFrame:
    """Monta uma linha por pregão do alvo; gap e rótulos só existem nos dias elegíveis."""
    pre = params['features']['pre_open']
    label = params['labels']
    minutes = label['post_open_minutes']
    sessions = daily_sessions(
        candles,
        calendar,
        window_minutes=minutes,
    )
    sessions = sessions[sessions.is_expected_session]
    moments = session_moments(sessions, calendar.index, pre['cutoff_brt'])
    window = opening_window(candles, sessions, minutes).reindex(sessions.index)
    prev_close = last_price(candles, moments.prev_close_utc, 0)
    eligible = sessions.eligible_regular_opening.astype(bool)
    roll = sessions.index.isin(roll_dates(asset, calendar.index))
    is_roll = pd.Series(roll, index=sessions.index)
    metadata = _metadata(asset, is_roll, eligible, prev_close)
    opening = open_features(window.open, prev_close, is_roll).where(eligible)
    labels = _labels(window, prev_close, opening.x_open_gap, label)
    external = [external_features(name, frame, moments, pre) for name, frame in externals.items()]
    return pd.concat(
        [metadata, target_features(candles, sessions.index), *external, opening,
         labels, range_labels(window).where(eligible)],
        axis=1,
    )


def _metadata(
    asset: str, is_roll: pd.Series, eligible: pd.Series, prev_close: pd.Series,
) -> pd.DataFrame:
    """Identifica rolagens, pregões elegíveis e ausência do fechamento anterior."""
    return pd.DataFrame(
        {
            'asset': asset,
            'is_roll_day': is_roll,
            'is_eligible': eligible,
            'has_gap_in_data': prev_close.isna(),
        },
        index=is_roll.index,
    )


def _labels(
    window: pd.DataFrame, prev_close: pd.Series, gap: pd.Series, settings: dict,
) -> pd.DataFrame:
    """Comportamento na janela de abertura, só nos dias de gap."""
    threshold = settings['gap_threshold']['value']
    margin = settings['behavior']['trend_margin']
    return pd.DataFrame({'y_behavior': behavior(window, prev_close, gap, threshold, margin)})


def build_daily(project_root: str | Path = PROJECT) -> pd.DataFrame:
    """Grava data/processed/daily.parquet com uma linha por pregão e alvo."""
    root = Path(project_root).resolve()
    params = yaml.safe_load((root / 'config/params.yaml').read_text())
    tratamento = root / 'data/tratamento'
    externals = {
        asset_id: pd.read_parquet(tratamento / f'{asset_id}_m1.parquet', columns=['datetime', 'open', 'close'])
        for asset_id in params['externals']
    }
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
    print(result.groupby('asset')[['is_eligible', 'is_roll_day']].sum().to_string())
    print(result.groupby('asset').y_behavior.value_counts().to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
