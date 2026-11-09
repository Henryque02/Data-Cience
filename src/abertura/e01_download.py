"""Baixa da Dukascopy as velas de 1 minuto dos ativos externos.

Cada ativo é baixado em blocos mensais, um CSV por bloco, em
data/raw/feature/<ativo>/<início>_<fim>.csv. Os horários são UTC.
Sem --start, começa em download.start (config/params.yaml); sem --end, vai até ontem.
Um fim depois de hoje é recusado, porque o dia corrente ainda está incompleto.

Quem baixa é a ferramenta Node dukascopy-node (versão fixa no package.json), com velas
de 1 minuto, preço bid, volume e sem cache. Ela grava numa pasta temporária em
data/staging/, e o CSV só vai para data/raw/ se a ferramenta terminar sem erro dentro
do tempo limite e o arquivo tiver velas. Assim nunca fica arquivo pela metade.

Rodar de novo pula os blocos já publicados, então uma coleta interrompida continua de
onde parou. O conteúdo das velas não é conferido aqui: a junção e as duplicatas ficam
em e02_tratamento.py, e a elegibilidade dos pregões em e03_filtros.py.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import subprocess
import tempfile
from typing import Iterator

import yaml

PROJECT = Path(__file__).resolve().parents[2]


def month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Divide [início, fim) em meses contíguos, sem sobreposição."""
    while start < end:
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        stop = min(next_month, end)
        yield start, stop
        start = stop


def inspect_csv(path: Path) -> dict:
    """Conta os candles; CSV sem candles não representa download concluído."""
    with path.open(encoding='utf-8-sig') as stream:
        rows = sum(1 for _ in stream) - 1  # desconta o cabeçalho
    if rows < 1:
        raise ValueError(f'Arquivo sem candles: {path}')
    return {'rows': rows}


def download_chunk(
    root: Path,
    asset_id: str,
    dukascopy_id: str,
    start: date,
    end: date,
    *,
    timeout: int = 300,
    batch_size: int = 5,
    batch_pause_ms: int = 1000,
    retries: int = 3,
) -> dict:
    """Baixa um bloco; arquivo já publicado com candles é reaproveitado."""
    name = f'{start.isoformat()}_{end.isoformat()}'
    output = root / 'raw' / 'feature' / asset_id / f'{name}.csv'
    if output.exists():
        return {**inspect_csv(output), 'status': 'skipped'}

    # Fica em data/ porque a publicação final só é atômica dentro do mesmo disco.
    staging = root / 'staging'
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'{asset_id}-', dir=staging) as folder:
        command = [
            'node', str(PROJECT / 'node_modules/dukascopy-node/dist/cli/index.js'),
            '-i', dukascopy_id, '-from', start.isoformat(), '-to', end.isoformat(),
            '-t', 'm1', '-f', 'csv', '-p', 'bid', '-utc', '0', '-v',
            # Sem isto a ferramenta gravaria o token em ~/.dukascopy-node.
            '--waf-token-cache-path', str(Path(folder) / 'waf-token.json'),
            '-dir', folder, '-fn', name,
            '-bs', str(batch_size), '-bp', str(batch_pause_ms), '-r', str(retries),
        ]
        subprocess.run(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            timeout=timeout, check=True,
        )
        received = Path(folder) / f'{name}.csv'
        if not received.exists():
            raise ValueError(f'Ferramenta não produziu CSV: {asset_id} {name}')
        stats = inspect_csv(received)
        output.parent.mkdir(parents=True, exist_ok=True)
        received.replace(output)
    return {**stats, 'status': 'downloaded'}


def _argument_parser() -> argparse.ArgumentParser:
    """Define ativos, período e paralelismo da coleta."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--assets', nargs='+')
    parser.add_argument('--start', type=date.fromisoformat)
    parser.add_argument(
        '--end', type=date.fromisoformat, help='Fim UTC exclusivo; dia corrente excluído'
    )
    parser.add_argument('--workers', type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Baixa os blocos mensais e informa sucessos e falhas por bloco."""
    parser = _argument_parser()
    args = parser.parse_args(argv)
    config = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    settings, assets = config['download'], config['externals']
    if args.assets:
        assets = {key: assets[key] for key in args.assets}
    start = args.start or date.fromisoformat(settings['start'])
    end = args.end or datetime.now(UTC).date()
    if start >= end or end > datetime.now(UTC).date():
        parser.error('Intervalo inválido ou inclui dia UTC ainda incompleto.')
    windows = list(month_windows(start, end))
    root = PROJECT / 'data'
    options = {
        'timeout': settings['timeout_seconds'],
        'batch_size': settings['batch_size'], 'batch_pause_ms': settings['batch_pause_ms'],
        'retries': settings['retries'],
    }
    workers = args.workers if args.workers is not None else settings['workers']
    pool = ThreadPoolExecutor(max_workers=workers)
    tasks = {
        pool.submit(download_chunk, root, asset_id, dukascopy_id, begin, stop, **options):
            (asset_id, begin, stop)
        for asset_id, dukascopy_id in assets.items() for begin, stop in windows
    }
    failures = 0
    for task in as_completed(tasks):
        asset_id, begin, stop = tasks[task]
        try:
            record = task.result()
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            failures += 1
            print(f'ERRO {asset_id} {begin}..{stop}: {exc}', flush=True)
            continue
        print(f"{asset_id} {begin}..{stop} {record['status']} rows={record['rows']}", flush=True)
    pool.shutdown()
    print(f'Resumo: {len(tasks) - failures} blocos válidos; {failures} falhas.')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
