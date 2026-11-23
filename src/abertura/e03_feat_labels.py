"""Variáveis (x_) e rótulos (y_) de cada pregão: tudo o que vira coluna da tabela diária.

Não tem comando próprio: quem chama é o e04_daily.py. A separação entre o que pode e o
que não pode entrar no modelo está no prefixo das colunas, conferido por
e05_validacao.check_features: x_pre_ é conhecido antes da abertura, x_open_ na abertura e
y_ só depois (AGENTS.md, seção 3.2).

Antes da abertura (x_pre_)

- last_price dá o último close com vela aberta até um instante. No corte das 08:58 a
  vela das 08:58 entra (fecha às 08:59).

- traded diz se o ativo teve alguma vela dentro de um intervalo. Cada variável externa só
  existe se o ativo negociou no intervalo que ela mede; senão fica vazia. Assim um feriado
  lá fora na madrugada não vira retorno zero. Se negociou e parou (pane da bolsa), vale o
  último preço.

- price_age diz há quanto tempo foi a última vela até um instante. O preço de partida do
  overnight (no fechamento da B3 em D-1) precisa ter no máximo max_start_age_hours (24 h);
  mais velho que isso, o mercado de fora ficou parado o dia D-1 inteiro (feriado lá), e
  a variável fica vazia. Sem essa regra, o overnight do dia seguinte ao feriado somava
  vários dias que a B3 já tinha negociado (Hang Seng no Ano-Novo Chinês de 2023: partia
  do preço de 5 dias antes). Em 2020-2026 as idades no fechamento da B3 ficam até 18 h ou
  acima de 24 h, sem nenhum caso entre 18 e 24 h; acima de 24 h são 105 noites (Hang Seng
  57, A50 13, FTSE 10, Europe 50 8, os demais 2 ou 3). Fim de semana e feriado só da B3
  não disparam a regra: D-1 é o pregão anterior, e o preço de fora nesse dia é recente.

- session_moments calcula, para cada pregão D, o horário do fechamento do alvo em D-1 e
  o corte de D às 08:58. Na Quarta-feira de Cinzas, que abre às 13:00, o corte vai para
  12:58 (special_cutoff_brt); o dia vem do calendário da B3, conhecido antes. Se o alvo
  não tem D-1 nos dados, as variáveis externas ficam vazias.

- without_roll_jumps tira dos CFDs de Brent e cobre o salto da troca de contrato
  (decisão de 17/11/2026). A troca acontece numa reabertura depois da pausa diária, e
  nessa noite a pausa fica mais longa (roll_pause_minutes: Brent 200-201 min em vez de
  181; cobre 80-81 em vez de 61). Na vela da reabertura conta só o que ela andou
  (abertura -> fechamento), sem a diferença para o fechamento antes da pausa. Perde o
  movimento real durante a pausa, em média 0,2% no Brent. Vale para overnight e
  night_vol. Trocas com salto pequeno podem não alongar a pausa e passar sem correção.

- external_features cria, por ativo externo, overnight (retorno do fechamento da B3 em
  D-1 até 08:58), o sinal principal do gap, e night_vol (o quanto o preço sacudiu nesse
  mesmo intervalo). As duas exigem negociação depois do fechamento da B3. Retornos da
  última 1h e 3h, do dia anterior lá fora e do pregão asiático foram cortados: eram
  pedaços do overnight ou não tinham relação com o gap.

- target_features cria, com o próprio alvo, a amplitude média dos 5 pregões anteriores e
  a posição do fechamento de D-1 entre a mínima (0) e a máxima (1) do dia; medidas
  dentro do pregão, não incluem a rolagem. O retorno do pregão anterior saiu em
  17/11/2026: a posição do fechamento mede o mesmo efeito e foi mais forte no estudo. O
  primeiro dia do histórico não entra, porque pode ser parcial (o arquivo do professor
  começa às 11:49 de 15/10/2020): as medidas que dependeriam dele ficam vazias.

O gap (x_open_ e y_gap)

- open_features calcula o gap (abertura da 1ª vela de D / fechamento de D-1 - 1) e seu
  tamanho sem sinal, inclusive em dia de rolagem, sem ajuste entre contratos. Nas
  perguntas 2 e 3 o gap já aconteceu e é variável (x_open_gap); na pergunta 1 ele é a
  resposta e aparece, com o mesmo valor, como y_gap.

Depois da abertura (y_)

- opening_window resume a janela de 60 min a partir da primeira vela de D: abertura,
  máxima, mínima e fechamento, usando apenas as velas disponíveis, mesmo com buracos.
- gap_class classifica o gap em alta, baixa ou normal pelo limiar de cada alvo
  (labels.gap_threshold: 0,30% no WIN e 0,25% no WDO). É o rótulo da pergunta 1, a
  classificação pedida no quadro do professor. Gap exatamente no limiar é normal; sem
  fechamento anterior, o rótulo fica vazio.
- behavior só existe em dia de gap de alta ou de baixa (mesmo limiar). Reversão: o preço
  toca o fechamento de D-1 na janela. Tendência: a janela fecha mais de 0,1% além da
  abertura, na direção do gap. Senão, lateral. Reversão tem prioridade, mesmo se o dia
  também terminar a favor. Sem fechamento anterior, vazio.
- range_labels mede a máxima e a mínima da janela em relação à abertura (faixa).
- labels junta y_gap, y_gap_class e y_behavior.

Conferência contra vazamento (AGENTS.md, seção 3.2), num dia real: alterar preços
externos depois das 08:58 (12:58 na Cinzas) ou velas do alvo no dia D não pode mudar as
x_pre_ de D; alterar o close externo das 08:58 muda o overnight. Alterar máxima, mínima,
fechamento ou volume da 1ª vela de D, ou as velas seguintes, não pode mudar o gap;
alterar a abertura da 1ª vela muda.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .e02_tratamento import LOCAL_TIMEZONE, local_dates


def last_price(candles: pd.DataFrame, moments: pd.Series) -> pd.Series:
    """Último close com candle aberto até cada instante; sem instante ou sem vela, NaN."""
    # side='right' inclui o candle aberto no instante; 'left' perderia o candle das 08:58.
    position = candles.datetime.searchsorted(moments, side='right') - 1
    prices = candles.close.to_numpy()[position.clip(0)].astype(float)
    prices[moments.isna().to_numpy() | (position < 0)] = np.nan
    return pd.Series(prices, index=moments.index)


def price_age(candles: pd.DataFrame, moments: pd.Series) -> pd.Series:
    """Tempo desde a última vela aberta até cada instante; sem vela, NaT."""
    position = candles.datetime.searchsorted(moments, side='right') - 1
    age = pd.Series(moments.array - candles.datetime.array[position.clip(0)], index=moments.index)
    return age.where(position >= 0)


def traded(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Se houve ao menos uma vela aberta depois do início e até o fim de cada intervalo."""
    after_start = candles.datetime.searchsorted(starts, side='right')
    until_end = candles.datetime.searchsorted(ends, side='right')
    valid = starts.notna().to_numpy() & ends.notna().to_numpy()
    return pd.Series((until_end > after_start) & valid, index=starts.index)


def without_roll_jumps(candles: pd.DataFrame, pauses: list[int]) -> pd.DataFrame:
    """Refaz o close somando só a variação dentro de cada contrato."""
    reopening = candles.datetime.diff().dt.total_seconds().div(60).round().isin(pauses)
    step = np.log(candles.close / candles.close.shift())
    # Na vela que reabre depois da pausa da troca conta só o que ela andou (open -> close).
    step = step.where(~reopening, np.log(candles.close / candles.open)).fillna(0)
    return candles.assign(close=candles.close.iloc[0] * np.exp(step.cumsum()))


def realized_vol(candles: pd.DataFrame, starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Raiz da soma dos retornos quadráticos de 1 min dentro de cada intervalo."""
    squared = np.r_[0.0, np.diff(np.log(candles.close.to_numpy())) ** 2].cumsum()
    first = candles.datetime.searchsorted(starts, side='right').clip(1)
    last = candles.datetime.searchsorted(ends, side='right').clip(1)
    total = pd.Series(squared[last - 1] - squared[first - 1], index=starts.index)
    return np.sqrt(total.where(starts.notna() & ends.notna()))


def _at_brt(dates: pd.DatetimeIndex, time_brt: str) -> pd.Series:
    """Instante UTC de um horário de Brasília ('HH:MM') em cada data."""
    local = dates.tz_localize(LOCAL_TIMEZONE) + pd.to_timedelta(f'{time_brt}:00')
    return pd.Series(local.tz_convert('UTC'), index=dates)


def session_moments(
    sessions: pd.DataFrame, calendar: pd.DatetimeIndex, cutoff_brt: str, special_cutoff_brt: str,
) -> pd.DataFrame:
    """Instantes de referência de cada pregão, em UTC; sem D-1 nos dados fica vazio."""
    previous = pd.Series(calendar[:-1], index=calendar[1:])
    prev_date = sessions.index.to_series().map(previous)
    # A Cinzas vem do calendário da B3, publicado antes do dia: não há vazamento.
    cutoff = _at_brt(sessions.index, cutoff_brt).mask(
        sessions.is_special_open, _at_brt(sessions.index, special_cutoff_brt),
    )
    return pd.DataFrame(
        {'prev_close_utc': prev_date.map(sessions.last_utc), 'cutoff_utc': cutoff},
        index=sessions.index,
    )


def external_features(
    name: str, candles: pd.DataFrame, moments: pd.DataFrame, settings: dict,
) -> pd.DataFrame:
    """Retorno e volatilidade de um ativo externo, do fechamento da B3 até o corte."""
    cutoff = last_price(candles, moments.cutoff_utc)
    previous = last_price(candles, moments.prev_close_utc)
    result = pd.DataFrame(
        {
            f'x_pre_{name}_overnight': cutoff / previous - 1,
            f'x_pre_{name}_night_vol': realized_vol(candles, moments.prev_close_utc, moments.cutoff_utc),
        }
    )
    # Sem nenhuma vela depois do fechamento da B3, o mercado de fora não mediu esta noite;
    # com preço de partida velho, ficou parado em D-1 e a noite somaria dias já vistos.
    fresh = price_age(candles, moments.prev_close_utc) <= pd.Timedelta(hours=settings['max_start_age_hours'])
    return result.where(traded(candles, moments.prev_close_utc, moments.cutoff_utc) & fresh, axis=0)


def target_features(candles: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Histórico do alvo até D-1, medido dentro dos pregões para ignorar a rolagem."""
    daily = candles.groupby(local_dates(candles)).agg(
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
    ).iloc[1:]  # O 1º dia do histórico pode ser parcial (WIN: 15/10/2020 desde 11:49).
    # shift(1) impede o dia D de entrar na própria variável; removê-lo cria vazamento.
    result = pd.DataFrame(
        {
            'x_pre_target_range_5d': (daily.high / daily.low - 1).rolling(5).mean().shift(1),
            'x_pre_target_close_position': ((daily.close - daily.low) / (daily.high - daily.low)).shift(1),
        }
    )
    return result.reindex(dates)


def open_features(first_open: pd.Series, prev_close: pd.Series) -> pd.DataFrame:
    """Gap observado, inclusive na rolagem: do dia D, só o open do primeiro candle."""
    gap = first_open / prev_close - 1
    return pd.DataFrame({'x_open_gap': gap, 'x_open_gap_abs': gap.abs()})


def opening_window(candles: pd.DataFrame, sessions: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Resume cada pregão na janela que começa no primeiro candle observado."""
    dates = local_dates(candles)
    inside = candles.datetime < dates.map(sessions.first_utc) + pd.Timedelta(minutes=minutes)
    return candles[inside].groupby(dates[inside]).agg(
        open=('open', 'first'),
        high=('high', 'max'),
        low=('low', 'min'),
        close=('close', 'last'),
    )


def gap_class(gap: pd.Series, threshold: float) -> pd.Series:
    """Classifica o gap; sem gap válido o rótulo fica ausente."""
    labels = pd.Series('normal', index=gap.index, dtype='object')
    labels[gap > threshold] = 'alta'
    labels[gap < -threshold] = 'baixa'
    return labels.where(gap.notna())


def behavior(
    window: pd.DataFrame, prev_close: pd.Series, gap: pd.Series, threshold: float,
    trend_margin: float,
) -> pd.Series:
    """Só existe em dia com gap relevante; reversão tem prioridade sobre tendência."""
    # Gap exatamente no limiar não conta; gap ausente compara como falso.
    up, down = gap > threshold, gap < -threshold
    move = window.close / window.open - 1
    aligned_move = move.where(up, -move)
    touched = (up & window.low.le(prev_close)) | (down & window.high.ge(prev_close))
    labels = pd.Series('lateral', index=window.index, dtype='object')
    labels[aligned_move > trend_margin] = 'tendencia'
    # A ordem define a prioridade: inverter estas linhas muda o rótulo de dias que fazem os dois.
    labels[touched] = 'reversao'
    return labels.where(up | down)


def range_labels(window: pd.DataFrame) -> pd.DataFrame:
    """Máxima e mínima da janela relativas à abertura."""
    return pd.DataFrame(
        {
            'y_range_high': window.high / window.open - 1,
            'y_range_low': window.low / window.open - 1,
        }
    )


def labels(
    window: pd.DataFrame, prev_close: pd.Series, gap: pd.Series, threshold: float,
    trend_margin: float,
) -> pd.DataFrame:
    """Gap e sua classe (pergunta 1) e comportamento na janela de abertura (pergunta 2)."""
    return pd.DataFrame(
        {
            # Mesmo valor de x_open_gap: aqui é a resposta da pergunta 1; lá, variável das 2 e 3.
            'y_gap': gap,
            'y_gap_class': gap_class(gap, threshold),
            'y_behavior': behavior(window, prev_close, gap, threshold, trend_margin),
        }
    )
