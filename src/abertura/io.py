"""Leitores M1 com schema único e tratamento explícito dos fusos."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .download import DataValidationError

STANDARD_COLUMNS = ['datetime', 'open', 'high', 'low', 'close', 'volume']
VALUE_COLUMNS = STANDARD_COLUMNS[1:]


def normalize_candles(frame: pd.DataFrame) -> pd.DataFrame:
    """Valida, ordena e remove apenas duplicatas integralmente idênticas."""
    missing = set(STANDARD_COLUMNS) - set(frame.columns)
    if missing or frame.empty:
        raise DataValidationError(f'Dados vazios ou colunas ausentes: {sorted(missing)}')
    result = frame[STANDARD_COLUMNS].copy()
    if not isinstance(result.datetime.dtype, pd.DatetimeTZDtype):
        raise DataValidationError('datetime deve ter fuso explícito antes da normalização.')
    result['datetime'] = result.datetime.dt.tz_convert('UTC').astype('datetime64[ns, UTC]')
    if result.datetime.isna().any() or (result.datetime.astype('int64') % 60_000_000_000 != 0).any():
        raise DataValidationError('Timestamp ausente ou fora da grade M1.')
    try:
        result[VALUE_COLUMNS] = result[VALUE_COLUMNS].apply(pd.to_numeric, errors='raise').astype('float64')
    except (TypeError, ValueError) as exc:
        raise DataValidationError(f'Preço/volume não numérico: {exc}') from exc
    if not np.isfinite(result[VALUE_COLUMNS].to_numpy()).all():
        raise DataValidationError('Preço/volume ausente ou não finito.')
    if (result[['open', 'high', 'low', 'close']] <= 0).any().any() or (result.volume < 0).any():
        raise DataValidationError('Preço não positivo ou volume negativo.')
    if ((result.low > result[['open', 'close']].min(axis=1)) |
        (result.high < result[['open', 'close']].max(axis=1)) |
        (result.low > result.high)).any():
        raise DataValidationError('OHLC inconsistente.')
    duplicates = result[result.duplicated('datetime', keep=False)]
    if not duplicates.empty and duplicates.groupby('datetime')[VALUE_COLUMNS].nunique().gt(1).any().any():
        raise DataValidationError('Candles conflitantes no mesmo timestamp; decidir a fonte antes de continuar.')
    result = result.drop_duplicates().sort_values('datetime', kind='stable').reset_index(drop=True)
    result.attrs = {**frame.attrs, 'source_rows': len(frame), 'duplicates_removed': len(frame) - len(result)}
    return result


def _columns(frame: pd.DataFrame, required: list[str]) -> None:
    """Exige campos reais em vez de criar colunas substitutas."""
    missing = set(required) - set(frame.columns)
    if missing:
        raise DataValidationError(f'Colunas ausentes na fonte: {sorted(missing)}')


def read_dukascopy_csv(path: str | Path) -> pd.DataFrame:
    """Lê epoch em milissegundos UTC e volume original da Dukascopy."""
    frame = pd.read_csv(path, encoding='utf-8-sig')
    _columns(frame, ['timestamp', *VALUE_COLUMNS])
    frame['datetime'] = pd.to_datetime(frame.timestamp, unit='ms', utc=True, errors='raise')
    frame.attrs = {'source': 'dukascopy', 'source_timezone': 'UTC', 'volume_column': 'volume'}
    return normalize_candles(frame)


def read_mt5_csv(
    path: str | Path,
    timezone: str = 'America/Sao_Paulo',
    *,
    volume_column: str = '<VOL>',
) -> pd.DataFrame:
    """Lê exportação TAB do terminal; o fuso do CSV é um parâmetro."""
    frame = pd.read_csv(path, sep='\t', encoding='utf-8-sig')
    _columns(frame, ['<DATE>', '<TIME>', '<OPEN>', '<HIGH>', '<LOW>', '<CLOSE>', volume_column])
    local = pd.to_datetime(frame['<DATE>'] + ' ' + frame['<TIME>'], format='%Y.%m.%d %H:%M:%S', errors='raise')
    frame['datetime'] = local.dt.tz_localize(timezone, ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    frame = frame.rename(columns={'<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low',
                                  '<CLOSE>': 'close', volume_column: 'volume'})
    frame.attrs = {'source': 'mt5_csv', 'source_timezone': timezone, 'volume_column': volume_column}
    return normalize_candles(frame)


def read_mt5_api_csv(path: str | Path, *, volume_column: str = 'real_volume') -> pd.DataFrame:
    """Lê copy_rates_range exportado: epoch segundos já está em UTC."""
    frame = pd.read_csv(path, encoding='utf-8-sig')
    _columns(frame, ['time', 'open', 'high', 'low', 'close', volume_column])
    frame['datetime'] = pd.to_datetime(frame.time, unit='s', utc=True, errors='raise')
    frame = frame.rename(columns={volume_column: 'volume'})
    frame.attrs = {'source': 'mt5_api', 'source_timezone': 'UTC', 'volume_column': volume_column}
    return normalize_candles(frame)
