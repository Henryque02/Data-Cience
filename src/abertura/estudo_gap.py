"""Estudo da pergunta 1 (gap): compara listas de variáveis e formatos de logística.

Uso: uv run --locked python -m abertura.estudo_gap [--alvo win] [--rodada 1] [--vazios]
     [--formato] [--calibracao] [--recencia]

Para testar uma hipótese, edite RODADAS abaixo: cada rodada tem, por alvo, conjuntos com
nome e lista de variáveis (x_pre_ da tabela diária). O primeiro conjunto de cada alvo é a
referência da coluna "melhora". Rodada 1: a proposta por grupos (GRUPOS) sem cada grupo.
Rodada 2: o núcleo (grupos que fizeram falta) com e sem os grupos fracos. Rodada 3
(padrão): conferência com o Lasso, que escolhe sozinho entre 40 colunas; no fim imprime
em que fração das janelas o Lasso manteve cada variável. As listas da rodada 2 foram
congeladas em 23/11/2026 (VARIAVEIS, em modelo1_gap.py, que reúne o modelo escolhido).

--vazios: com as LISTAS, compara descartar o dia com variável vazia (treino e teste) e
tratar o vazio como zero na entrada do modelo. Mostra o efeito nos dias completos e, nos
dias com vazio, o modelo com zeros contra a frequência histórica. Adotado em 23/11/2026:
vazio vira zero.

--formato: com as LISTAS e o vazio como zero, compara multinomial e dois binários, com o C
fixo (models.logistic_c) e com o C escolhido só no treino de cada janela (validação em
ordem de tempo, 4 cortes, log loss). "melhora" é contra a multinomial com a mesma regra de C.
Fechado em 23/11/2026: dois binários com C = 0,1.

--calibracao: com esse modelo, mede se as probabilidades batem com a frequência observada
(tabela por faixa de probabilidade e erro de calibração, ECE), a AUC de cada classe e a
matriz de confusão. Compara com a multinomial e com o mesmo modelo recalibrado (Platt, ajustado
só no treino de cada janela, em 4 cortes em ordem de tempo).

--recencia: com o modelo fechado, testa formas de acompanhar a mudança na proporção de
dias normais (de cerca de 40% até 2022 para 70% em 2024-2025): treino de 2 anos (atual),
de 18 meses e de 1 ano, e treino de 2 anos com peso maior nos dias recentes (o peso cai à
metade a cada "meia-vida"). Os dias de teste são os mesmos (as janelas de teste do treino
de 2 anos); "melhora" é contra o treino de 2 anos. Mostra o log loss por ano de teste.

Regras da comparação:
- Lê data/processed/daily.parquet; só o período de desenvolvimento (até
  walk_forward.dev_end). Os 12 meses reservados não são lidos.
- Sem dias de rolagem (decisão de 23/11/2026: o rótulo nesses dias mede a troca de
  contrato).
- Nas rodadas, todos os conjuntos de um alvo usam os mesmos dias: sai o dia em que qualquer variável
  de qualquer conjunto está vazia. A linha "dias" mostra quantos sobraram no teste.
- Walk-forward de e05_validacao (2 anos de treino, 3 meses de teste, avança 3 meses). A
  escala das variáveis é ajustada só no treino de cada janela.
- Dois formatos de regressão logística, com a mesma regularização (models.logistic_c):
  multinomial (um modelo, três probabilidades) e dois binários (alta contra o resto e
  baixa contra o resto; normal é o que sobra, e as três são reescaladas para somar 1).
- Conjuntos marcados com Lasso usam penalidade L1, que zera variáveis; a força da
  penalidade é escolhida só no treino de cada janela, por validação em ordem de tempo
  (4 cortes, log loss).
- Métricas fora da amostra: log loss (principal), acerto, acerto balanceado e Brier.
  "melhora" é a queda média do log loss por dia em relação ao primeiro conjunto no mesmo
  formato, com o erro padrão; melhora menor que duas vezes o erro não se distingue de
  acaso.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .e05_validacao import (
    CLASSES, baseline_model, calibration_error, confusion, daily_loss, reliability, scores,
    walk_forward_predict, walk_forward_windows,
)
from .modelo1_gap import VARIAVEIS, TwoBinary

PROJECT = Path(__file__).resolve().parents[2]
TARGET = 'y_gap_class'
ORDER = CLASSES[TARGET]


def overnight(*assets: str) -> list[str]:
    """Colunas de retorno da madrugada dos ativos."""
    return [f'x_pre_{asset}_overnight' for asset in assets]


def night_vol(*assets: str) -> list[str]:
    """Colunas de volatilidade da madrugada dos ativos."""
    return [f'x_pre_{asset}_night_vol' for asset in assets]


TARGET_HISTORY = ['x_pre_target_range_5d', 'x_pre_target_close_position']
# Todos os externos menos o Hang Seng, que tem 118 dias vazios no período.
ASSETS_19 = (
    'spx', 'ndx', 'sx5e', 'ftse', 'nikkei', 'a50', 'brent', 'gold', 'dxy', 'usdmxn',
    'copper', 'eurusd', 'usdjpy', 'usdzar', 'usdcnh', 'usdchf', 'audusd', 'btcusd', 'ethusd',
)
ALL_19 = overnight(*ASSETS_19)
ALL_40 = ALL_19 + night_vol(*ASSETS_19) + TARGET_HISTORY


class Lasso(list):
    """Lista de variáveis entregue ao Lasso, que escolhe quais usar dentro do treino."""

# Proposta de cada alvo, em grupos com motivo econômico. Em pares quase repetidos
# (correlação acima de 0,7 entre si) fica um representante: o mais ligado ao gap ou, no
# empate, o com menos dias vazios (S&P em vez de Nasdaq; DXY em vez de EUR/USD e USD/CHF;
# A50 em vez de Hang Seng, que tem 118 dias vazios; Ether em vez de Bitcoin).
GRUPOS = {
    'win': {
        'bolsas EUA': overnight('spx'),              # o gap do WIN segue o S&P (0,70)
        'bolsa Europa': overnight('sx5e'),           # negocia nas horas antes das 09:00 (0,67)
        'bolsa Japão': overnight('nikkei'),          # madrugada asiática (0,49)
        'bolsa China': overnight('a50'),             # China, principal compradora do Brasil (0,36)
        'moedas emergentes': overnight('usdmxn', 'audusd', 'usdzar'),  # apetite por risco emergente
        'commodities': overnight('copper', 'brent'),  # Vale e Petrobras pesam no índice
        'dólar global': overnight('dxy'),            # dólar forte costuma pesar em bolsa
        'cripto': overnight('ethusd'),               # apetite por risco, inclusive no fim de semana
        'agitação da madrugada': night_vol('sx5e'),  # noite agitada, gap maior (tamanho, não direção)
        'histórico do alvo': TARGET_HISTORY,         # agitação da B3 e devolução do fechamento de D-1
    },
    'wdo': {
        'dólar global': overnight('dxy'),            # força do dólar no mundo (0,50)
        'moedas emergentes': overnight('usdmxn', 'audusd', 'usdzar', 'usdcnh'),  # pares do real (0,41 a 0,69)
        'bolsas EUA': overnight('spx'),              # bolsa em queda, dólar em alta (−0,52)
        'commodities': overnight('copper'),          # exportações brasileiras (−0,41)
        'bolsa Japão': overnight('nikkei'),          # madrugada asiática (−0,34)
        'cripto': overnight('ethusd'),               # apetite por risco (−0,26)
        'agitação da madrugada': night_vol('sx5e'),  # tamanho do gap
        'histórico do alvo': TARGET_HISTORY,         # não ajudou o WDO em 23/11; fica para confirmar
    },
}


def proposal_sets(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """A proposta completa, a proposta sem cada grupo e, para comparar, os 19 ativos."""
    full = [name for features in groups.values() for name in features]
    sets = {'proposta completa': full}
    sets |= {f'sem {group}': [name for name in full if name not in features] for group, features in groups.items()}
    sets['19 overnight + agitação + histórico'] = ALL_19 + night_vol('sx5e') + TARGET_HISTORY
    return sets


# Rodada 2: grupos que fizeram falta na rodada 1 (núcleo) e os que ficaram dentro do acaso
# (fracos). Os fracos se cobrem entre si, então entram juntos e um de cada vez.
NUCLEO = {
    'win': ['bolsas EUA', 'moedas emergentes', 'histórico do alvo'],
    'wdo': ['dólar global', 'moedas emergentes'],
}
FRACOS = {
    'win': ['bolsa Europa', 'bolsa Japão', 'bolsa China', 'commodities'],
    'wdo': ['bolsas EUA', 'commodities', 'agitação da madrugada', 'histórico do alvo'],
}


def core_sets(groups: dict[str, list[str]], core: list[str], weak: list[str]) -> dict[str, list[str]]:
    """O núcleo, o núcleo com todos os fracos, com cada fraco e a proposta completa."""
    pick = lambda names: [column for name in names for column in groups[name]]
    sets = {'núcleo': pick(core), 'núcleo + todos os fracos': pick(core + weak)}
    sets |= {f'núcleo + {name}': pick(core + [name]) for name in weak}
    sets['proposta completa (rodada 1)'] = pick(list(groups))
    return sets


# Listas da pergunta 1, congeladas em 23/11/2026 (VARIAVEIS, em modelo1_gap.py): o núcleo
# com todos os fracos (rodada 2), conferidas pelo Lasso (rodada 3).
LISTAS = VARIAVEIS


def lasso_sets(chosen: list[str]) -> dict[str, list[str]]:
    """A lista da rodada 2, o Lasso nas 40 colunas e as 40 sem seleção (controle)."""
    return {
        'lista da rodada 2': chosen,
        'Lasso: 40 colunas': Lasso(ALL_40),
        '40 colunas sem seleção': ALL_40,
    }


# Hipóteses a testar. O primeiro conjunto de cada alvo é a referência.
# Rodada 1: nas linhas "sem <grupo>", melhora negativa (maior que duas vezes o erro) quer
# dizer que o grupo faz falta. Rodada 2: nas linhas "núcleo + ...", melhora positiva maior
# que duas vezes o erro quer dizer que o acréscimo ajuda. Rodada 3: o Lasso confirma a
# lista se ficar perto dela no log loss e mantiver variáveis parecidas.
RODADAS = {
    1: {asset: proposal_sets(groups) for asset, groups in GRUPOS.items()},
    2: {asset: core_sets(groups, NUCLEO[asset], FRACOS[asset]) for asset, groups in GRUPOS.items()},
    3: {asset: lasso_sets(LISTAS[asset]) for asset in GRUPOS},
}


def logistic(c: float | None, l1: bool = False):
    """Logística com escala ajustada no treino.

    Com c=None (L2) ou com l1 (Lasso), a força da penalidade é escolhida só no treino.
    """
    if c is not None and not l1:
        return make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=2000))
    if l1:
        options = {'Cs': np.logspace(-2.5, 0.5, 13), 'l1_ratios': [1.0], 'solver': 'saga', 'max_iter': 5000}
    else:
        options = {'Cs': np.logspace(-3, 1, 13), 'l1_ratios': [0.0], 'max_iter': 2000}
    tuned = LogisticRegressionCV(
        cv=TimeSeriesSplit(4), scoring='neg_log_loss', use_legacy_attributes=False, **options,
    )
    return make_pipeline(StandardScaler(), tuned)


def formats(c: float | None, l1: bool) -> dict:
    """Os formatos de logística comparados, com a mesma regularização."""
    return {'multinomial': lambda: logistic(c, l1), 'dois binários': lambda: TwoBinary(logistic(c, l1))}


def kept(model) -> np.ndarray:
    """Variáveis com coeficiente diferente de zero em algum lado do modelo."""
    parts = model.models_.values() if isinstance(model, TwoBinary) else [model]
    return np.any([part[-1].coef_ != 0 for part in parts], axis=(0, 1))


def load(asset: str, params: dict, features: list[str]) -> pd.DataFrame:
    """Dias do alvo no desenvolvimento, sem rolagem e com todas as variáveis preenchidas."""
    daily = pd.read_parquet(PROJECT / 'data/processed/daily.parquet')
    table = daily[daily.asset == asset].set_index('date_brt').sort_index()
    table = table[(table.index <= params['walk_forward']['dev_end']) & ~table.is_roll_day]
    return table.dropna(subset=[TARGET, *features])


def summary(losses: pd.Series, reference: pd.Series, predictions: pd.DataFrame) -> dict:
    """Log loss, melhora contra a referência (com erro padrão) e acerto nos mesmos dias."""
    difference = reference - losses
    hits = predictions.y_true.eq(predictions.y_pred)
    return {
        'dias': len(losses), 'log loss': losses.mean(), 'melhora': difference.mean(),
        'erro': difference.std() / np.sqrt(len(difference)), 'acerto': hits.mean(),
    }


# Variantes de treino do estudo de recência: (meses de treino, meia-vida do peso em meses).
RECENCIA = {
    '2 anos (atual)': (24, None),
    '18 meses': (18, None),
    '1 ano': (12, None),
    '2 anos, meia-vida de 1 ano': (24, 12),
    '2 anos, meia-vida de 6 meses': (24, 6),
}


def recency_predict(table: pd.DataFrame, features: list[str], c: float, months: int,
                    half_life: int | None, windows: list) -> pd.DataFrame:
    """Walk-forward com treino de `months` meses antes de cada teste e peso por recência."""
    results = []
    for _, test_start, test_end in windows:
        train = table[(table.index >= test_start - pd.DateOffset(months=months)) & (table.index < test_start)]
        test = table[(table.index >= test_start) & (table.index < test_end)]
        weight = None
        if half_life is not None:
            age = (test_start - train.index).days / 30.4375
            weight = 0.5 ** (age / half_life)
        weights = {} if weight is None else {'logisticregression__sample_weight': weight}
        model = TwoBinary(logistic(c)).fit(train[features], train[TARGET], **weights)
        probabilities = pd.DataFrame(model.predict_proba(test[features]), index=test.index, columns=ORDER)
        results.append(probabilities.assign(y_true=test[TARGET], y_pred=probabilities.idxmax(axis=1)))
    return pd.concat(results)


def recency_study(asset: str, params: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Treino de 2 anos contra treinos mais curtos e com peso nos dias recentes."""
    features = LISTAS[asset]
    table = load(asset, params, []).fillna(dict.fromkeys(features, 0.0))
    walk = params['walk_forward']
    windows = walk_forward_windows(table.index, walk['train_years'], walk['test_months'], walk['step_months'])
    rows, by_year, reference = {}, {}, None
    for name, (months, half_life) in RECENCIA.items():
        predictions = recency_predict(table, features, params['models']['logistic_c'], months, half_life, windows)
        losses = daily_loss(predictions)
        reference = losses if reference is None else reference
        difference = reference - losses
        observed = predictions.y_true.eq('normal')
        rows[name] = scores(predictions, ORDER) | {
            'melhora': difference.mean(), 'erro': difference.std() / np.sqrt(len(difference)),
            'ECE': calibration_error(predictions, ORDER),
            'normal previsto': predictions.normal.mean(), 'normal real': observed.mean(),
        }
        by_year[name] = losses.groupby(losses.index.year).mean()
    result = pd.DataFrame(rows).T.rename(columns={'n': 'dias', 'log_loss': 'log loss', 'accuracy': 'acerto'})
    result['dias'] = result.dias.astype(int)
    columns = ['dias', 'log loss', 'melhora', 'erro', 'ECE', 'acerto', 'normal previsto', 'normal real']
    years = pd.DataFrame(by_year).T
    years.columns.name = 'log loss por ano de teste'
    return result[columns], years


def walk_options(params: dict) -> dict:
    """Opções do walk-forward lidas de config/params.yaml."""
    walk = params['walk_forward']
    return {key: walk[key] for key in ('train_years', 'test_months', 'step_months')}


def chosen_c(model) -> list[float]:
    """C escolhido no treino por cada logística do modelo."""
    parts = model.models_.values() if isinstance(model, TwoBinary) else [model]
    return [part[-1].C_ for part in parts]


def calibration_study(asset: str, params: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Calibração, AUC e matriz de confusão do modelo fechado, contra multinomial e Platt."""
    features = LISTAS[asset]
    table = load(asset, params, []).fillna(dict.fromkeys(features, 0.0))
    options = walk_options(params)
    c = params['models']['logistic_c']
    models = {
        'dois binários (modelo)': lambda: TwoBinary(logistic(c)),
        'multinomial': lambda: logistic(c),
        'dois binários + Platt': lambda: CalibratedClassifierCV(TwoBinary(logistic(c)), method='sigmoid', cv=TimeSeriesSplit(4)),
        'frequência histórica': baseline_model,
    }
    rows, results = {}, {}
    for name, make_model in models.items():
        predictions = walk_forward_predict(table, TARGET, features, make_model, **options)
        results[name] = predictions
        losses = daily_loss(predictions)
        reference = daily_loss(results['dois binários (modelo)'])
        difference = reference - losses
        rows[name] = scores(predictions, ORDER) | {
            'melhora': difference.mean(), 'erro': difference.std() / np.sqrt(len(difference)),
            'ECE': calibration_error(predictions, ORDER),
        } | {f'AUC {k}': roc_auc_score(predictions.y_true.eq(k), predictions[k]) for k in ORDER}
    summary_table = pd.DataFrame(rows).T.rename(columns={'n': 'dias', 'log_loss': 'log loss', 'accuracy': 'acerto'})
    summary_table['dias'] = summary_table.dias.astype(int)
    summary_table = summary_table[['dias', 'log loss', 'melhora', 'erro', 'brier', 'ECE', 'acerto', *[f'AUC {k}' for k in ORDER]]]
    main_model = results['dois binários (modelo)']
    return summary_table, reliability(main_model, ORDER), confusion(main_model, ORDER)


def format_study(asset: str, params: dict) -> pd.DataFrame:
    """Multinomial contra dois binários, com C fixo e com C escolhido no treino."""
    features = LISTAS[asset]
    table = load(asset, params, []).fillna(dict.fromkeys(features, 0.0))
    options = walk_options(params)
    frequency = walk_forward_predict(table, TARGET, features, baseline_model, **options)
    rows = {('frequência histórica', '-'): scores(frequency, ORDER) | {'melhora': np.nan, 'erro': np.nan, 'C (mediana)': np.nan}}
    for rule, c in (('C fixo', params['models']['logistic_c']), ('C no treino', None)):
        reference = None
        for model_name, factory in formats(c, False).items():
            fitted = []
            make_model = lambda: fitted.append(factory()) or fitted[-1]
            predictions = walk_forward_predict(table, TARGET, features, make_model, **options)
            losses = daily_loss(predictions)
            reference = losses if reference is None else reference
            difference = reference - losses
            median_c = np.median([v for m in fitted for v in chosen_c(m)]) if c is None else c
            rows[(rule, model_name)] = scores(predictions, ORDER) | {
                'melhora': difference.mean(), 'erro': difference.std() / np.sqrt(len(difference)),
                'C (mediana)': median_c,
            }
    result = pd.DataFrame(rows).T.rename(columns={
        'n': 'dias', 'log_loss': 'log loss', 'accuracy': 'acerto', 'balanced_accuracy': 'acerto balanc.',
    })
    result['dias'] = result.dias.astype(int)
    result.index.names = ['regra do C', 'formato']
    return result[['dias', 'log loss', 'melhora', 'erro', 'acerto', 'acerto balanc.', 'brier', 'C (mediana)']]


def empty_days(asset: str, params: dict) -> tuple[pd.DataFrame, pd.Series]:
    """Descartar o dia com variável vazia contra tratar o vazio como zero, com as LISTAS."""
    features = LISTAS[asset]
    table = load(asset, params, [])
    zero = table.fillna(dict.fromkeys(features, 0.0))
    empty = table[features].isna().any(axis=1)
    options = walk_options(params)
    frequency = walk_forward_predict(zero, TARGET, features, baseline_model, **options)
    rows = {}
    for model_name, make_model in formats(params['models']['logistic_c'], False).items():
        dropped = walk_forward_predict(table, TARGET, features, make_model, **options)
        zeros = walk_forward_predict(zero, TARGET, features, make_model, **options)
        full = dropped.index
        rows[('dias completos', 'descarta (referência)', model_name)] = summary(
            daily_loss(dropped), daily_loss(dropped), dropped)
        rows[('dias completos', 'vazio vira zero', model_name)] = summary(
            daily_loss(zeros.loc[full]), daily_loss(dropped), zeros.loc[full])
        gaps = zeros.index[empty.reindex(zeros.index)]
        rows[('dias com vazio', 'frequência (referência)', model_name)] = summary(
            daily_loss(frequency.loc[gaps]), daily_loss(frequency.loc[gaps]), frequency.loc[gaps])
        rows[('dias com vazio', 'vazio vira zero', model_name)] = summary(
            daily_loss(zeros.loc[gaps]), daily_loss(frequency.loc[gaps]), zeros.loc[gaps])
    result = pd.DataFrame(rows).T
    result['dias'] = result.dias.astype(int)
    result.index.names = ['dias de teste', 'tratamento', 'formato']
    tested = empty.loc[frequency.index]
    count = table.loc[tested.index, features].isna().sum()
    return result, count[count > 0].sort_values(ascending=False)


def compare(asset: str, params: dict, sets: dict[str, list[str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Avalia cada conjunto em cada formato, nos mesmos dias.

    Devolve as métricas e, para conjuntos do Lasso, a fração das janelas em que cada
    variável ficou com coeficiente diferente de zero.
    """
    table = load(asset, params, sorted({name for features in sets.values() for name in features}))
    options = walk_options(params)
    first = next(iter(sets.values()))
    frequency = walk_forward_predict(table, TARGET, first, baseline_model, **options)
    rows = {('frequência histórica', '-'): scores(frequency, ORDER) | {'melhora': np.nan, 'erro': np.nan}}
    choices = {}
    for model_name in ('multinomial', 'dois binários'):
        reference = None
        for set_name, features in sets.items():
            factory = formats(params['models']['logistic_c'], isinstance(features, Lasso))[model_name]
            fitted = []
            make_model = lambda: fitted.append(factory()) or fitted[-1]
            predictions = walk_forward_predict(table, TARGET, list(features), make_model, **options)
            if isinstance(features, Lasso):
                choices[(set_name, model_name)] = np.mean([kept(model) for model in fitted], axis=0)
            losses = daily_loss(predictions)
            reference = losses if reference is None else reference
            difference = reference - losses
            rows[(set_name, model_name)] = scores(predictions, ORDER) | {
                'melhora': difference.mean(), 'erro': difference.std() / np.sqrt(len(difference)),
            }
    result = pd.DataFrame(rows).T.rename(columns={
        'n': 'dias', 'log_loss': 'log loss', 'accuracy': 'acerto',
        'balanced_accuracy': 'acerto balanc.',
    })
    result['dias'] = result.dias.astype(int)
    result.index.names = ['conjunto', 'formato']
    lasso = pd.DataFrame({key: pd.Series(value, index=list(sets[key[0]])) for key, value in choices.items()})
    return result[['dias', 'log loss', 'melhora', 'erro', 'acerto', 'acerto balanc.', 'brier']], lasso


def main(argv: list[str] | None = None) -> int:
    """Imprime a comparação de cada alvo."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--alvo', choices=list(GRUPOS), nargs='+', default=list(GRUPOS))
    parser.add_argument('--rodada', type=int, choices=list(RODADAS), default=max(RODADAS))
    parser.add_argument('--vazios', action='store_true', help='estudo dos dias com variável vazia')
    parser.add_argument('--formato', action='store_true', help='multinomial contra dois binários')
    parser.add_argument('--calibracao', action='store_true', help='calibração e matriz de confusão do modelo')
    parser.add_argument('--recencia', action='store_true', help='treinos mais curtos e peso nos dias recentes')
    args = parser.parse_args(argv)
    params = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    pd.set_option('display.width', 250, 'display.float_format', '{:.4f}'.format)
    for asset in args.alvo:
        if args.recencia:
            print(f'\n== {asset.upper()} · recência do treino (desenvolvimento, sem rolagem, vazio vira zero)')
            result, years = recency_study(asset, params)
            print(result.to_string())
            print('\n' + years.to_string())
            continue
        if args.calibracao:
            print(f'\n== {asset.upper()} · calibração (desenvolvimento, sem rolagem, vazio vira zero)')
            summary_table, table, matrix = calibration_study(asset, params)
            print(summary_table.to_string())
            print('\nProbabilidade prevista x frequência observada (modelo):\n' + table.to_string())
            print('\nMatriz de confusão (modelo; linhas: real, colunas: previsto):\n' + matrix.to_string())
            continue
        if args.formato:
            print(f'\n== {asset.upper()} · formato (desenvolvimento, sem rolagem, vazio vira zero)')
            print(format_study(asset, params).to_string())
            continue
        if args.vazios:
            print(f'\n== {asset.upper()} · dias com variável vazia (desenvolvimento, sem rolagem)')
            result, count = empty_days(asset, params)
            print(result.to_string())
            print('\nDias de teste com a variável vazia:\n' + count.to_string())
            continue
        print(f'\n== {asset.upper()} · rodada {args.rodada} (desenvolvimento, sem rolagem)')
        result, lasso = compare(asset, params, RODADAS[args.rodada][asset])
        print(result.to_string())
        if not lasso.empty:
            print('\nFração das janelas em que o Lasso manteve a variável (só as mantidas):')
            lasso = lasso[lasso.max(axis=1) > 0]
            print(lasso.sort_values(lasso.columns[-1], ascending=False).to_string())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
