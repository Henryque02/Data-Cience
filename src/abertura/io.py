"""Leitores M1 com schema único e tratamento explícito dos fusos.

Este projeto não tem testes automatizados. O pior erro aqui não dá aviso: o horário de todos os
candles fica deslocado em algumas horas (ou o volume vem de outra coluna), e o resto do pipeline
roda normalmente. Janelas pré-abertura e a primeira linha do pregão passam a apontar para o
horário errado. Ao alterar este módulo, confira as garantias abaixo.

FUSO (a regra mais importante)

- CSV exportado pelo terminal MT5 (read_mt5_csv): sem fuso no arquivo. O fuso é um PARÂMETRO,
  padrão America/Sao_Paulo.
- API do MT5 (read_mt5_api_csv, epoch em segundos) e Dukascopy (read_dukascopy_csv, epoch em
  milissegundos): já são UTC. Nunca aplicar fuso nestes dois.
- Aplicar o fuso duas vezes desloca todos os candles. Exemplo: o candle da API 1602773340 é
  2020-10-15 14:49 UTC. Tratado como Brasília, viraria 17:49 UTC, 3 h depois.
- A saída é sempre `datetime64[ns, UTC]`. Brasília só serve para exibir.

LEITORES

- read_mt5_csv: `2020.10.15 11:49:00` em Brasília vira 2020-10-15 14:49 UTC. Com
  timezone='UTC' o mesmo texto vira 11:49 UTC, 3 h antes. Fuso ambíguo ou inexistente levanta
  erro, em vez de adivinhar.
- Volume do MT5 é a coluna <VOL> (real), nunca <TICKVOL>. No primeiro candle do WIN de exemplo
  são 9001 contra 2373 ticks. Sem a coluna, levanta DataValidationError: nada de trocar por
  tick. attrs['volume_column'] guarda '<VOL>'. Na API, a coluna é real_volume.
- Preço decimal é preservado: o primeiro WDO de exemplo abre em 5248,5, com volume 10451.
  As colunas open, high, low, close e volume saem como float64.
- Dukascopy: o 1º candle de exemplo (1793232000000) é 2026-10-29 00:00 UTC, que em Brasília é
  dia 28 às 21:00. Agrupar por data UTC e por data de Brasília dá dias diferentes. Volume da
  Dukascopy é de tick (0,02728 no exemplo), não é volume real.
- Arquivo só com cabeçalho levanta DataValidationError.

NORMALIZAÇÃO (normalize_candles)

- Ordena por tempo e remove só duplicata idêntica. Com 3 candles e linhas [1, 0, 0, 2], saem 3
  linhas, ordenadas e únicas, com attrs source_rows = 4 e duplicates_removed = 1.
- Mesmo timestamp com close (ex.: 7719,676 contra 7719,675) ou volume diferentes levanta
  DataValidationError. Escolher a fonte é decisão humana.
- Nada é consertado. Cada um destes casos levanta DataValidationError: close nan, volume
  negativo, high menor que open/close (high = 1), low maior que open/close (low = 10000) e open
  zero.
- datetime sem fuso, ou com segundos (00:00:01), levanta DataValidationError.
"""

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
    # Milissegundos (não segundos), já em UTC.
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
    # Único ponto que aplica fuso. API e Dukascopy já vêm em UTC: aplicar de novo desloca tudo.
    frame['datetime'] = local.dt.tz_localize(timezone, ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    frame = frame.rename(columns={'<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low',
                                  '<CLOSE>': 'close', volume_column: 'volume'})
    frame.attrs = {'source': 'mt5_csv', 'source_timezone': timezone, 'volume_column': volume_column}
    return normalize_candles(frame)


def read_mt5_api_csv(path: str | Path, *, volume_column: str = 'real_volume') -> pd.DataFrame:
    """Lê copy_rates_range exportado: epoch segundos já está em UTC."""
    frame = pd.read_csv(path, encoding='utf-8-sig')
    _columns(frame, ['time', 'open', 'high', 'low', 'close', volume_column])
    # Segundos, já em UTC: sem tz_localize (ver read_mt5_csv).
    frame['datetime'] = pd.to_datetime(frame.time, unit='s', utc=True, errors='raise')
    frame = frame.rename(columns={volume_column: 'volume'})
    frame.attrs = {'source': 'mt5_api', 'source_timezone': 'UTC', 'volume_column': volume_column}
    return normalize_candles(frame)
