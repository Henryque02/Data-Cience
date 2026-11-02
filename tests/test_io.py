"""Contratos de tempo, preços e volume dos três formatos de entrada."""

from pathlib import Path

import pandas as pd
import pytest

from abertura.download import DataValidationError
from abertura.io import normalize_candles, read_dukascopy_csv, read_mt5_api_csv, read_mt5_csv

FIXTURES = Path(__file__).parent / 'fixtures'
STANDARD = ['datetime', 'open', 'high', 'low', 'close', 'volume']


def test_professor_local_time_is_converted_to_utc_and_real_volume():
    frame = read_mt5_csv(FIXTURES / 'mt5_win.tsv')
    assert list(frame) == STANDARD
    assert str(frame.datetime.dtype) == 'datetime64[ns, UTC]'
    assert frame.datetime.iloc[0] == pd.Timestamp('2020-10-15T14:49:00Z')
    assert frame.volume.iloc[0] == 9001
    assert frame.attrs['volume_column'] == '<VOL>'
    assert frame[STANDARD[1:]].dtypes.eq('float64').all()


def test_mt5_timezone_is_explicitly_configurable():
    frame = read_mt5_csv(FIXTURES / 'mt5_win.tsv', timezone='UTC')
    assert frame.datetime.iloc[0] == pd.Timestamp('2020-10-15T11:49:00Z')


def test_wdo_decimal_prices_are_preserved():
    frame = read_mt5_csv(FIXTURES / 'mt5_wdo.tsv')
    assert frame.open.iloc[0] == 5248.5
    assert frame.volume.iloc[0] == 10451


def test_api_seconds_are_utc_without_brazil_shift():
    frame = read_mt5_api_csv(FIXTURES / 'mt5_api.csv')
    assert frame.datetime.iloc[0] == pd.Timestamp('2020-10-15T14:49:00Z')
    assert frame.volume.iloc[0] == 9001
    assert frame.attrs['volume_column'] == 'real_volume'


def test_dukascopy_milliseconds_are_utc_across_local_midnight():
    frame = read_dukascopy_csv(FIXTURES / 'dukascopy_m1.csv')
    assert frame.datetime.iloc[0] == pd.Timestamp('2026-10-29T00:00:00Z')
    assert frame.datetime.dt.tz_convert('America/Sao_Paulo').iloc[0].day == 28
    assert frame.volume.iloc[0] == pytest.approx(0.02728)


def test_normalization_sorts_and_removes_only_identical_duplicates():
    original = read_dukascopy_csv(FIXTURES / 'dukascopy_m1.csv')
    messy = original.iloc[[1, 0, 0, 2]].copy()
    result = normalize_candles(messy)
    assert len(result) == 3
    assert result.datetime.is_monotonic_increasing
    assert result.datetime.is_unique
    assert result.attrs['source_rows'] == 4
    assert result.attrs['duplicates_removed'] == 1


@pytest.mark.parametrize('column,value', [('close', 7719.676), ('volume', 0.1)])
def test_conflicting_duplicate_prices_or_volume_are_rejected(column, value):
    original = read_dukascopy_csv(FIXTURES / 'dukascopy_m1.csv')
    duplicate = original.iloc[[0]].copy()
    duplicate[column] = value
    with pytest.raises(DataValidationError):
        normalize_candles(pd.concat([original, duplicate], ignore_index=True))


@pytest.mark.parametrize('column,value', [('close', float('nan')), ('volume', -1),
                                         ('high', 1), ('low', 10000), ('open', 0)])
def test_invalid_prices_and_volume_are_not_repaired(column, value):
    frame = read_dukascopy_csv(FIXTURES / 'dukascopy_m1.csv')
    frame.loc[0, column] = value
    with pytest.raises(DataValidationError):
        normalize_candles(frame)


def test_naive_datetime_and_subminute_timestamp_are_rejected():
    frame = read_dukascopy_csv(FIXTURES / 'dukascopy_m1.csv')
    naive = frame.copy()
    naive['datetime'] = naive.datetime.dt.tz_localize(None)
    with pytest.raises(DataValidationError):
        normalize_candles(naive)
    frame.loc[0, 'datetime'] = pd.Timestamp('2026-10-29T00:00:01Z')
    with pytest.raises(DataValidationError):
        normalize_candles(frame)


def test_missing_real_volume_is_not_silently_replaced_by_ticks(tmp_path):
    raw = pd.read_csv(FIXTURES / 'mt5_win.tsv', sep='\t').drop(columns='<VOL>')
    path = tmp_path / 'no_real_volume.tsv'
    raw.to_csv(path, sep='\t', index=False)
    with pytest.raises(DataValidationError):
        read_mt5_csv(path)


def test_header_only_file_is_not_a_valid_dataset(tmp_path):
    path = tmp_path / 'empty.csv'
    path.write_text('timestamp,open,high,low,close,volume\n')
    with pytest.raises(DataValidationError):
        read_dukascopy_csv(path)
