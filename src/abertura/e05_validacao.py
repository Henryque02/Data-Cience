"""Validação comum às perguntas: regra contra vazamento, walk-forward e métricas.

Não tem comando próprio: os modelos (modeloN_*.py) e os estudos (estudo_*.py) chamam estas
funções. O que é de cada pergunta (variáveis, preparo dos dados, formato do modelo) fica
no arquivo do modelo; aqui fica só o que vale igual para todas.

- check_features bloqueia variáveis proibidas (prefixos definidos em e03_feat_labels.py):
  para prever o gap (pergunta 1) só entram x_pre_; para o comportamento (pergunta 2),
  x_pre_ e x_open_. Rótulos y_ nunca entram.
- baseline_model prevê a frequência de cada classe no treino: é a referência mínima.
- Janelas (início do treino, início do teste, fim do teste), sem embaralhar datas:
  walk_forward_windows (desenvolvimento) treina com 2 anos e testa nos 3 meses seguintes,
  avançando de 3 em 3, a partir de 2 anos depois do primeiro dia; final_windows faz o
  mesmo nos 12 meses reservados, a partir do dia seguinte a walk_forward.dev_end.
- predict treina um modelo novo em cada janela, só com o passado, e devolve as
  probabilidades fora da amostra; classe que não apareceu no treino recebe zero.
  walk_forward_predict (usado nos estudos) tira antes as linhas com variável ausente.
- Métricas: scores (acerto, acerto balanceado, log loss, Brier), daily_loss (log loss de
  cada dia, para a melhora com erro padrão), reliability e calibration_error (prevista
  contra observada por faixa de probabilidade; ECE), evaluate (tudo isso, com a AUC de
  cada classe, contra a frequência histórica) e confusion (matriz de confusão).

Conferência contra vazamento (AGENTS.md, seção 3.2): check_features recusa x_open_ na
pergunta 1 e qualquer y_; em cada janela o treino termina antes do primeiro dia de teste.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import confusion_matrix, log_loss, roc_auc_score

CLASSES = {
    'y_gap_class': ['baixa', 'normal', 'alta'],
    'y_behavior': ['tendencia', 'reversao', 'lateral'],
}

Windows = list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]


def check_features(target: str, features: list[str]) -> None:
    """Bloqueia rótulos e, na previsão do gap, qualquer variável pós-abertura."""
    allowed = ('x_pre_',) if target == 'y_gap_class' else ('x_pre_', 'x_open_')
    invalid = [name for name in features if not name.startswith(allowed)]
    if invalid:
        raise ValueError(f'Variáveis não permitidas para {target}: {invalid}')


def baseline_model() -> DummyClassifier:
    """Prevê a frequência histórica do treino."""
    return DummyClassifier(strategy='prior')


def walk_forward_windows(
    dates: pd.DatetimeIndex, train_years: int, test_months: int, step_months: int,
) -> Windows:
    """Janelas do desenvolvimento, a partir de train_years depois do primeiro dia."""
    start = dates.min() + pd.DateOffset(years=train_years)
    windows = []
    while start <= dates.max():
        windows.append((start - pd.DateOffset(years=train_years), start, start + pd.DateOffset(months=test_months)))
        start += pd.DateOffset(months=step_months)
    return windows


def final_windows(params: dict) -> Windows:
    """Janelas do teste final: de 3 em 3 meses a partir do dia seguinte a dev_end."""
    walk = params['walk_forward']
    start = pd.Timestamp(walk['dev_end']) + pd.Timedelta(days=1)
    windows = []
    while start <= pd.Timestamp(params['sample']['end']):
        test_end = start + pd.DateOffset(months=walk['test_months'])
        windows.append((start - pd.DateOffset(years=walk['train_years']), start, test_end))
        start += pd.DateOffset(months=walk['step_months'])
    return windows


def predict(
    table: pd.DataFrame, target: str, features: list[str], make_model: Callable, windows: Windows,
) -> pd.DataFrame:
    """Treina em cada janela só com o passado e devolve as previsões fora da amostra."""
    check_features(target, features)
    results = []
    for train_start, test_start, test_end in windows:
        # '<' e não '<=': a data inicial do teste não pode estar no treino.
        train = table[(table.index >= train_start) & (table.index < test_start)]
        test = table[(table.index >= test_start) & (table.index < test_end)]
        model = make_model().fit(train[features], train[target])
        probabilities = pd.DataFrame(
            model.predict_proba(test[features]), index=test.index, columns=model.classes_,
        ).reindex(columns=CLASSES[target], fill_value=0.0)
        results.append(probabilities.assign(y_true=test[target], y_pred=probabilities.idxmax(axis=1)))
    return pd.concat(results)


def walk_forward_predict(
    table: pd.DataFrame, target: str, features: list[str], make_model: Callable, *,
    train_years: int, test_months: int, step_months: int,
) -> pd.DataFrame:
    """Walk-forward do desenvolvimento, só com as linhas sem variável ausente."""
    sample = table.dropna(subset=[target, *features]).sort_index()
    windows = walk_forward_windows(sample.index, train_years, test_months, step_months)
    return predict(sample, target, features, make_model, windows)


def scores(predictions: pd.DataFrame, classes: list[str]) -> dict:
    """Acerto, acerto balanceado, log loss e Brier das previsões fora da amostra."""
    hits = predictions.y_true.eq(predictions.y_pred)
    ordered = sorted(classes)  # log_loss assume colunas em ordem alfabética.
    observed = pd.get_dummies(predictions.y_true)
    observed = observed.reindex(columns=classes, fill_value=False).to_numpy(float)
    return {
        'n': len(predictions),
        'accuracy': hits.mean(),
        'balanced_accuracy': hits.groupby(predictions.y_true).mean().mean(),
        'log_loss': log_loss(predictions.y_true, predictions[ordered].to_numpy(), labels=ordered),
        'brier': ((predictions[classes].to_numpy() - observed) ** 2).sum(axis=1).mean(),
    }


def daily_loss(predictions: pd.DataFrame) -> pd.Series:
    """Log loss de cada dia: -log da probabilidade dada à classe que aconteceu."""
    position = predictions.columns.get_indexer(predictions.y_true)
    given = predictions.to_numpy()[np.arange(len(predictions)), position].astype(float)
    return pd.Series(-np.log(given.clip(1e-15)), index=predictions.index)


BINS = [0, 0.1, 0.2, 0.35, 0.5, 0.7, 1]  # faixas de probabilidade prevista


def reliability(predictions: pd.DataFrame, classes: list[str]) -> pd.DataFrame:
    """Por classe e faixa de probabilidade: dias, média prevista e frequência observada."""
    parts = []
    for name in classes:
        frame = pd.DataFrame({
            'faixa': pd.cut(predictions[name], BINS, include_lowest=True),
            'prevista': predictions[name], 'observada': predictions.y_true.eq(name),
        })
        table = frame.groupby('faixa', observed=True).agg(
            dias=('prevista', 'size'), prevista=('prevista', 'mean'), observada=('observada', 'mean'),
        )
        parts.append(table.assign(classe=name).set_index('classe', append=True).swaplevel())
    return pd.concat(parts)


def calibration_error(predictions: pd.DataFrame, classes: list[str]) -> float:
    """ECE: distância média entre prevista e observada nas faixas, pesada por dias."""
    table = reliability(predictions, classes)
    gap = (table.prevista - table.observada).abs() * table.dias
    return gap.groupby(level='classe').sum().div(table.dias.groupby(level='classe').sum()).mean()


def evaluate(model: pd.DataFrame, frequency: pd.DataFrame, classes: list[str]) -> pd.DataFrame:
    """Métricas do modelo e da frequência histórica; melhora é a queda do log loss por dia."""
    difference = daily_loss(frequency) - daily_loss(model)
    rows = {}
    for name, predictions in (('modelo', model), ('frequência histórica', frequency)):
        rows[name] = scores(predictions, classes) | {'ECE': calibration_error(predictions, classes)} | {
            f'AUC {k}': roc_auc_score(predictions.y_true.eq(k), predictions[k]) for k in classes
        }
    result = pd.DataFrame(rows).T.rename(columns={
        'n': 'dias', 'log_loss': 'log loss', 'accuracy': 'acerto', 'balanced_accuracy': 'acerto balanc.',
    })
    result['dias'] = result.dias.astype(int)
    result.loc['modelo', 'melhora'] = difference.mean()
    result.loc['modelo', 'erro'] = difference.std() / np.sqrt(len(difference))
    columns = ['dias', 'log loss', 'melhora', 'erro', 'brier', 'ECE', 'acerto', 'acerto balanc.']
    return result[columns + [f'AUC {k}' for k in classes]]


def confusion(predictions: pd.DataFrame, classes: list[str]) -> pd.DataFrame:
    """Matriz de confusão: linhas são o resultado real e colunas, o previsto."""
    matrix = confusion_matrix(predictions.y_true, predictions.y_pred, labels=classes)
    return pd.DataFrame(
        matrix,
        index=pd.Index(classes, name='real'),
        columns=pd.Index(classes, name='previsto'),
    )
