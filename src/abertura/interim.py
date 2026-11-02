"""Publicação reexecutável dos Parquets padronizados por ativo."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd
import yaml

from .download import IntegrityError, PROJECT, sha256, write_json
from .io import normalize_candles, read_dukascopy_csv, read_mt5_api_csv, read_mt5_csv

PARSER_VERSION = 1


def raw_files(asset_id: str, asset: dict, data_dir: Path) -> list[Path]:
    """Seleciona só o histórico definido, sem incluir piloto ou outras fontes."""
    if asset['source'] == 'dukascopy':
        files = sorted((data_dir / 'raw/dukascopy' / asset_id).glob('*.csv'))
    elif asset['source'] == 'professor':
        files = [data_dir / 'raw/professor' / asset['filename']]
    elif asset['source'] == 'mt5':
        files = sorted((data_dir / 'raw/mt5' / asset_id).glob('*.csv'))
    else:
        raise ValueError(f"Fonte desconhecida: {asset['source']}")
    if not files or any(not path.is_file() for path in files):
        raise FileNotFoundError(f'Nenhum histórico disponível para {asset_id}.')
    return files


def _provenance(asset_id: str, asset: dict, files: list[Path], root: Path) -> list[dict]:
    """Confere hashes de aquisição quando disponíveis e registra cada entrada."""
    result = []
    professor_meta = root / 'metadata/professor.json'
    known_professor = {}
    if professor_meta.exists():
        known_professor = {Path(item['path']).name: item['sha256']
                           for item in json.loads(professor_meta.read_text())['files']}
    for path in files:
        digest = sha256(path)
        acquisition = root / 'metadata/dukascopy' / asset_id / f'{path.stem}.json'
        expected = None
        if asset['source'] == 'dukascopy' and acquisition.exists():
            acquired = json.loads(acquisition.read_text())
            expected_identity = {'asset': asset_id, 'symbol': asset['symbol'], 'timeframe': 'm1',
                                 'price_type': 'bid', 'utc_offset_minutes': 0, 'volume_included': True}
            mismatches = [key for key, value in expected_identity.items() if acquired.get(key) != value]
            if mismatches:
                raise IntegrityError(f'Manifesto de aquisição incompatível ({", ".join(mismatches)}): {acquisition}')
            expected = acquired['sha256']
        elif asset['source'] == 'professor':
            expected = known_professor.get(path.name)
        if expected is not None and digest != expected:
            raise IntegrityError(f'Arquivo bruto diverge do registro de aquisição: {path}')
        result.append({'path': str(path.relative_to(root)), 'sha256': digest,
                       'collection_hash_verified': expected is not None})
    return result


def build_asset(asset_id: str, asset: dict, data_dir: str | Path, *, force: bool = False) -> dict:
    """Gera um Parquet UTC; mantém a saída anterior se uma entrada for inválida."""
    root = Path(data_dir).resolve()
    files = raw_files(asset_id, asset, root)
    sources = _provenance(asset_id, asset, files, root)
    options = {key: asset.get(key) for key in ('source', 'symbol', 'filename', 'timezone', 'volume_column')}
    identity = {'parser_version': PARSER_VERSION, 'options': options, 'files': sources}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    output = root / 'interim' / f'{asset_id}_m1.parquet'
    metadata = root / 'metadata/interim' / f'{asset_id}.json'
    if not force and output.exists() and metadata.exists():
        previous = json.loads(metadata.read_text())
        if previous.get('input_fingerprint') == fingerprint and previous.get('parquet_sha256') == sha256(output):
            return {**previous, 'status': 'skipped'}

    frames = []
    count = 0
    for path in files:
        if asset['source'] == 'dukascopy':
            frame = read_dukascopy_csv(path)
        elif asset['source'] == 'professor':
            frame = read_mt5_csv(path, asset.get('timezone', 'America/Sao_Paulo'),
                                 volume_column=asset.get('volume_column', '<VOL>'))
        else:
            frame = read_mt5_api_csv(path, volume_column=asset.get('volume_column', 'real_volume'))
        count += frame.attrs['source_rows']
        frames.append(frame)
    combined = normalize_candles(pd.concat(frames, ignore_index=True))
    del frames
    record = {**identity, 'asset': asset_id, 'input_fingerprint': fingerprint,
              'rows': len(combined), 'source_rows': count, 'duplicates_removed': count - len(combined),
              'first_utc': combined.datetime.iloc[0].isoformat(),
              'last_utc': combined.datetime.iloc[-1].isoformat(),
              'parquet_path': str(output.relative_to(root)),
              'datetime_dtype': str(combined.datetime.dtype),
              'built_at_utc': datetime.now(UTC).isoformat()}
    combined.attrs = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{asset_id}-', dir=output.parent) as folder:
        temporary = Path(folder) / 'candles.parquet'
        combined.to_parquet(temporary, engine='pyarrow', index=False, compression='zstd')
        record['parquet_sha256'] = sha256(temporary)
        record['parquet_bytes'] = temporary.stat().st_size
        temporary.replace(output)
    write_json(metadata, record)
    return {**record, 'status': 'built'}


def build_all(
    project_root: str | Path = PROJECT,
    *,
    config: dict | None = None,
    asset_ids: list[str] | None = None,
    force: bool = False,
) -> pd.DataFrame:
    """Padroniza os ativos sequencialmente para limitar o uso de memória."""
    project_root = Path(project_root).resolve()
    config = config or yaml.safe_load((project_root / 'config/assets.yaml').read_text())
    ids = asset_ids if asset_ids is not None else list(config['assets'])
    results = []
    for asset_id in ids:
        record = build_asset(asset_id, config['assets'][asset_id], project_root / 'data', force=force)
        results.append({key: record[key] for key in
                        ('asset', 'status', 'rows', 'source_rows', 'duplicates_removed',
                         'first_utc', 'last_utc', 'parquet_bytes')})
        print(f"{asset_id}: {record['status']}, {record['rows']:,} candles", flush=True)
    return pd.DataFrame(results)


def main(argv: list[str] | None = None) -> int:
    """Entrada equivalente à célula de conversão do notebook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', nargs='+')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    print(build_all(asset_ids=args.assets, force=args.force).to_string(index=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
