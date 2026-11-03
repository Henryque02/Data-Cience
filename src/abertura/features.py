"""Variáveis pré-abertura (x_pre_) e de abertura observada (x_open_).

Este projeto não tem testes automatizados. Quem alterar este módulo ou
`daily.py` precisa conferir à mão as garantias abaixo. Se uma delas quebrar, o
código continua rodando sem erro, mas o resultado do modelo deixa de valer.

VAZAMENTO (AGENTS.md, seção 3.2)

Vazamento é usar uma informação que ainda não existia na hora da decisão. O
modelo parece acertar mais, mas está olhando a resposta. Para conferir, rode
`daily.build_target` duas vezes, mudando só os dados indicados, e compare a
linha do dia D. Confira sempre o par: a primeira verificação de cada par sozinha
também passaria se a variável não lesse dado nenhum.

1. x_pre_ não enxerga depois do corte. Dobrar os preços externos depois das
   08:58 BRT de D e triplicar os preços do dia D inteiro do alvo não pode mudar
   nenhuma x_pre_ de D.
2. O corte é mesmo usado. Multiplicar só o close do candle aberto às 08:58 BRT
   tem de mudar x_pre_<ativo>_overnight.
3. x_open_ só conhece o open do primeiro candle de D. Mudar high, low, close ou
   volume desse candle, ou qualquer campo dos candles seguintes, não pode mudar
   nenhuma x_open_.
4. Esse open é mesmo usado. Mudá-lo tem de mudar x_open_gap.

CÁLCULO

- last_price: com candles às 11:56, 11:57, 11:58 e 11:59 e closes 1, 2, 3 e 4, o
  preço às 11:58 e às 11:58:30 é 3; o candle das 11:59 não conta. Candle das
  10:00 vale às 11:00 com limite de 60 min e vira NaN às 11:01. Sem candle
  anterior também é NaN. Nunca usar preço posterior nem preencher o buraco.
- realized_vol: soma só retornos de candles depois do início e até o fim. Com
  log-preços 0; 0,5; 0,51; 0,54 e 2,0 das 00:00 às 00:04, o intervalo de 00:01 a
  00:03 dá raiz(0,01² + 0,03²).
- session_moments: em 2026-03-11, o corte de 08:58 BRT é 11:58 UTC.
  prev_close_utc e prev2_close_utc são os últimos candles dos dois pregões
  anteriores do calendário. Se D-1 falta nos dados, prev_close_utc fica vazio:
  nunca recorrer ao último pregão disponível, pois o gap atravessaria um buraco.
- asia_session_return: usa o horário local do mercado, nunca BRT. Em Tóquio, das
  09:00 às 15:30 de 2026-03-10 equivale a 00:00–06:30 UTC.
- target_features: usa só pregões anteriores a D. Um choque no próprio D não pode
  mudar a linha de D. Com menos de 5 pregões anteriores, a faixa de 5 dias fica
  NaN. Mede dentro de cada pregão, para o salto da rolagem não entrar.
- open_features: dia de rolagem não tem gap, porque o salto entre contratos não é
  movimento de mercado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .sessions import LOCAL_TIMEZONE, local_dates

NANOSECONDS_PER_MINUTE = 60_000_000_000


def _nanoseconds(values: pd.Series) -> np.ndarray:
    """Converte instantes para inteiros UTC; ausentes ficam negativos."""
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit('ns').asi8


def last_price(candles: pd.DataFrame, moments: pd.Series, max_age_minutes: int) -> pd.Series:
    """Último close com candle aberto até cada instante; preço antigo vira NaN."""
    times = _nanoseconds(candles.datetime)
    stamps = _nanoseconds(moments)
    # side='right' inclui o candle aberto no instante; 'left' perderia o candle das 08:58.
    position = np.searchsorted(times, stamps, side='right') - 1
    known = position.clip(0)
    prices = candles.close.to_numpy()[known].astype(float)
    too_old = stamps - times[known] > max_age_minutes * NANOSECONDS_PER_MINUTE
    prices[moments.isna().to_numpy() | (position < 0) | too_old] = np.nan
    return pd.Series(prices, index=moments.index)


def realized_vol(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Raiz da soma dos retornos quadráticos de 1 min dentro de cada intervalo."""
    times = _nanoseconds(candles.datetime)
    squared = np.r_[0.0, np.diff(np.log(candles.close.to_numpy())) ** 2].cumsum()
    first = np.searchsorted(times, _nanoseconds(starts), side='right').clip(1)
    last = np.searchsorted(times, _nanoseconds(ends), side='right').clip(1)
    result = pd.Series(np.sqrt(squared[last - 1] - squared[first - 1]), index=starts.index)
    return result.where(starts.notna() & ends.notna())


def session_moments(sessions: pd.DataFrame, calendar: pd.DatetimeIndex, cutoff_brt: str) -> pd.DataFrame:
    """Instantes de referência de cada pregão, em UTC; sem D-1 nos dados fica vazio."""
    previous = pd.Series(calendar[:-1], index=calendar[1:])
    prev_date = sessions.index.to_series().map(previous)
    hours, minutes = (int(part) for part in cutoff_brt.split(':'))
    cutoff = sessions.index.tz_localize(LOCAL_TIMEZONE) + pd.Timedelta(hours=hours, minutes=minutes)
    return pd.DataFrame({'prev_close_utc': prev_date.map(sessions.last_utc),
                         'prev2_close_utc': prev_date.map(previous).map(sessions.last_utc),
                         'cutoff_utc': cutoff.tz_convert('UTC')}, index=sessions.index)


def asia_session_return(candles: pd.DataFrame, dates: pd.DatetimeIndex, session: dict, max_age: int) -> pd.Series:
    """Retorno do pregão asiático de cada data, definido no horário local do mercado."""
    midnight = dates.tz_localize(session['timezone'])
    moments = {key: pd.Series(midnight + pd.Timedelta(f'{session[key]}:00'), index=dates).dt.tz_convert('UTC')
               for key in ('start', 'end')}
    return last_price(candles, moments['end'], max_age) / last_price(candles, moments['start'], max_age) - 1


def external_features(name: str, candles: pd.DataFrame, moments: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Retornos e volatilidade de um ativo externo, só com preços até o corte."""
    reference_age = settings['reference_max_age_minutes']
    cutoff = last_price(candles, moments.cutoff_utc, settings['max_price_age_minutes'])
    previous = last_price(candles, moments.prev_close_utc, reference_age)
    earlier = last_price(candles, moments.prev2_close_utc, reference_age)
    result = pd.DataFrame(index=moments.index)
    result[f'x_pre_{name}_overnight'] = cutoff / previous - 1
    for minutes in settings['recent_windows_minutes']:
        start = moments.cutoff_utc - pd.Timedelta(minutes=minutes)
        result[f'x_pre_{name}_last_{minutes}m'] = cutoff / last_price(candles, start, reference_age) - 1
    result[f'x_pre_{name}_night_vol'] = realized_vol(candles, moments.prev_close_utc, moments.cutoff_utc)
    result[f'x_pre_{name}_prev_day'] = previous / earlier - 1
    if name in settings['asia_sessions']:
        session = settings['asia_sessions'][name]
        result[f'x_pre_{name}_session'] = asia_session_return(candles, moments.index, session, reference_age)
    return result


def target_features(candles: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Histórico do alvo até D-1, medido dentro dos pregões para ignorar a rolagem."""
    daily = candles.groupby(local_dates(candles)).agg(
        open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))
    # shift(1) impede o dia D de entrar na própria variável; removê-lo cria vazamento.
    result = pd.DataFrame({
        'x_pre_target_range_5d': (daily.high / daily.low - 1).rolling(5).mean().shift(1),
        'x_pre_target_return_prev': (daily.close / daily.open - 1).shift(1)})
    return result.reindex(dates)


def open_features(first_open: pd.Series, prev_close: pd.Series, is_roll_day: pd.Series) -> pd.DataFrame:
    """Gap observado: do dia D, só o open do primeiro candle; rolagem o invalida."""
    gap = (first_open / prev_close - 1).where(~is_roll_day)
    return pd.DataFrame({'x_open_gap': gap, 'x_open_gap_abs': gap.abs()})
