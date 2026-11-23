"""Tratamento: padroniza as velas de 1 minuto e define os pregões da B3.

Uso: uv run --locked python -m abertura.e02_tratamento [--assets win spx ...]

O módulo tem duas partes.

1. Velas (o comando). Lê os arquivos brutos e grava data/tratamento/<ativo>_m1.parquet,
   um por ativo: datetime em UTC, open, high, low, close e, só em WIN e WDO, volume
   (contratos). As etapas seguintes leem só esses Parquets.
   - WIN e WDO: duas exportações do MetaTrader em data/raw/target/, com horário de
     Brasília sem fuso escrito. O fuso de targets (config/params.yaml) converte para UTC,
     e 09:00 vira 12:00 UTC; é o único ponto do projeto que aplica fuso. As exportações
     são emendadas na switch_date: a do professor até a véspera, a da Genial a partir
     dela (nos dias em comum, 99,99% das velas são iguais).
   - Externos: CSVs mensais da Dukascopy em data/raw/feature/<ativo>/, já em UTC. O volume
     deles é descartado, porque não é volume negociado.
   - Velas repetidas idênticas saem. Duas velas diferentes no mesmo minuto param o comando
     com erro: escolher a fonte é decisão humana. Se a gravação for interrompida, basta
     rodar de novo.

2. Pregões (funções usadas pelas etapas seguintes; não gravam nada e não excluem dias).
   - b3_sessions: calendário oficial da B3 (biblioteca exchange_calendars), com feriados e a
     marcação da Quarta-feira de Cinzas, que abre às 13:00. Bate com os dados nos feriados
     de São Paulo em que a B3 mudou de regra: houve pregão em 20/11/2020 e 25/01/2022, não
     em 09/07/2021. O corte das 12:58 na Cinzas fica em params.yaml e é aplicado no
     e03_feat_labels.py.
   - local_dates: data de Brasília (o pregão) de cada vela de WIN e WDO, para agrupá-las por
     dia. Os externos não são agrupados por data: são medidos entre dois instantes.
   - daily_sessions: para cada dia com dados, a primeira vela (abertura e início da janela
     pós-abertura) e a última (fechamento, que é o D-1 do pregão seguinte).
   - roll_dates: dias de troca de contrato, só como marcação; o gap continua calculado.
     WIN: quarta-feira mais próxima do dia 15 dos meses pares, ou o pregão seguinte se for
     feriado (12/10/2022 passou para 13/10/2022). WDO: último pregão de cada mês. O
     calendário recebido precisa cobrir meses inteiros, senão o último dia de um mês
     cortado viraria falsa rolagem. A evidência das regras está no AGENTS.md, seção 2.4.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import yaml

PROJECT = Path(__file__).resolve().parents[2]
PRICE_COLUMNS = ['open', 'high', 'low', 'close']
LOCAL_TIMEZONE = 'America/Sao_Paulo'


# 1. Velas

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
    """Padroniza os ativos um por vez, para não carregar tudo na memória."""
    config = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    ids = asset_ids or [*config['targets'], *config['externals']]
    return pd.DataFrame([build_asset(asset_id, config) for asset_id in ids])


# 2. Pregões

def b3_sessions(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DataFrame:
    """Dias de pregão da B3 entre as datas, com a marcação da Quarta-feira de Cinzas."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    calendar = xcals.get_calendar(
        'BVMF', start=start - pd.Timedelta(days=10), end=end + pd.Timedelta(days=10)
    )
    result = pd.DataFrame(index=calendar.schedule.loc[start:end].index.copy())
    result.index.name = 'date_brt'
    result['is_special_open'] = result.index.isin(calendar.late_opens)
    return result


def local_dates(frame: pd.DataFrame) -> pd.Series:
    """Retorna datas civis brasileiras, mantendo timestamps originais intactos."""
    return frame.datetime.dt.tz_convert(LOCAL_TIMEZONE).dt.tz_localize(None).dt.normalize()


def daily_sessions(frame: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Resume cada dia com dados; a abertura do dia é o primeiro candle observado."""
    dates = local_dates(frame)
    result = frame.datetime.groupby(dates).agg(first_utc='min', last_utc='max')
    result.index.name = 'date_brt'
    result = result.join(calendar)
    # Dias com dados antes do calendário (WDO do professor desde 17/09/2020) ficam sem marcação.
    result['is_special_open'] = result.is_special_open.astype('boolean').fillna(False).astype(bool)
    return result


def _win_roll_dates(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Quarta mais próxima do dia 15 dos meses pares; feriado passa ao pregão seguinte."""
    months = pd.period_range(sessions.min(), sessions.max(), freq='M')
    dates = []
    for month in months[months.month % 2 == 0]:
        day15 = pd.Timestamp(month.year, month.month, 15)
        nearest = day15 + pd.Timedelta(days=(5 - day15.dayofweek) % 7 - 3)
        position = sessions.searchsorted(nearest)
        if sessions.min() <= nearest and position < len(sessions):
            dates.append(sessions[position])
    return pd.DatetimeIndex(dates)


def _wdo_roll_dates(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Último pregão do mês: a série troca de contrato na véspera do vencimento."""
    last = pd.Series(sessions, index=sessions).groupby(sessions.to_period('M')).last()
    return pd.DatetimeIndex(last.to_numpy())


def roll_dates(asset: str, sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Pregões em que o gap do ativo contém a diferença entre contratos."""
    rules = {'win': _win_roll_dates, 'wdo': _wdo_roll_dates}
    return rules[asset](sessions)


def main(argv: list[str] | None = None) -> int:
    """Converte os ativos selecionados e imprime o resumo."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--assets', nargs='+')
    args = parser.parse_args(argv)
    print(build_all(args.assets).to_string(index=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
