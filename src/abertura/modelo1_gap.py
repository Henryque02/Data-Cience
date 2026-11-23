"""Modelo da pergunta 1: antes da abertura, a chance de o gap ser de alta, de baixa ou normal.

Uso: uv run --locked python -m abertura.modelo1_gap [--alvo win] [--final]

Reúne o que foi escolhido nos estudos de estudo_gap.py (só no desenvolvimento, até
walk_forward.dev_end; números e motivos no README, em Decisões pendentes):
- Variáveis por alvo (VARIAVEIS, 23/11/2026), todas x_pre_ (conhecidas até 08:58, ou
  12:58 na Quarta-feira de Cinzas).
- Dias de rolagem fora do treino e do teste (23/11/2026): nesses dias o rótulo mede a
  troca de contrato.
- Variável vazia (mercado lá fora fechado) vira zero na entrada do modelo (23/11/2026); a
  tabela diária continua com o vazio.
- Dois binários (23/11/2026): uma logística para alta contra o resto e outra para baixa
  contra o resto, com C = models.logistic_c (0,1) e escala ajustada no treino. Normal é o
  que sobra, e as três probabilidades são reescaladas para somar 1. Sem recalibração.
- Walk-forward: cada janela treina do zero com os 2 anos anteriores, sem peso por
  recência, e prevê os 3 meses seguintes.

Modos:
- padrão: desenvolvimento, com as janelas de e05_validacao; reproduz os números dos estudos.
- --final: teste final nos 12 meses reservados (de dev_end até sample.end), a ser lido
  uma única vez (decisão de 17/11/2026). Quatro janelas de 3 meses a partir do dia
  seguinte a dev_end, cada uma treinada com os 2 anos anteriores. Grava as previsões em
  reports/modelo1_gap_final.csv.

Walk-forward e métricas vêm de e05_validacao.py, iguais para todas as perguntas: log loss
(principal), Brier, erro de calibração (ECE), AUC de cada classe, acerto, a tabela de
calibração e a matriz de confusão, contra a frequência histórica nas mesmas janelas.

Conferência contra vazamento: check_features (e05_validacao) recusa x_open_ e y_; o treino
de cada janela termina antes do primeiro dia de teste.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .e05_validacao import (
    CLASSES, baseline_model, confusion, evaluate, final_windows, predict, reliability,
    walk_forward_windows,
)

PROJECT = Path(__file__).resolve().parents[2]
TARGET = 'y_gap_class'
ORDER = CLASSES[TARGET]  # baixa, normal, alta

# Variáveis escolhidas em 23/11/2026 (rodadas 1 a 3 de estudo_gap.py).
VARIAVEIS = {
    'win': [
        'x_pre_spx_overnight',                                            # bolsas EUA
        'x_pre_usdmxn_overnight', 'x_pre_audusd_overnight', 'x_pre_usdzar_overnight',  # moedas emergentes
        'x_pre_target_range_5d', 'x_pre_target_close_position',          # histórico do alvo
        'x_pre_sx5e_overnight',                                           # bolsa Europa
        'x_pre_nikkei_overnight',                                         # bolsa Japão
        'x_pre_a50_overnight',                                            # bolsa China
        'x_pre_copper_overnight', 'x_pre_brent_overnight',               # commodities
    ],
    'wdo': [
        'x_pre_dxy_overnight',                                            # dólar global
        'x_pre_usdmxn_overnight', 'x_pre_audusd_overnight', 'x_pre_usdzar_overnight',
        'x_pre_usdcnh_overnight',                                         # moedas emergentes
        'x_pre_spx_overnight',                                            # bolsas EUA
        'x_pre_copper_overnight',                                         # commodities
        'x_pre_sx5e_night_vol',                                           # agitação da madrugada
        'x_pre_target_range_5d', 'x_pre_target_close_position',          # histórico do alvo
    ],
}


class TwoBinary(BaseEstimator, ClassifierMixin):
    """Duas logísticas binárias (alta e baixa contra o resto); normal é o que sobra."""

    def __init__(self, base):
        self.base = base

    def fit(self, frame: pd.DataFrame, labels: pd.Series, **fit_params) -> TwoBinary:
        self.models_ = {
            side: clone(self.base).fit(frame, labels.eq(side), **fit_params) for side in ('alta', 'baixa')
        }
        self.classes_ = np.array(ORDER)
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        up, down = (self.models_[side].predict_proba(frame)[:, 1] for side in ('alta', 'baixa'))
        # Se alta + baixa passar de 1, normal fica com um mínimo e as três são reescaladas.
        normal = np.clip(1 - up - down, 0.01, None)
        result = np.column_stack([down, normal, up])  # mesma ordem de ORDER
        return result / result.sum(axis=1, keepdims=True)


def gap_model(c: float) -> TwoBinary:
    """O modelo escolhido: dois binários com logística L2 e escala ajustada no treino."""
    return TwoBinary(make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=2000)))


def load(asset: str, params: dict, end: str) -> pd.DataFrame:
    """Dias do alvo até `end`, sem rolagem, com rótulo e com o vazio das VARIAVEIS como zero."""
    daily = pd.read_parquet(PROJECT / 'data/processed/daily.parquet')
    table = daily[daily.asset == asset].set_index('date_brt').sort_index()
    table = table[(table.index <= end) & ~table.is_roll_day].dropna(subset=[TARGET])
    return table.fillna(dict.fromkeys(VARIAVEIS[asset], 0.0))


def run(asset: str, params: dict, final: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Previsões fora da amostra do modelo e da frequência histórica."""
    walk = params['walk_forward']
    if final:
        table = load(asset, params, params['sample']['end'])
        windows = final_windows(params)
    else:
        table = load(asset, params, walk['dev_end'])
        windows = walk_forward_windows(table.index, walk['train_years'], walk['test_months'], walk['step_months'])
    features = VARIAVEIS[asset]
    model = predict(table, TARGET, features, lambda: gap_model(params['models']['logistic_c']), windows)
    frequency = predict(table, TARGET, features, baseline_model, windows)
    return model, frequency


def main(argv: list[str] | None = None) -> int:
    """Avalia o modelo no desenvolvimento ou, com --final, no período reservado."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--alvo', choices=list(VARIAVEIS), nargs='+', default=list(VARIAVEIS))
    parser.add_argument('--final', action='store_true', help='teste final nos 12 meses reservados (uma vez)')
    args = parser.parse_args(argv)
    params = yaml.safe_load((PROJECT / 'config/params.yaml').read_text())
    pd.set_option('display.width', 250, 'display.float_format', '{:.4f}'.format)
    period = 'teste final (período reservado)' if args.final else 'desenvolvimento'
    saved = []
    for asset in args.alvo:
        model, frequency = run(asset, params, args.final)
        first, last = model.index.min().date(), model.index.max().date()
        print(f'\n== {asset.upper()} · {period}, {first} a {last} (sem rolagem, vazio vira zero)')
        print(evaluate(model, frequency, ORDER).to_string())
        print('\nProbabilidade prevista x frequência observada:\n' + reliability(model, ORDER).to_string())
        print('\nMatriz de confusão (linhas: real, colunas: previsto):\n' + confusion(model, ORDER).to_string())
        saved.append(model.assign(asset=asset))
    if args.final:
        output = PROJECT / 'reports/modelo1_gap_final.csv'
        output.parent.mkdir(exist_ok=True)
        pd.concat(saved).rename_axis('date_brt').reset_index().to_csv(output, index=False)
        print(f'\nPrevisões gravadas em {output.relative_to(PROJECT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
