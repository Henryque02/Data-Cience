# Correlação e matriz de confusão

Gerado por `notebooks/02_correlacao_e_matriz_confusao.ipynb`. Primeira avaliação: linha de base e regressão logística em walk-forward
(treino 2 anos, teste 3 meses, avanço 3 meses, C = 0.1).

## Pergunta 1: tipo de abertura (`y_gap_class`)

Período testado:

- WIN: 2022-10-24 a 2026-09-25, 827 previsões, amostra comum de 1279 dias.
- WDO: 2022-09-26 a 2026-04-01, 727 previsões, amostra comum de 1170 dias.

**WIN**

| configuração | n | acerto | acerto_balanceado | log_loss | brier |
|---|---|---|---|---|---|
| Linha de base | 827 | 61.1% | 33.3% | 0.9647 | 0.5701 |
| Logística núcleo | 827 | 71.3% | 60.7% | 0.6710 | 0.4034 |
| Logística núcleo + todas x_pre_ | 827 | 69.9% | 60.5% | 0.7363 | 0.4244 |

**WDO**

| configuração | n | acerto | acerto_balanceado | log_loss | brier |
|---|---|---|---|---|---|
| Linha de base | 727 | 75.9% | 33.3% | 0.7297 | 0.4017 |
| Logística núcleo | 727 | 82.7% | 58.8% | 0.4933 | 0.2811 |
| Logística núcleo + todas x_pre_ | 727 | 79.4% | 56.6% | 0.5844 | 0.3268 |

Matrizes de confusão da logística núcleo (figura `reports/figures/06_matriz_gap.png`):

**WIN** (linhas = real, colunas = previsto, % da linha real)

| real \ previsto | baixa | normal | alta |
|---|---|---|---|
| baixa | 73 (48%) | 76 (50%) | 3 (2%) |
| normal | 40 (8%) | 436 (86%) | 29 (6%) |
| alta | 0 (0%) | 89 (52%) | 81 (48%) |

**WDO** (linhas = real, colunas = previsto, % da linha real)

| real \ previsto | baixa | normal | alta |
|---|---|---|---|
| baixa | 39 (45%) | 48 (55%) | 0 (0%) |
| normal | 9 (2%) | 531 (96%) | 12 (2%) |
| alta | 0 (0%) | 57 (65%) | 31 (35%) |

## Pergunta 2: comportamento pós-abertura (`y_behavior`, janela de 60 min)

Período testado:

- WIN: 2022-10-27 a 2026-09-23, 321 previsões, amostra comum de 575 dias.
- WDO: 2022-09-26 a 2026-04-01, 175 previsões, amostra comum de 370 dias.

**WIN**

| configuração | n | acerto | acerto_balanceado | log_loss | brier |
|---|---|---|---|---|---|
| Linha de base | 321 | 36.4% | 33.1% | 1.0979 | 0.6634 |
| Logística núcleo | 321 | 36.1% | 33.2% | 1.1135 | 0.6781 |
| Logística núcleo + todas x_pre_ | 321 | 38.0% | 36.0% | 1.4153 | 0.7982 |

**WDO**

| configuração | n | acerto | acerto_balanceado | log_loss | brier |
|---|---|---|---|---|---|
| Linha de base | 175 | 43.4% | 33.3% | 1.0738 | 0.6507 |
| Logística núcleo | 175 | 40.6% | 38.3% | 1.1167 | 0.6778 |
| Logística núcleo + todas x_pre_ | 175 | 38.9% | 36.8% | 1.4566 | 0.7898 |

Matrizes de confusão da logística núcleo (figura `reports/figures/07_matriz_comportamento.png`):

**WIN** (linhas = real, colunas = previsto, % da linha real)

| real \ previsto | tendência | reversão | lateral |
|---|---|---|---|
| tendência | 67 (53%) | 8 (6%) | 51 (40%) |
| reversão | 33 (40%) | 9 (11%) | 41 (49%) |
| lateral | 66 (59%) | 6 (5%) | 40 (36%) |

**WDO** (linhas = real, colunas = previsto, % da linha real)

| real \ previsto | tendência | reversão | lateral |
|---|---|---|---|
| tendência | 15 (26%) | 8 (14%) | 34 (60%) |
| reversão | 9 (21%) | 14 (33%) | 19 (45%) |
| lateral | 27 (36%) | 7 (9%) | 42 (55%) |

## Correlação

Correlação de Pearson entre o retorno overnight de cada ativo e o gap (figura `reports/figures/05_correlacoes.png`):

| ativo | WIN | WDO |
|---|---|---|
| spx | 0.714 | -0.527 |
| sx5e | 0.68 | -0.525 |
| ndx | 0.657 | -0.48 |
| ftse | 0.596 | -0.448 |
| usdmxn | -0.519 | 0.687 |
| nikkei | 0.513 | -0.358 |
| copper | 0.43 | -0.401 |
| a50 | 0.353 | -0.256 |
| dxy | -0.313 | 0.504 |
| eurusd | 0.286 | -0.478 |
| gold | 0.238 | -0.246 |
| brent | 0.09 | -0.155 |
| usdjpy | -0.019 | 0.128 |

## Conclusões

**Pergunta 1, tipo de abertura.** Só dizemos que há sinal quando o log loss da logística é menor que o da linha de base.

- **WIN, Logística núcleo:** log loss 0.6710 contra 0.9647 da linha de base: há sinal (log loss menor que o da linha de base).
- **WIN, Logística núcleo + todas x_pre_:** log loss 0.7363 contra 0.9647 da linha de base: há sinal (log loss menor que o da linha de base).
- **WDO, Logística núcleo:** log loss 0.4933 contra 0.7297 da linha de base: há sinal (log loss menor que o da linha de base).
- **WDO, Logística núcleo + todas x_pre_:** log loss 0.5844 contra 0.7297 da linha de base: há sinal (log loss menor que o da linha de base).

O acerto da logística núcleo foi 71.3% no WIN (linha de base 61.1%) e 82.7% no WDO (linha de base 75.9%). Acertar a classe mais comum não prova nada; olhe o log loss e a diagonal da matriz.

**Pergunta 2, comportamento depois da abertura.**

- **WIN, Logística núcleo:** log loss 1.1135 contra 1.0979 da linha de base: sem sinal (log loss igual ou maior que o da linha de base).
- **WIN, Logística núcleo + todas x_pre_:** log loss 1.4153 contra 1.0979 da linha de base: sem sinal (log loss igual ou maior que o da linha de base).
- **WDO, Logística núcleo:** log loss 1.1167 contra 1.0738 da linha de base: sem sinal (log loss igual ou maior que o da linha de base).
- **WDO, Logística núcleo + todas x_pre_:** log loss 1.4566 contra 1.0738 da linha de base: sem sinal (log loss igual ou maior que o da linha de base).

O acerto da logística núcleo foi 36.1% no WIN (linha de base 36.4%) e 40.6% no WDO (linha de base 43.4%).

**Acertar o gap não é oportunidade de lucro.** Às 09:00 o gap já aconteceu e não dá para operá-lo. O que importaria para operar é a pergunta 2: saber se o preço segue, volta ou fica parado depois da abertura.

**Limites.** Esta é só a primeira avaliação. Não há gradient boosting, não há curva de calibração e não há backtest com custos e slippage (a diferença entre o preço esperado e o executado). Um log loss menor que o da linha de base ainda não é uma regra lucrativa.
