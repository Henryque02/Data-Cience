"""Tabela diária por alvo: metadados, variáveis e rótulos.

Este projeto não tem testes automatizados. Toda variável passa por `build_target`,
então as verificações de vazamento descritas em `features.py` se aplicam a qualquer
mudança aqui. Além delas, garanta que: x_open_ e y_ só existem em pregões elegíveis;
dia de rolagem ou sem pregão anterior nos dados não tem gap; e x_pre_ nunca recebe
dados do dia D do alvo.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .clean import roll_dates
from .download import PROJECT
from .features import external_features, last_price, open_features, session_moments, target_features
from .labels import behavior, gap_class, opening_window, range_labels
from .sessions import LOCAL_TIMEZONE, b3_sessions, daily_sessions


def build_target(
    asset: str,
    candles: pd.DataFrame,
    externals: dict[str, pd.DataFrame],
    calendar: pd.DataFrame,
    params: dict,
) -> pd.DataFrame:
    """Monta uma linha por pregão do alvo; gap e rótulos só existem nos dias elegíveis."""
    pre, label = params['features']['pre_open'], params['labels']
    minutes = label['post_open_minutes']
    sessions = daily_sessions(candles, calendar, window_minutes=minutes,
                              max_open_delay_minutes=params['sample']['max_open_delay_minutes'])
    sessions = sessions[sessions.is_expected_session]
    moments = session_moments(sessions, calendar.index, pre['cutoff_brt'])
    window = opening_window(candles, sessions, minutes).reindex(sessions.index)
    prev_close = last_price(candles, moments.prev_close_utc, 0)
    eligible = sessions.eligible_regular_opening.astype(bool)
    is_roll = pd.Series(sessions.index.isin(roll_dates(asset, calendar.index)), index=sessions.index)
    metadata = pd.DataFrame({'asset': asset, 'is_roll_day': is_roll, 'is_eligible': eligible,
                             'has_gap_in_data': prev_close.isna()}, index=sessions.index)
    opening = open_features(window.open, prev_close, is_roll).where(eligible)
    classes = gap_class(opening.x_open_gap, label['gap_threshold']['value'])
    labels = pd.DataFrame({'y_gap_class': classes,
                           'y_behavior': behavior(window, prev_close, classes, label['behavior']['trend_margin'])})
    external = [external_features(name, frame, moments, pre) for name, frame in externals.items()]
    return pd.concat([metadata, target_features(candles, sessions.index), *external, opening,
                      labels, range_labels(window).where(eligible)], axis=1)


def build_daily(project_root: str | Path = PROJECT) -> pd.DataFrame:
    """Grava data/processed/daily.parquet com uma linha por pregão e alvo."""
    root = Path(project_root).resolve()
    params = yaml.safe_load((root / 'config/params.yaml').read_text())
    config = yaml.safe_load((root / 'config/assets.yaml').read_text())
    interim = root / 'data/interim'
    externals = {asset_id: pd.read_parquet(interim / f'{asset_id}_m1.parquet', columns=['datetime', 'close'])
                 for asset_id, asset in config['assets'].items() if asset['source'] == 'dukascopy'}
    last = max(frame.datetime.iloc[-1] for frame in externals.values())
    calendar = b3_sessions(config['period']['start'], last.tz_convert(LOCAL_TIMEZONE).tz_localize(None).normalize())
    tables = []
    for asset_id, asset in config['assets'].items():
        if asset['source'] != 'dukascopy':
            candles = pd.read_parquet(interim / f'{asset_id}_m1.parquet')
            tables.append(build_target(asset_id, candles, externals, calendar, params))
    result = pd.concat(tables).rename_axis('date_brt').reset_index()
    output = root / 'data/processed/daily.parquet'
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, engine='pyarrow', index=False)
    return result


def main() -> int:
    """Gera a tabela e resume a amostra de cada alvo."""
    result = build_daily()
    print(result.groupby('asset')[['is_eligible', 'is_roll_day']].sum().to_string())
    print(result.groupby('asset').y_gap_class.value_counts().to_string())
    print(result.groupby('asset').y_behavior.value_counts().to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
