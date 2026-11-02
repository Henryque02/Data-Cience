"""Integração da publicação Parquet e da retomada com arquivos reais pequenos."""

import json
from pathlib import Path

import pandas as pd
import pytest

from abertura.download import DataValidationError, IntegrityError, sha256
from abertura.interim import build_asset

FIXTURE = Path(__file__).parent / 'fixtures/dukascopy_m1.csv'
ASSET = {'source': 'dukascopy', 'symbol': 'usa500idxusd'}


def source_file(root, name='part1.csv'):
    path = root / 'raw/dukascopy/spx' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(FIXTURE.read_bytes())
    return path


def record_acquisition(root, raw, **overrides):
    metadata = root / 'metadata/dukascopy/spx' / f'{raw.stem}.json'
    metadata.parent.mkdir(parents=True, exist_ok=True)
    record = {'asset': 'spx', 'symbol': 'usa500idxusd', 'timeframe': 'm1',
              'price_type': 'bid', 'utc_offset_minutes': 0, 'volume_included': True,
              'sha256': sha256(raw), **overrides}
    metadata.write_text(json.dumps(record))
    return metadata


def test_parquet_roundtrip_schema_and_resume(tmp_path):
    source_file(tmp_path)
    result = build_asset('spx', ASSET, tmp_path)
    frame = pd.read_parquet(tmp_path / 'interim/spx_m1.parquet')
    assert frame.datetime.iloc[0] == pd.Timestamp('2026-10-29T00:00:00Z')
    assert str(frame.datetime.dtype) == 'datetime64[ns, UTC]'
    assert list(frame) == ['datetime', 'open', 'high', 'low', 'close', 'volume']
    assert len(frame) == 3
    assert result['status'] == 'built'
    assert result['rows'] == 3
    assert build_asset('spx', ASSET, tmp_path)['status'] == 'skipped'


def test_identical_overlaps_between_files_are_counted(tmp_path):
    source_file(tmp_path, 'part1.csv')
    source_file(tmp_path, 'part2.csv')
    result = build_asset('spx', ASSET, tmp_path)
    assert result['rows'] == 3
    assert result['source_rows'] == 6
    assert result['duplicates_removed'] == 3


def test_conflicting_overlap_preserves_previous_parquet(tmp_path):
    source_file(tmp_path)
    build_asset('spx', ASSET, tmp_path)
    target = tmp_path / 'interim/spx_m1.parquet'
    old_hash = sha256(target)
    second = source_file(tmp_path, 'part2.csv')
    second.write_text(second.read_text().replace('7719.675', '7719.676'))
    with pytest.raises(DataValidationError):
        build_asset('spx', ASSET, tmp_path)
    assert sha256(target) == old_hash


def test_collection_hash_mismatch_is_rejected(tmp_path):
    raw = source_file(tmp_path)
    record_acquisition(tmp_path, raw)
    raw.write_text(raw.read_text() + '\n')
    with pytest.raises(IntegrityError):
        build_asset('spx', ASSET, tmp_path)


@pytest.mark.parametrize('field,value', [('asset', 'ndx'), ('symbol', 'usatechidxusd'),
                                        ('timeframe', 'm5'), ('price_type', 'ask'),
                                        ('utc_offset_minutes', 180), ('volume_included', False)])
def test_acquisition_identity_mismatch_is_rejected(tmp_path, field, value):
    raw = source_file(tmp_path)
    record_acquisition(tmp_path, raw, **{field: value})
    with pytest.raises(IntegrityError):
        build_asset('spx', ASSET, tmp_path)
    assert not (tmp_path / 'interim/spx_m1.parquet').exists()


def test_changed_config_symbol_cannot_relabel_existing_parquet(tmp_path):
    raw = source_file(tmp_path)
    record_acquisition(tmp_path, raw)
    build_asset('spx', ASSET, tmp_path)
    target = tmp_path / 'interim/spx_m1.parquet'
    original_hash = sha256(target)
    with pytest.raises(IntegrityError):
        build_asset('spx', {**ASSET, 'symbol': 'usatechidxusd'}, tmp_path)
    assert sha256(target) == original_hash


def test_changed_timezone_rebuilds_professor_data(tmp_path):
    path = tmp_path / 'raw/professor/WIN$N_M1.csv'
    path.parent.mkdir(parents=True)
    path.write_bytes((FIXTURE.parent / 'mt5_win.tsv').read_bytes())
    asset = {'source': 'professor', 'filename': path.name, 'timezone': 'America/Sao_Paulo'}
    first = build_asset('win', asset, tmp_path)
    second = build_asset('win', {**asset, 'timezone': 'UTC'}, tmp_path)
    assert first['input_fingerprint'] != second['input_fingerprint']
    assert second['status'] == 'built'
    assert pd.read_parquet(tmp_path / 'interim/win_m1.parquet').datetime.iloc[0] == pd.Timestamp('2020-10-15T11:49:00Z')
