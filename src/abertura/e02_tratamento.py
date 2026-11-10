"""Lê os CSVs brutos de cada ativo e grava um Parquet padronizado.


Gera data/tratamento/<ativo>_m1.parquet, um arquivo por ativo, com as colunas datetime
(UTC), open, high, low e close (float64), mais volume só em WIN e WDO, ordenado e sem
velas repetidas. É daqui que todas as etapas seguintes leem.

- WIN e WDO (targets em config/params.yaml): exportação do terminal MetaTrader, arquivo
  separado por TAB, com data e hora sem fuso. O fuso vem de targets (Brasília), e 09:00
  vira 12:00 UTC; é o único lugar do projeto que aplica fuso. O volume é <VOL>
  (contratos); <TICKVOL> e <SPREAD> são descartados. Cada alvo emenda dois arquivos de
  data/raw/target/: o primeiro vale até a véspera de switch_date e o segundo a partir
  dela, pela data de Brasília. Hoje é o professor até 05/11/2021 e a Genial desde
  08/11/2021; nos dias em comum as duas fontes eram 99,99% idênticas.
- Externos (externals): todos os CSVs mensais de data/raw/feature/<ativo>/. O timestamp
  da Dukascopy já é UTC (milissegundos desde 1970). O volume da fonte é descartado: não
  é volume real negociado e o AGENTS.md proíbe usá-lo.
- A junção remove velas idênticas (aparecem quando dois arquivos cobrem os mesmos dias),
  recusa com erro duas velas diferentes no mesmo horário e ordena.

Os ativos são processados um por vez, para não carregar tudo na memória. O Parquet é
gravado direto: se a gravação for interrompida, basta rodar de novo.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

PROJECT = Path(__file__).resolve().parents[2]
PRICE_COLUMNS = ['open', 'high', 'low', 'close']


def normalize_candles(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Mantém datetime e as colunas pedidas, com horário em UTC e valores float64."""
    result = frame[['datetime', *columns]].copy()
    result['datetime'] = result.datetime.dt.tz_convert('UTC').astype('datetime64[ns, UTC]')
    result[columns] = result[columns].astype('float64')
    return result


def read_mt5_csv(path: Path, timezone: str) -> pd.DataFrame:
    """Lê a exportação TAB do terminal MetaTrader e converte o horário local para UTC."""
    frame = pd.read_csv(path, sep='\t', encoding='utf-8-sig')
    local = pd.to_datetime(frame['<DATE>'] + ' ' + frame['<TIME>'], format='%Y.%m.%d %H:%M:%S')
    # Único ponto que aplica fuso. Dukascopy já vem em UTC: aplicar de novo desloca tudo.
    frame['datetime'] = local.dt.tz_localize(timezone).dt.tz_convert('UTC')
    frame = frame.rename(columns={
        '<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low', '<CLOSE>': 'close',
        '<VOL>': 'volume',
    })
    return normalize_candles(frame, [*PRICE_COLUMNS, 'volume'])


def read_dukascopy_csv(path: Path) -> pd.DataFrame:
    """Lê o CSV da Dukascopy, com timestamp em milissegundos UTC."""
    frame = pd.read_csv(path, encoding='utf-8-sig')
    frame['datetime'] = pd.to_datetime(frame.timestamp, unit='ms', utc=True)
    return normalize_candles(frame, PRICE_COLUMNS)


def merge_candles(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Une arquivos do mesmo ativo; velas idênticas saem, conflitantes causam erro."""
    # Sobreposição real: atualizar um mês já baixado em parte gera dois arquivos com os mesmos dias.
    result = pd.concat(frames, ignore_index=True).drop_duplicates()
    if result.duplicated('datetime').any():
        raise ValueError('Velas conflitantes no mesmo horário; decidir a fonte antes de continuar.')
    return result.sort_values('datetime', kind='stable').reset_index(drop=True)


def target_frames(spec: dict) -> list[pd.DataFrame]:
    """Lê os dois arquivos do alvo e mantém cada um do seu lado da data de troca."""
    first, second = (
        read_mt5_csv(PROJECT / 'data/raw/target' / name, spec['timezone']) for name in spec['files']
    )
    # A troca é pela hora local do arquivo (Brasília), não pela hora em UTC.
    switch = pd.Timestamp(spec['switch_date'], tz=spec['timezone'])
    return [first[first.datetime < switch], second[second.datetime >= switch]]


def external_frames(asset_id: str) -> list[pd.DataFrame]:
    """Lê todos os CSVs mensais do ativo externo."""
    files = sorted((PROJECT / 'data/raw/feature' / asset_id).glob('*.csv'))
    if not files:
        raise FileNotFoundError(f'Nenhum CSV em data/raw/feature/{asset_id}.')
    return [read_dukascopy_csv(path) for path in files]


def build_asset(asset_id: str, config: dict) -> dict:
    """Gera o Parquet do ativo e devolve um resumo."""
    if asset_id in config['targets']:
        frames = target_frames(config['targets'][asset_id])
    else:
        frames = external_frames(asset_id)
    count = sum(len(frame) for frame in frames)
    combined = merge_candles(frames)
    del frames
    output = PROJECT / 'data/tratamento' / f'{asset_id}_m1.parquet'
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output, engine='pyarrow', index=False, compression='zstd')
    return {
        'asset': asset_id,
        'rows': len(combined),
        'duplicates_removed': count - len(combined),
        'first_utc': combined.datetime.iloc[0].isoformat(),
        'last_utc': combined.datetime.iloc[-1].isoformat(),
    }


def build_all(asset_ids: list[str] | None = None) -> pd.DataFrame:
    """Padroniza os ativos um por vez."""
    config = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    ids = asset_ids or [*config['targets'], *config['externals']]
    return pd.DataFrame([build_asset(asset_id, config) for asset_id in ids])


def main(argv: list[str] | None = None) -> int:
    """Converte os ativos selecionados e imprime o resumo."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--assets', nargs='+')
    args = parser.parse_args(argv)
    print(build_all(args.assets).to_string(index=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
