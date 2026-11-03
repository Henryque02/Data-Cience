"""Coleta bruta Dukascopy com blocos validados e retomada.

Este projeto não tem testes automatizados. Um erro aqui deixa um CSV parcial, vazio, de outro
ativo ou de outro período passar por completo, sem erro nenhum. Tudo que vem depois (interim,
variáveis, rótulos) herda o defeito. Ao alterar este módulo, confira as garantias abaixo.

TEMPO (a ferramenta roda com -utc 0; não alterar)

- Todo horário aqui é UTC, em milissegundos. Nada é convertido para Brasília.
- month_windows divide [início, fim) em meses contíguos e sem sobreposição. De 2024-01-31 a
  2024-03-02 saem (01-31, 02-01), (02-01, 03-01) e (03-01, 03-02). Fevereiro de 2024 fica
  inteiro, com o dia 29. Se o fim deixar de ser exclusivo, o último dia vira dia duplicado.
- Início igual ao fim, ou depois do fim, levanta ValueError.
- inspect_csv recusa candle fora de [início, fim) em UTC. O CSV de exemplo começa em 1793232000000
  (2026-10-29 00:00 UTC). Pedir o período 2026-10-28 a 2026-10-29 precisa falhar, porque o dia
  29 é exclusivo. Timestamp que não é minuto cheio também é recusado.

VALIDAÇÃO DO CSV (inspect_csv, sem alterar o arquivo)

- CSV bom com 3 candles devolve rows = 3, first_utc 2026-10-29T00:00:00+00:00, last_utc
  2026-10-29T00:02:00+00:00, utc_days = 1 e as colunas timestamp, open, high, low, close, volume.
- Cada um destes casos precisa levantar DataValidationError: timestamp repetido, linhas fora de
  ordem, preço nan, high menor que open/close (ex.: high trocado por 1), arquivo só com
  cabeçalho, cabeçalho diferente (date no lugar de timestamp) e linha incompleta
  (`1793232180000,1`).
- Arquivo vazio nunca vale como "sem mercado": ausência de dados não foi comprovada.

PUBLICAÇÃO E RETOMADA (download_chunk)

- O CSV só aparece em raw/ depois de validado. A ferramenta falhar (CalledProcessError) não deixa
  CSV em raw/. Saída vazia da ferramenta levanta DataValidationError e também não deixa CSV.
- Bloco já publicado é reaproveitado sem chamar a rede: status 'downloaded' na primeira vez,
  'skipped' na segunda. Antes de reaproveitar, o CSV passa de novo por inspect_csv.
- CSV quebrado em raw/ (por exemplo, `broken` no fim) levanta DataValidationError e o arquivo é
  mantido como está, para inspeção. Nunca apagar nem rebaixar sozinho.
- Não há registro de hash: uma edição que mantenha o CSV válido, como trocar um preço, não é
  detectada. Por isso, raw/ nunca deve ser editado.
- asset_id fora de `[a-z][a-z0-9_]*`, como '../escape', levanta ValueError. Sem isso o caminho
  escaparia de data/.
- O comando da ferramenta precisa levar `-t m1 -utc 0 -p bid -v -ch`: candle de 1 min, UTC, preço
  bid, volume e cache. Mudar qualquer um desloca ou troca a série inteira sem erro.

EXECUÇÃO (main)

- Ctrl+C (SIGINT) não inicia bloco novo e devolve o código 130. Com 4 meses pedidos e um
  trabalhador, só janeiro roda.

Conferência: o período real recebido de cada ativo aparece na tabela de cobertura do notebook 01.
Compare com o pedido antes de usar. O calendário e os buracos são auditados em quality.py.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import UTC, date, datetime, time, timedelta
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from threading import Event
from typing import Callable, Iterator

import yaml

PROJECT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / '.cache' / 'abertura-b3'
FIELDS = ['timestamp', 'open', 'high', 'low', 'close', 'volume']


class DataValidationError(ValueError):
    """Arquivo recebido sem dados válidos para o intervalo solicitado."""


def month_windows(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Divide [início, fim) em meses contíguos, sem sobreposição."""
    if start >= end:
        raise ValueError('O início deve anteceder o fim exclusivo.')
    while start < end:
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        stop = min(next_month, end)
        yield start, stop
        start = stop


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
            # Fim exclusivo: um candle em 00:00 do dia final pertence ao bloco seguinte.
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
    """Baixa um bloco; arquivo já publicado é revalidado e reaproveitado."""
    if not re.fullmatch(r'[a-z][a-z0-9_]*', asset_id) or start >= end:
        raise ValueError('Identificador ou intervalo inválido.')
    root = root.resolve()
    name = f'{start.isoformat()}_{end.isoformat()}'
    output = root / 'raw' / ('feature_pilot' if pilot else 'feature') / asset_id / f'{name}.csv'
    if output.exists():
        return {**inspect_csv(output, start, end), 'status': 'skipped'}

    # Fica em data/ porque a publicação final só é atômica dentro do mesmo disco.
    staging = root / 'staging'
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'{asset_id}-', dir=staging) as folder:
        command = [
            'node', str(PROJECT / 'node_modules/dukascopy-node/dist/cli/index.js'),
            '-i', symbol, '-from', start.isoformat(), '-to', end.isoformat(),
            '-t', 'm1', '-f', 'csv', '-p', 'bid', '-utc', '0', '-v', '-ch',
            '-chpath', str(CACHE / 'dukascopy'),
            '--waf-token-cache-path', str(CACHE / 'dukascopy-waf' / 'token.json'),
            '-dir', folder, '-fn', name,
            '-bs', str(batch_size), '-bp', str(batch_pause_ms), '-r', str(retries),
        ]
        runner(command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, timeout=timeout, check=True)
        received = Path(folder) / f'{name}.csv'
        if not received.exists():
            raise DataValidationError(f'Ferramenta não produziu CSV: {asset_id} {name}')
        stats = inspect_csv(received, start, end)
        output.parent.mkdir(parents=True, exist_ok=True)
        received.replace(output)
    return {**stats, 'status': 'downloaded'}


def main(argv: list[str] | None = None) -> int:
    """Executa piloto ou histórico e registra sucessos e falhas por bloco."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
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
    summary = {'success': [], 'failures': []}
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
    except KeyboardInterrupt:
        stopped.set()
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
    print(f"Resumo: {len(summary['success'])} blocos válidos; {len(summary['failures'])} falhas.")
    if stopped.is_set():
        return 130
    return 1 if summary['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
