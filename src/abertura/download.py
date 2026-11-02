"""Coleta bruta Dukascopy com blocos verificáveis e retomada."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from threading import Event
from typing import Callable, Iterator

import yaml

PROJECT = Path(__file__).resolve().parents[2]
TOOL_VERSION = '1.51.1'
FIELDS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']


class DataValidationError(ValueError):
    """Arquivo recebido sem dados válidos para o intervalo solicitado."""


class IntegrityError(ValueError):
    """Arquivo bruto ou manifesto diverge da aquisição registrada."""


def month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Divide [início, fim) em meses contíguos, sem sobreposição."""
    if start >= end:
        raise ValueError('O início deve anteceder o fim exclusivo.')
    while start < end:
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        stop = min(next_month, end)
        yield start, stop
        start = stop


def sha256(path: Path) -> str:
    """Calcula o hash sem carregar o arquivo inteiro na memória."""
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_csv(path: Path, start: date, end: date) -> dict:
    """Verifica CSV real, preços, ordenação e limites UTC sem alterá-lo."""
    lower = int(datetime.combine(start, time(), UTC).timestamp()) * 1000
    upper = int(datetime.combine(end, time(), UTC).timestamp()) * 1000
    previous = None
    first = None
    rows = 0
    days: set[str] = set()
    largest_gap = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise DataValidationError(f'Cabeçalho inesperado: {reader.fieldnames}')
        for number, row in enumerate(reader, 2):
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('Linha incompleta ou com campos extras')
                stamp = int(row['timestamp'])
                prices = [float(row[key]) for key in FIELDS[1:]]
            except (TypeError, ValueError) as exc:
                raise DataValidationError(f'Linha {number} inválida: {exc}') from exc
            if not lower <= stamp < upper or stamp % 60000:
                raise DataValidationError(f'Timestamp fora de M1/intervalo na linha {number}')
            if previous is not None and stamp <= previous:
                raise DataValidationError(f'Timestamp duplicado ou desordenado na linha {number}')
            op, high, low, close, volume = prices
            if not all(math.isfinite(value) for value in prices):
                raise DataValidationError(f'Preço/volume não finito na linha {number}')
            if min(op, high, low, close) <= 0 or volume < 0:
                raise DataValidationError(f'Preço/volume inválido na linha {number}')
            if not low <= min(op, close) <= max(op, close) <= high:
                raise DataValidationError(f'OHLC inconsistente na linha {number}')
            if previous is not None:
                largest_gap = max(largest_gap, (stamp - previous) // 60000)
            first = stamp if first is None else first
            previous = stamp
            rows += 1
            days.add(datetime.fromtimestamp(stamp / 1000, UTC).date().isoformat())
    if not rows:
        raise DataValidationError('Arquivo vazio: ausência de mercado não foi comprovada.')
    return {
        'rows': rows,
        'first_utc': datetime.fromtimestamp(first / 1000, UTC).isoformat(),
        'last_utc': datetime.fromtimestamp(previous / 1000, UTC).isoformat(),
        'utc_days': len(days),
        'dates_utc': sorted(days),
        'largest_interval_minutes': largest_gap,
        'columns': FIELDS,
    }


def write_json(path: Path, content: dict) -> None:
    """Publica metadados atomicamente no mesmo sistema de arquivos."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def download_chunk(
    root: Path,
    asset_id: str,
    symbol: str,
    start: date,
    end: date,
    *,
    runner: Callable = subprocess.run,
    pilot: bool = False,
    timeout: int = 300,
    batch_size: int = 5,
    batch_pause_ms: int = 1000,
    retries: int = 3,
) -> dict:
    """Baixa um bloco; reutiliza apenas dados com manifesto e hash válidos."""
    if not re.fullmatch(r'[a-z][a-z0-9_]*', asset_id) or start >= end:
        raise ValueError('Identificador ou intervalo inválido.')
    root = root.resolve()
    scope = 'dukascopy_pilot' if pilot else 'dukascopy'
    name = f'{start.isoformat()}_{end.isoformat()}'
    output = root / 'raw' / scope / asset_id / f'{name}.csv'
    manifest = root / 'metadata' / scope / asset_id / f'{name}.json'
    log = root / 'logs' / scope / asset_id / f'{name}.log'
    expected = {
        'schema_version': 1,
        'asset': asset_id,
        'symbol': symbol,
        'start_utc': start.isoformat(),
        'end_exclusive_utc': end.isoformat(),
        'timeframe': 'm1',
        'price_type': 'bid',
        'utc_offset_minutes': 0,
        'volume_included': True,
        'tool': 'dukascopy-node',
        'tool_version': TOOL_VERSION,
    }
    if output.exists():
        try:
            old = json.loads(manifest.read_text())
        except (OSError, ValueError) as exc:
            raise IntegrityError(f'CSV sem manifesto válido: {output}') from exc
        if any(old.get(key) != value for key, value in expected.items()):
            raise IntegrityError(f'Manifesto incompatível: {manifest}')
        if old.get('sha256') != sha256(output) or not old.get('rows'):
            raise IntegrityError(f'Arquivo bruto alterado: {output}')
        return {**old, 'status': 'skipped'}

    log.parent.mkdir(parents=True, exist_ok=True)
    staging = root / 'staging'
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'{asset_id}-', dir=staging) as folder:
        command = [
            'node', str(PROJECT / 'node_modules/dukascopy-node/dist/cli/index.js'),
            '-i', symbol, '-from', start.isoformat(), '-to', end.isoformat(),
            '-t', 'm1', '-f', 'csv', '-p', 'bid', '-utc', '0', '-v', '-ch',
            '-chpath', str(root / 'cache' / 'dukascopy'),
            '--waf-token-cache-path', str(root / 'cache' / 'dukascopy-waf' / 'token.json'),
            '-dir', folder, '-fn', name,
            '-bs', str(batch_size), '-bp', str(batch_pause_ms), '-r', str(retries),
        ]
        with log.open('w') as stream:
            runner(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=True)
        received = Path(folder) / f'{name}.csv'
        if not received.exists():
            raise DataValidationError(f'Ferramenta não produziu CSV; consulte {log}')
        stats = inspect_csv(received, start, end)
        record = {
            **expected, **stats,
            'sha256': sha256(received),
            'bytes': received.stat().st_size,
            'downloaded_at_utc': datetime.now(UTC).isoformat(),
            'csv_path': str(output),
            'manifest_path': str(manifest),
            'log_path': str(log),
            'command': command,
            'coverage_note': 'Requisição concluída; calendário e buracos serão auditados separadamente.',
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        # O CSV é o ponto de confirmação: se os metadados falharem, ele
        # permanece temporário. Manifesto sem CSV pode ser retomado normalmente.
        write_json(manifest, record)
        received.replace(output)
    return {**record, 'status': 'downloaded'}


def import_professor(root: Path, source: Path) -> list[dict]:
    """Copia os arquivos existentes sem modificar seus bytes nem os originais."""
    records = []
    for name in ('WIN$N_M1.csv', 'WDO$N_M1.csv'):
        original = source / name
        if not original.exists():
            continue
        target = root / 'raw' / 'professor' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256(original)
        if target.exists() and sha256(target) != digest:
            raise IntegrityError(f'Cópia do professor já existe com conteúdo diferente: {target}')
        if not target.exists():
            shutil.copy2(original, target)
        records.append({'source': str(original.resolve()), 'path': str(target.resolve()),
                        'sha256': digest, 'bytes': target.stat().st_size})
    write_json(root / 'metadata' / 'professor.json', {'files': records})
    return records


def main(argv: list[str] | None = None) -> int:
    """Executa piloto ou histórico e registra sucessos e falhas por bloco."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT / 'config/assets.yaml')
    parser.add_argument('--params', type=Path, default=PROJECT / 'config/params.yaml')
    parser.add_argument('--data-dir', type=Path, default=PROJECT / 'data')
    parser.add_argument('--assets', nargs='+')
    parser.add_argument('--start', type=date.fromisoformat)
    parser.add_argument('--end', type=date.fromisoformat, help='Fim UTC exclusivo; dia corrente excluído')
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--workers', type=int)
    parser.add_argument('--plan', action='store_true', help='Lista requisições sem baixar')
    args = parser.parse_args(argv)
    settings = yaml.safe_load(args.params.read_text())['acquisition']
    config = yaml.safe_load(args.config.read_text())
    assets = {key: value for key, value in config['assets'].items() if value['source'] == 'dukascopy'}
    if args.assets:
        missing = set(args.assets) - assets.keys()
        if missing:
            parser.error(f'Ativos sem fonte Dukascopy: {sorted(missing)}')
        assets = {key: assets[key] for key in args.assets}
    workers = args.workers if args.workers is not None else settings['workers']
    if not 1 <= workers <= 4:
        parser.error('--workers deve ficar entre 1 e 4.')
    start = args.start or date.fromisoformat(config['period']['start'])
    end = args.end or datetime.now(UTC).date()
    if start >= end or end > datetime.now(UTC).date():
        parser.error('Intervalo inválido ou inclui dia UTC ainda incompleto.')
    if args.pilot:
        windows = [(date.fromisoformat(item['start']), date.fromisoformat(item['end_exclusive']))
                   for item in settings['pilot_periods']]
    else:
        windows = list(month_windows(start, end))
    if args.plan:
        print(json.dumps({'assets': assets, 'windows': [[str(a), str(b)] for a, b in windows],
                          'requests': len(assets) * len(windows)}, ensure_ascii=False, indent=2))
        return 0

    root = args.data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')
    summary_path = root / 'metadata' / 'runs' / f'{run_id}.json'
    summary = {'run_id': run_id, 'pilot': args.pilot, 'start_utc': str(start),
               'end_exclusive_utc': str(end), 'assets': list(assets),
               'requested_chunks': len(assets) * len(windows), 'success': [], 'failures': []}
    write_json(summary_path, summary)
    stopped = Event()

    def collect(asset_id: str, asset: dict) -> tuple[list[dict], list[dict]]:
        successes, failures = [], []
        for begin, stop in windows:
            if stopped.is_set():
                break
            try:
                record = download_chunk(
                    root, asset_id, asset['symbol'], begin, stop, pilot=args.pilot,
                    timeout=settings['timeout_seconds'], batch_size=settings['batch_size'],
                    batch_pause_ms=settings['batch_pause_ms'], retries=settings['retries'],
                )
                successes.append(record)
                print(f"{asset_id} {begin}..{stop} {record['status']} rows={record['rows']}", flush=True)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append({'asset': asset_id, 'start': str(begin), 'end_exclusive': str(stop),
                                 'error': f'{type(exc).__name__}: {exc}'})
                print(f'ERRO {asset_id} {begin}..{stop}: {exc}', flush=True)
                # Evita milhares de tentativas se um ativo não tiver dados na fonte.
                if len(failures) >= 3 and not successes:
                    break
        return successes, failures

    pool = ThreadPoolExecutor(max_workers=workers)
    tasks = {pool.submit(collect, key, value): key for key, value in assets.items()}
    recorded = set()
    try:
        for task in as_completed(tasks):
            successes, failures = task.result()
            summary['success'].extend(successes)
            summary['failures'].extend(failures)
            recorded.add(task)
            write_json(summary_path, summary)
    except KeyboardInterrupt:
        stopped.set()
        summary['interrupted'] = True
        for task in tasks:
            task.cancel()
        print('Interrompendo: aguardando apenas os blocos já em andamento.', flush=True)
    finally:
        pool.shutdown(wait=True, cancel_futures=stopped.is_set())
        # Após SIGINT, recolher também o resultado dos blocos que já estavam
        # em andamento; nenhum mês seguinte será iniciado pelos trabalhadores.
        for task in tasks:
            if task not in recorded and not task.cancelled():
                successes, failures = task.result()
                summary['success'].extend(successes)
                summary['failures'].extend(failures)
    summary['finished_at_utc'] = datetime.now(UTC).isoformat()
    if not stopped.is_set():
        summary['professor'] = import_professor(root, PROJECT / 'gg')
    write_json(summary_path, summary)
    print(f"Resumo: {len(summary['success'])} blocos válidos; {len(summary['failures'])} falhas. {summary_path}")
    if stopped.is_set():
        return 130
    return 1 if summary['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
