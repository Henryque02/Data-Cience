"""Conversão dos CSVs brutos em um Parquet padronizado por ativo.

Este projeto não tem testes automatizados. Um erro aqui deixa um Parquet de outro fuso, ou com
candles conflitantes, ser publicado como válido, ou apaga o Parquet bom anterior. Nada disso dá
erro depois. Ao alterar este módulo, confira as garantias abaixo.

PARQUET PUBLICADO (data/interim/<id>_m1.parquet)

- Colunas, nesta ordem: datetime, open, high, low, close, volume. datetime é
  `datetime64[ns, UTC]`. Com um CSV de 3 candles, o 1º candle é 2026-10-29 00:00 UTC e rows = 3.
- Toda execução refaz o Parquet a partir de raw/. As mesmas entradas geram os mesmos dados.
- Arquivos que se sobrepõem são unidos. Dois arquivos idênticos de 3 candles dão rows = 3,
  source_rows = 6 e duplicates_removed = 3.
- Sobreposição com candle diferente (close 7719,675 contra 7719,676) levanta
  DataValidationError e o Parquet anterior fica intacto. O arquivo novo só substitui o antigo no
  fim (`replace`), depois de escrito inteiro em pasta temporária.
- Fonte desconhecida levanta ValueError. Ativo sem arquivo bruto levanta FileNotFoundError.
- Não há registro de hash: um CSV válido, mas editado à mão, entra sem aviso. Por isso, raw/
  nunca deve ser editado.

FUSO DO PROFESSOR

- O fuso do CSV do professor vem da configuração (`timezone`). Trocar America/Sao_Paulo por UTC
  muda o 1º candle do WIN de 14:49 UTC para 11:49 UTC, ou seja, desloca a série inteira em 3 h.
  Confirmar o fuso na corretora está em "Suposições em aberto" do README.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import pandas as pd
import yaml

from .download import PROJECT
from .io import normalize_candles, read_dukascopy_csv, read_mt5_api_csv, read_mt5_csv


def raw_files(asset_id: str, asset: dict, data_dir: Path) -> list[Path]:
    """Seleciona só o histórico definido, sem incluir piloto ou outras fontes."""
    if asset['source'] == 'dukascopy':
        files = sorted((data_dir / 'raw/feature' / asset_id).glob('*.csv'))
    elif asset['source'] == 'professor':
        files = [data_dir / 'raw/target' / asset['filename']]
    elif asset['source'] == 'mt5':
        files = sorted((data_dir / 'raw/mt5' / asset_id).glob('*.csv'))
    else:
        raise ValueError(f"Fonte desconhecida: {asset['source']}")
    if not files or any(not path.is_file() for path in files):
        raise FileNotFoundError(f'Nenhum histórico disponível para {asset_id}.')
    return files


def build_asset(asset_id: str, asset: dict, data_dir: str | Path) -> dict:
    """Gera um Parquet UTC; mantém a saída anterior se uma entrada for inválida."""
    root = Path(data_dir).resolve()
    frames = []
    count = 0
    for path in raw_files(asset_id, asset, root):
        if asset['source'] == 'dukascopy':
            frame = read_dukascopy_csv(path)
        elif asset['source'] == 'professor':
            frame = read_mt5_csv(path, asset.get('timezone', 'America/Sao_Paulo'), volume_column=asset.get('volume_column', '<VOL>'))
        else:
            frame = read_mt5_api_csv(path, volume_column=asset.get('volume_column', 'real_volume'))
        count += frame.attrs['source_rows']
        frames.append(frame)
    combined = normalize_candles(pd.concat(frames, ignore_index=True))
    del frames
    record = {'asset': asset_id, 'rows': len(combined), 'source_rows': count,
              'duplicates_removed': count - len(combined),
              'first_utc': combined.datetime.iloc[0].isoformat(),
              'last_utc': combined.datetime.iloc[-1].isoformat()}
    combined.attrs = {}
    output = root / 'interim' / f'{asset_id}_m1.parquet'
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{asset_id}-', dir=output.parent) as folder:
        temporary = Path(folder) / 'candles.parquet'
        combined.to_parquet(temporary, engine='pyarrow', index=False, compression='zstd')
        record['parquet_bytes'] = temporary.stat().st_size
        # Só substitui o Parquet anterior depois de escrito inteiro; falha antes preserva o antigo.
        temporary.replace(output)
    return record


def build_all(
    project_root: str | Path = PROJECT,
    *,
    config: dict | None = None,
    asset_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Padroniza os ativos sequencialmente para limitar o uso de memória."""
    project_root = Path(project_root).resolve()
    config = config or yaml.safe_load((project_root / 'config/assets.yaml').read_text())
    ids = asset_ids if asset_ids is not None else list(config['assets'])
    results = []
    for asset_id in ids:
        record = build_asset(asset_id, config['assets'][asset_id], project_root / 'data')
        results.append(record)
        print(f"{asset_id}: {record['rows']:,} candles", flush=True)
    return pd.DataFrame(results)


def main(argv: list[str] | None = None) -> int:
    """Entrada equivalente à célula de conversão do notebook."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--assets', nargs='+')
    args = parser.parse_args(argv)
    print(build_all(asset_ids=args.assets).to_string(index=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
