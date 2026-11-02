"""Verifica limites temporais, integridade e retomada sem usar a rede."""

from datetime import date
from pathlib import Path
import json
import subprocess
import os
import signal
import threading
import time

import pytest

from abertura.download import (
    DataValidationError,
    IntegrityError,
    download_chunk,
    inspect_csv,
    month_windows,
)

START = date(2026, 10, 29)
END = date(2026, 10, 31)
FIXTURE = Path(__file__).parent / 'fixtures' / 'dukascopy_m1.csv'


def test_month_windows_preserves_leap_day_and_exclusive_end():
    assert list(month_windows(date(2024, 1, 31), date(2024, 3, 2))) == [
        (date(2024, 1, 31), date(2024, 2, 1)),
        (date(2024, 2, 1), date(2024, 3, 1)),
        (date(2024, 3, 1), date(2024, 3, 2)),
    ]


@pytest.mark.parametrize('start,end', [(END, START), (START, START)])
def test_month_windows_rejects_empty_or_reversed_range(start, end):
    with pytest.raises(ValueError):
        list(month_windows(start, end))


def test_real_csv_reports_utc_period_and_days():
    stats = inspect_csv(FIXTURE, START, END)
    assert stats['rows'] == 3
    assert stats['first_utc'] == '2026-10-29T00:00:00+00:00'
    assert stats['last_utc'] == '2026-10-29T00:02:00+00:00'
    assert stats['utc_days'] == 1
    assert stats['columns'] == ['timestamp', 'open', 'high', 'low', 'close', 'volume']


@pytest.mark.parametrize('problem', ['duplicate', 'unordered', 'nan', 'bad_ohlc', 'empty', 'header', 'partial_row'])
def test_invalid_csv_is_rejected(tmp_path, problem):
    lines = FIXTURE.read_text().splitlines()
    if problem == 'duplicate':
        lines.append(lines[-1])
    elif problem == 'unordered':
        lines[1], lines[2] = lines[2], lines[1]
    elif problem == 'nan':
        lines[1] = lines[1].replace('7719.536', 'nan')
    elif problem == 'bad_ohlc':
        lines[1] = lines[1].replace('7719.919', '1')
    elif problem == 'empty':
        lines = lines[:1]
    elif problem == 'header':
        lines[0] = lines[0].replace('timestamp', 'date')
    else:
        lines.append('1793232180000,1')
    path = tmp_path / 'invalid.csv'
    path.write_text('\n'.join(lines) + '\n')
    with pytest.raises(DataValidationError):
        inspect_csv(path, START, END)


def test_candle_at_exclusive_end_is_rejected():
    with pytest.raises(DataValidationError):
        inspect_csv(FIXTURE, date(2026, 10, 28), START)


def fake_vendor(command, *, stdout, stderr, timeout, check):
    """Substitui só a rede; usa a saída CSV real da ferramenta."""
    directory = Path(command[command.index('-dir') + 1])
    filename = command[command.index('-fn') + 1] + '.csv'
    assert command[command.index('-t') + 1] == 'm1'
    assert command[command.index('-utc') + 1] == '0'
    assert command[command.index('-p') + 1] == 'bid'
    assert '-v' in command and '-ch' in command
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(FIXTURE.read_bytes())
    return subprocess.CompletedProcess(command, 0)


def acquire(tmp_path, **kwargs):
    return download_chunk(tmp_path, 'spx', 'usa500idxusd', START, END, **kwargs)


def test_completed_chunk_is_reused_without_download(tmp_path):
    result = acquire(tmp_path, runner=fake_vendor)
    assert result['status'] == 'downloaded'
    assert result['rows'] == 3
    assert Path(result['csv_path']).read_bytes() == FIXTURE.read_bytes()

    def unavailable(*args, **kwargs):
        raise AssertionError('Retomada não deve chamar a rede')

    again = acquire(tmp_path, runner=unavailable)
    assert again['status'] == 'skipped'
    assert again['sha256'] == result['sha256']


def test_modified_raw_file_is_detected_and_preserved(tmp_path):
    result = acquire(tmp_path, runner=fake_vendor)
    path = Path(result['csv_path'])
    path.write_bytes(path.read_bytes() + b'broken\n')
    with pytest.raises(IntegrityError):
        acquire(tmp_path, runner=fake_vendor)
    assert path.read_bytes().endswith(b'broken\n')


def test_manifest_for_another_symbol_is_not_reused(tmp_path):
    result = acquire(tmp_path, runner=fake_vendor)
    manifest = Path(result['manifest_path'])
    content = json.loads(manifest.read_text())
    content['symbol'] = 'eurusd'
    manifest.write_text(json.dumps(content))
    with pytest.raises(IntegrityError):
        acquire(tmp_path, runner=fake_vendor)


def test_vendor_failure_keeps_no_completed_csv(tmp_path):
    def failure(command, **kwargs):
        fake_vendor(command, **kwargs)
        raise subprocess.CalledProcessError(1, command)

    with pytest.raises(subprocess.CalledProcessError):
        acquire(tmp_path, runner=failure)
    assert not list((tmp_path / 'raw').rglob('*.csv'))
    result = acquire(tmp_path, runner=fake_vendor)
    assert result['status'] == 'downloaded'


def test_empty_vendor_output_is_not_certified(tmp_path):
    def empty(command, **kwargs):
        fake_vendor(command, **kwargs)
        output = next(Path(command[command.index('-dir') + 1]).glob('*.csv'))
        output.write_text('timestamp,open,high,low,close,volume\n')
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(DataValidationError):
        acquire(tmp_path, runner=empty)
    assert not list((tmp_path / 'raw').rglob('*.csv'))


def test_asset_id_cannot_escape_data_directory(tmp_path):
    with pytest.raises(ValueError):
        download_chunk(tmp_path, '../escape', 'eurusd', START, END, runner=fake_vendor)


def test_failed_manifest_publication_leaves_no_orphan_csv(tmp_path, monkeypatch):
    import abertura.download as module
    original = module.write_json

    def fail(*args, **kwargs):
        raise OSError('Falha simulada na gravação do manifesto')

    monkeypatch.setattr(module, 'write_json', fail)
    with pytest.raises(OSError):
        acquire(tmp_path, runner=fake_vendor)
    assert not list((tmp_path / 'raw').rglob('*.csv'))
    monkeypatch.setattr(module, 'write_json', original)
    assert acquire(tmp_path, runner=fake_vendor)['status'] == 'downloaded'


@pytest.mark.skipif(os.name == 'nt', reason='SIGINT de processo testado no Linux')
def test_interrupt_stops_new_chunks_and_records_finished_work(tmp_path, monkeypatch):
    import abertura.download as module
    config = tmp_path / 'assets.yaml'
    config.write_text("period:\n  start: '2024-01-01'\nassets:\n  spx: {source: dukascopy, symbol: usa500idxusd}\n")
    started = []
    timer = threading.Timer(0.03, lambda: os.kill(os.getpid(), signal.SIGINT))

    def slow_download(root, asset_id, symbol, begin, end, **kwargs):
        started.append(begin)
        if len(started) == 1:
            timer.start()
        time.sleep(0.10)
        return {'asset': asset_id, 'rows': 3, 'status': 'downloaded'}

    monkeypatch.setattr(module, 'download_chunk', slow_download)
    try:
        result = module.main(['--config', str(config), '--data-dir', str(tmp_path / 'data'),
                              '--start', '2024-01-01', '--end', '2024-05-01', '--workers', '1'])
    finally:
        timer.cancel()
    assert result == 130
    assert started == [date(2024, 1, 1)]
    summary = json.loads(next((tmp_path / 'data/metadata/runs').glob('*.json')).read_text())
    assert summary['interrupted'] is True
    assert len(summary['success']) == 1
