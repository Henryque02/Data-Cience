"""Modelos de classificação avaliados em walk-forward, e suas métricas.

Não tem comando próprio: as funções são chamadas na análise dos modelos.

- check_features bloqueia variáveis proibidas: para prever o gap (pergunta 1) só entram
  x_pre_; para o comportamento (pergunta 2), x_pre_ e x_open_. Rótulos y_ nunca entram.
- add_aligned_features multiplica retornos pelo sinal do gap (x_open_aligned_): mede se
  o exterior confirma ou contraria a abertura.
- baseline_model prevê a frequência do treino; logistic_model é a regressão logística,
  com a escala ajustada só no treino de cada janela.
- walk_forward_predict treina com 2 anos e testa nos 3 meses seguintes, avançando de 3
  em 3, sem embaralhar datas. Linhas com variáveis ausentes saem da amostra; classes que
  não apareceram no treino recebem probabilidade zero.
- scores calcula acerto, acerto balanceado, log loss e Brier; confusion monta a matriz
  de confusão (linhas: real; colunas: previsto).

Conferência contra vazamento (AGENTS.md, seção 3.2): check_features recusa x_open_ na
pergunta 1 e qualquer y_; em cada janela o treino termina antes do início do teste.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

CLASSES = {
    'y_gap_class': ['baixa', 'normal', 'alta'],
    'y_behavior': ['tendencia', 'reversao', 'lateral'],
}


def check_features(target: str, features: list[str]) -> None:
    """Bloqueia rótulos e, na previsão do gap, qualquer variável pós-abertura."""
    allowed = ('x_pre_',) if target == 'y_gap_class' else ('x_pre_', 'x_open_')
    invalid = [name for name in features if not name.startswith(allowed)]
    if invalid:
        raise ValueError(f'Variáveis não permitidas para {target}: {invalid}')


def add_aligned_features(table: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Mede retornos na direção do gap; depende do gap, logo é variável x_open_."""
    aligned = table[columns].mul(np.sign(table.x_open_gap), axis=0)
    names = {name: name.replace('x_pre_', 'x_open_aligned_', 1) for name in columns}
    return table.join(aligned.rename(columns=names))


def baseline_model() -> DummyClassifier:
    """Prevê a frequência histórica do treino."""
    return DummyClassifier(strategy='prior')


def logistic_model(c: float) -> Callable:
    """Regressão logística; a escala é ajustada só com o treino de cada janela."""
    return lambda: make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=2000))


def walk_forward_windows(
    dates: pd.DatetimeIndex, train_years: int, test_months: int, step_months: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Janelas sequenciais (início do treino, início do teste, fim do teste)."""
    start = dates.min() + pd.DateOffset(years=train_years)
    windows = []
    while start <= dates.max():
        train_start = start - pd.DateOffset(years=train_years)
        test_end = start + pd.DateOffset(months=test_months)
        windows.append((train_start, start, test_end))
        start += pd.DateOffset(months=step_months)
    return windows


def walk_forward_predict(
    table: pd.DataFrame,
    target: str,
    features: list[str],
    make_model: Callable,
    *,
    train_years: int,
    test_months: int,
    step_months: int,
    min_train_rows: int = 100,
) -> pd.DataFrame:
    """Treina só com o passado de cada janela e devolve as previsões fora da amostra."""
    check_features(target, features)
    sample = table.dropna(subset=[target, *features]).sort_index()
    results = []
    windows = walk_forward_windows(sample.index, train_years, test_months, step_months)
    for train_start, test_start, test_end in windows:
        # '<' e não '<=': a data inicial do teste não pode estar no treino.
        train = sample[(sample.index >= train_start) & (sample.index < test_start)]
        test = sample[(sample.index >= test_start) & (sample.index < test_end)]
        if test.empty or len(train) < min_train_rows:
            continue
        model = make_model().fit(train[features], train[target])
        probabilities = pd.DataFrame(
            model.predict_proba(test[features]), index=test.index, columns=model.classes_,
        )
        probabilities = probabilities.reindex(columns=CLASSES[target], fill_value=0.0)
        prediction = probabilities.assign(
            y_true=test[target], y_pred=probabilities.idxmax(axis=1),
        )
        results.append(prediction)
    return pd.concat(results)


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


def confusion(predictions: pd.DataFrame, classes: list[str]) -> pd.DataFrame:
    """Matriz de confusão: linhas são o resultado real e colunas, o previsto."""
    matrix = confusion_matrix(predictions.y_true, predictions.y_pred, labels=classes)
    return pd.DataFrame(
        matrix,
        index=pd.Index(classes, name='real'),
        columns=pd.Index(classes, name='previsto'),
    )
