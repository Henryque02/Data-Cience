"""Variáveis do modelo: x_pre_ (antes da abertura) e x_open_ (o gap observado).

Não tem comando próprio: quem chama é o e06_daily.py.

- last_price dá o último close com vela aberta até um instante. No corte das 08:58 a
  vela das 08:58 entra (fecha às 08:59). Preço com mais de 7 dias fica vazio.

- traded diz se o ativo teve alguma vela dentro de um intervalo. Cada variável externa só
  existe se o ativo negociou no intervalo que ela mede; senão fica vazia. Assim um feriado
  lá fora não vira retorno zero. Se negociou e parou (pane da bolsa), vale o último preço.

- session_moments calcula, para cada pregão D, o fechamento do alvo em D-1 e em D-2 e o
  corte de D às 08:58. Se o alvo não tem D-1 nos dados, as variáveis externas ficam vazias.

- without_daily_pauses, só para Brent e cobre (daily_pause_assets em config/params.yaml):
  esses CFDs seguem o contrato futuro e trocam de vencimento na pausa diária da Dukascopy
  (18:00-21:00 BRT no Brent, ~1 h no cobre), com um salto falso de preço. Os retornos
  desses dois ignoram a variação entre o fechamento e a reabertura de toda pausa de 30 min
  a 12 h; a reabertura de fim de semana, que traz notícia real, é mantida. Custo: perde o
  movimento real da pausa, em média 0,2% no Brent e 0,04% no cobre.

- external_features cria, por ativo externo: overnight (do fechamento da B3 até 08:58),
  last_60m e last_180m (última 1h e 3h) e night_vol (volatilidade da madrugada), que
  exigem negociação depois do fechamento da B3; e prev_day (de D-2 a D-1), que exige
  negociação nesse intervalo. Nikkei e A50 ganham session, o retorno do pregão local,
  com horário no fuso de lá, que exige negociação no pregão.

- target_features cria, com o próprio alvo, a amplitude média dos 5 pregões anteriores e
  o retorno do pregão anterior; medidas dentro do pregão, não incluem a rolagem.
  
- open_features calcula o gap (abertura da 1ª vela de D / fechamento de D-1 - 1) e seu
  tamanho sem sinal. Em dia de rolagem o gap fica vazio.

Conferência contra vazamento (AGENTS.md, seção 3.2), num dia real: alterar preços
externos depois das 08:58 ou velas do alvo no dia D não pode mudar as x_pre_ de D;
alterar o close externo das 08:58 muda o overnight. Alterar máxima, mínima, fechamento
ou volume da 1ª vela de D, ou as velas seguintes, não pode mudar o gap; alterar a
abertura da 1ª vela muda.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .e03_filtros import LOCAL_TIMEZONE, local_dates

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


def without_daily_pauses(candles: pd.DataFrame, min_minutes: int, max_minutes: int) -> pd.DataFrame:
    """Troca o close por uma série sem o salto das reaberturas após pausas diárias."""
    pause = candles.datetime.diff().dt.total_seconds().div(60).between(min_minutes, max_minutes)
    step = np.log(candles.close / candles.close.shift())
    # Na vela que reabre depois da pausa, conta só a variação dentro dela (open -> close).
    step = step.where(~pause, np.log(candles.close / candles.open)).fillna(0)
    return candles.assign(close=candles.close.iloc[0] * np.exp(step.cumsum()))


def traded(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Se houve ao menos uma vela aberta depois do início e até o fim de cada intervalo."""
    times = _nanoseconds(candles.datetime)
    after_start = np.searchsorted(times, _nanoseconds(starts), side='right')
    until_end = np.searchsorted(times, _nanoseconds(ends), side='right')
    valid = starts.notna().to_numpy() & ends.notna().to_numpy()
    return pd.Series((until_end > after_start) & valid, index=starts.index)


def realized_vol(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Raiz da soma dos retornos quadráticos de 1 min dentro de cada intervalo."""
    times = _nanoseconds(candles.datetime)
    squared = np.r_[0.0, np.diff(np.log(candles.close.to_numpy())) ** 2].cumsum()
    first = np.searchsorted(times, _nanoseconds(starts), side='right').clip(1)
    last = np.searchsorted(times, _nanoseconds(ends), side='right').clip(1)
    result = pd.Series(np.sqrt(squared[last - 1] - squared[first - 1]), index=starts.index)
    return result.where(starts.notna() & ends.notna())


def session_moments(
    sessions: pd.DataFrame, calendar: pd.DatetimeIndex, cutoff_brt: str,
) -> pd.DataFrame:
    """Instantes de referência de cada pregão, em UTC; sem D-1 nos dados fica vazio."""
    previous = pd.Series(calendar[:-1], index=calendar[1:])
    prev_date = sessions.index.to_series().map(previous)
    hours, minutes = (int(part) for part in cutoff_brt.split(':'))
    cutoff = sessions.index.tz_localize(LOCAL_TIMEZONE) + pd.Timedelta(hours=hours, minutes=minutes)
    return pd.DataFrame(
        {
            'prev_close_utc': prev_date.map(sessions.last_utc),
            'prev2_close_utc': prev_date.map(previous).map(sessions.last_utc),
            'cutoff_utc': cutoff.tz_convert('UTC'),
        },
        index=sessions.index,
    )


def asia_session_return(
    candles: pd.DataFrame, dates: pd.DatetimeIndex, session: dict, max_age: int,
) -> pd.Series:
    """Retorno do pregão asiático de cada data, definido no horário local do mercado."""
    midnight = dates.tz_localize(session['timezone'])
    moments = {}
    for key in ('start', 'end'):
        local_time = midnight + pd.Timedelta(f'{session[key]}:00')
        moments[key] = pd.Series(local_time, index=dates).dt.tz_convert('UTC')
    end = last_price(candles, moments['end'], max_age)
    start = last_price(candles, moments['start'], max_age)
    return (end / start - 1).where(traded(candles, moments['start'], moments['end']))


def external_features(
    name: str, candles: pd.DataFrame, moments: pd.DataFrame, settings: dict,
) -> pd.DataFrame:
    """Retornos e volatilidade de um ativo externo, só com preços até o corte."""
    if name in settings['daily_pause_assets']:
        candles = without_daily_pauses(candles, *settings['daily_pause_minutes'])
    age = settings['max_price_age_minutes']
    cutoff = last_price(candles, moments.cutoff_utc, age)
    previous = last_price(candles, moments.prev_close_utc, age)
    earlier = last_price(candles, moments.prev2_close_utc, age)
    result = pd.DataFrame(index=moments.index)
    result[f'x_pre_{name}_overnight'] = cutoff / previous - 1
    for minutes in settings['recent_windows_minutes']:
        start = moments.cutoff_utc - pd.Timedelta(minutes=minutes)
        result[f'x_pre_{name}_last_{minutes}m'] = cutoff / last_price(candles, start, age) - 1
    result[f'x_pre_{name}_night_vol'] = realized_vol(candles, moments.prev_close_utc, moments.cutoff_utc)
    # Sem nenhuma vela depois do fechamento da B3, o mercado de fora não mediu esta noite.
    result = result.where(traded(candles, moments.prev_close_utc, moments.cutoff_utc), axis=0)
    prev_day = previous / earlier - 1
    result[f'x_pre_{name}_prev_day'] = prev_day.where(
        traded(candles, moments.prev2_close_utc, moments.prev_close_utc)
    )
    if name in settings['asia_sessions']:
        session = settings['asia_sessions'][name]
        result[f'x_pre_{name}_session'] = asia_session_return(candles, moments.index, session, age)
    return result


def target_features(candles: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Histórico do alvo até D-1, medido dentro dos pregões para ignorar a rolagem."""
    daily = candles.groupby(local_dates(candles)).agg(
        open=('open', 'first'),
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
    )
    # shift(1) impede o dia D de entrar na própria variável; removê-lo cria vazamento.
    result = pd.DataFrame(
        {
            'x_pre_target_range_5d': (daily.high / daily.low - 1).rolling(5).mean().shift(1),
            'x_pre_target_return_prev': (daily.close / daily.open - 1).shift(1),
        }
    )
    return result.reindex(dates)


def open_features(
    first_open: pd.Series, prev_close: pd.Series, is_roll_day: pd.Series,
) -> pd.DataFrame:
    """Gap observado: do dia D, só o open do primeiro candle; rolagem o invalida."""
    gap = (first_open / prev_close - 1).where(~is_roll_day)
    return pd.DataFrame({'x_open_gap': gap, 'x_open_gap_abs': gap.abs()})
