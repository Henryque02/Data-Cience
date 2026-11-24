# AGENTS.md — Modelo 3: Classificação de Abertura da B3

Trabalho da disciplina "Data Science para Mercado Financeiro" (UFG). Leia este arquivo inteiro antes de qualquer tarefa.

## 1. Objetivo do projeto

Usar o que acontece **entre o fechamento da B3 e a abertura do dia seguinte** (bolsas estrangeiras, câmbio, commodities, cripto) para prever, **antes da abertura e só com dados até 08:58 BRT**, se o mini índice (WIN) e o mini dólar (WDO) vão abrir com **gap de alta, gap de baixa ou normal**, como probabilidades. É a classificação pedida no quadro do professor (Modelo 3).

**Escopo (decisão do usuário em 24/11/2026): o trabalho entrega só essa classificação.** O desenho original tinha mais duas perguntas, o comportamento do preço depois da abertura (tendência, reversão ou lateral) e a faixa operacional (alvo e stop), além de um backtest com custos; as três saíram do escopo, e o código delas foi retirado. Motivo de registro: prever o gap sozinho não gera operação, porque o preço de abertura sai do leilão de pré-abertura e só ganha o gap quem já estava posicionado na véspera; e, no desenvolvimento, a direção do preço depois da entrada foi praticamente cara ou coroa (estudo de 23/11/2026: de 5 a 60 min depois da entrada, o preço seguiu a direção do gap em 45% a 57% dos dias).

Exemplo (WIN): às 08:58 o modelo dá 15% de gap de baixa, 30% de normal e 55% de gap de alta. Às 09:00 o leilão define a abertura, e o gap acima de +0,30% confirma a classe "alta".

Validação: **walk-forward**, com um ano reservado para o teste final (seção 7).

## 2. Dados

### 2.1 Fontes

| Fonte | O quê | Como |
|---|---|---|
| MetaTrader 5 (corretora brasileira) | WIN e WDO, candles de 1 min | Exportação manual pelo terminal (Símbolos > Barras > Exportar), no Windows; sem biblioteca Python |
| Dukascopy (gratuita) | Ativos externos, candles de 1 min | `python -m abertura.e01_download`, que usa a ferramenta `dukascopy-node` (precisa do Node.js) |
| Arquivos do professor | `WIN-professor.csv`, `WDO-professor.csv` (MT5, separados por TAB, colunas `<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>`) | Em `data/raw/target/`. Usados até 2021-11-05 |
| Exportação do grupo (MT5 Genial) | `WIN-metaTrader.csv`, `WDO-metaTrader.csv` (séries `$N`, mesmo formato) | Em `data/raw/target/`. Usada a partir de 2021-11-08 (seção 2.4) |

### 2.2 Lista de ativos (fica em `config/params.yaml`, seções `targets` e `externals`)

| id | Fonte | Código na fonte | Papel |
|---|---|---|---|
| win | MT5 | série contínua do WIN | Alvo |
| wdo | MT5 | série contínua do WDO | Alvo |
| spx | Dukascopy | `usa500idxusd` | EUA (CFD que acompanha o futuro e negocia de madrugada) |
| ndx | Dukascopy | `usatechidxusd` | EUA tech |
| sx5e | Dukascopy | `eusidxeur` | Europa |
| ftse | Dukascopy | `gbridxgbp` | Londres |
| nikkei | Dukascopy | `jpnidxjpy` | Japão |
| a50 | Dukascopy | `chiidxusd` | China (substitui CSI 300) |
| hsi | Dukascopy | `hkgidxhkd` | Hong Kong (Hang Seng); incluído em 16/11/2026 |
| brent | Dukascopy | `brentcmdusd` | Petróleo |
| gold | Dukascopy | `xauusd` | Ouro |
| dxy | Dukascopy | `dollaridxusd` | Força global do dólar |
| usdmxn | Dukascopy | `usdmxn` | Proxy de moeda emergente (não há USD/BRL na Dukascopy) |
| copper | Dukascopy | `coppercmdusd` | Atividade industrial; não substituir minério de ferro |
| eurusd | Dukascopy | `eurusd` | Dólar frente ao euro |
| usdjpy | Dukascopy | `usdjpy` | Dólar frente ao iene |
| usdzar | Dukascopy | `usdzar` | Dólar frente ao rand; inclui o pedido repetido de rand |
| usdcnh | Dukascopy | `usdcnh` | Yuan offshore; não é CNY doméstico |
| usdchf | Dukascopy | `usdchf` | Dólar frente ao franco suíço |
| audusd | Dukascopy | `audusd` | Dólar australiano frente ao dólar dos EUA |
| btcusd | Dukascopy | `btcusd` | Bitcoin/USD (CFD, não futuro CME) |
| ethusd | Dukascopy | `ethusd` | Ether/USD (CFD, não futuro CME) |

São 20 séries externas. A ampliação de 12/11/2026 trouxe oito, e o Hang Seng entrou em
16/11/2026; EUR/SAR e EUR/AED
foram retiradas em 16/11/2026, da coleta à tabela, por repetirem o EUR/USD e só
existirem desde 16/09/2024. EUR/USD já atendia ao pedido de euro.
Nenhuma das 20 é contrato futuro: a Dukascopy só oferece câmbio à vista e CFDs
(catálogo de 1.499 instrumentos conferido em 16/11/2026). Adicionar uma série à coleta
não a seleciona automaticamente para os modelos.

**Período de análise:** de 2020-10-15 a 2026-11-06, o primeiro e o último dia
comuns a WIN e WDO (`sample.start` e `sample.end` em `config/params.yaml`). O
download externo começa antes, em 2020-10-01 (`download.start` em
`config/params.yaml`): as variáveis do primeiro pregão usam dados externos de dias
anteriores. A coleta atual vai até 2026-11-06 (limite superior exclusivo 2026-11-07
UTC). Registrar também o período efetivamente recebido; não encurtar toda a base
automaticamente por falha de um ativo.

### 2.3 Comando da Dukascopy (referência)

```bash
npx dukascopy-node -i usa500idxusd -from 2020-10-01 -to now -t m1 -f csv -v -dir data/raw/feature
```

- O horário sai em **UTC** (padrão, `-utc 0`). Não altere.
- `-v` inclui volume. Na Dukascopy é volume de tick/CFD, **não é volume real**, e é descartado no tratamento. Mesmo assim o `-v` fica: sem ele, a ferramenta preenche fins de semana, pausas e minutos sem negócio com velas planas (último preço repetido), o que esconderia feriados e pausas das regras da seção 5.
- Sem cache (`-ch`): um mês de um ativo leva cerca de 3,5 s e a coleta inteira cerca de 20 min. A retomada é por bloco mensal já publicado.
- Se der erro de WAF/bloqueio, rodar uma vez `npx dukascopy-node --install-browser`.

Na implementação, usar a versão local **dukascopy-node 1.51.1**, fixada em
`package.json` e `package-lock.json`, sem atualizar implicitamente via npx.
Baixar blocos
mensais com preço bid e volume, sem cache. Cada CSV só é publicado
se a ferramenta terminar sem erro e o arquivo tiver candles. Datas seguem
intervalos `[início, fim)` em UTC.
Retomada pula o CSV publicado com candles; arquivo sem candles não representa
download concluído. O coletor não confere o conteúdo: ordem e duplicatas são
tratadas em `e02_tratamento.py`, que também faz o resumo dos dias e as marcações.

### 2.4 Problemas conhecidos nos dados

- **Emenda de fontes.** WIN e WDO usam o arquivo do professor até 2021-11-05 e a exportação da Genial desde 2021-11-08 (`targets` em `config/params.yaml`). Nos dias em comum, 99,99% das velas são idênticas (provavelmente o mesmo feed). A Genial guarda só cerca de 5 anos, por isso o começo vem do professor. No período de análise, nenhum pregão fica sem dados.
- **Rolagem de contrato sem ajuste (WIN e WDO).** A série `$N` emenda contratos sem ajustar preço, e o dia da troca tem um salto entre contratos. WIN: quarta-feira mais próxima do dia 15 dos meses pares (feriado passa ao pregão seguinte, como 2022-10-13); salto médio de +1,6% a +1,9%. WDO: a série troca no **último pregão do mês anterior**; salto médio de cerca de +0,5%. Por decisão do usuário em 12/11/2026, esses gaps entram sem correção. `is_roll_day`, calculado em `e02_tratamento.py`, é uma marcação, sem excluir o dia nem invalidar o gap; a coluna `x_pre_roll_day`, que a repetia como variável, saiu em 23/11/2026. Decisão de 23/11/2026 (substitui a de 17/11): **os dias de rolagem saem do modelo**, no treino e no teste. Nesses dias o rótulo "alta" mede a troca de contrato, não o mercado; o modelo com a marcação só os "acertava" por saber o calendário (WIN 18 de 18), e a marcação não corrige o rótulo. A tabela continua com o dia e com `is_roll_day`; a exclusão é feita no modelo. O salto acompanha os juros (WIN: +0,25% em 2020, com Selic de 2%, e cerca de +2,1% em 2025-2026; WDO: cerca de +0,5%, com 7 de 73 rolagens negativas). Corrigir o rótulo com o salto esperado (média das rolagens anteriores) foi considerado e não adotado.
- **Rolagem nos CFDs de Brent e cobre.** Esses CFDs saltam na troca de vencimento, numa reabertura depois do fechamento da B3. Nessa noite a pausa diária fica mais longa (Brent: 200–201 min em vez de 181; cobre: 80–81 em vez de 61), e o salto sai quase sempre para o mesmo lado; no Brent, o WTI não acompanha, o que descarta notícia. Decisão de 17/11/2026: o salto dessas reaberturas é descontado (`features.pre_open.roll_pause_minutes`, `e03_feat_labels.without_roll_jumps`). Entre 12/11 e 17/11/2026 os saltos entravam sem correção; a correção do checkpoint, que ignorava todas as pausas de 30 min a 12 h, está preservada na cópia.
- **Horário de fechamento muda** ao longo dos anos (último candle às 17:54/17:59 ou 18:24/18:29). Detectar a partir dos dados; nunca fixar no código.
- **Abertura depois das 09:00 no WIN recente.** Desde out/2025, o primeiro candle costuma sair às 09:02 ou 09:03 na maioria dos pregões; o volume até 09:10 indica abertura real mais tarde. Em 2026-07-31, uma falha da B3 adiou a abertura de WIN e WDO para cerca de 12:33. A abertura é sempre o primeiro candle do dia.
- **Buracos explicados na primeira hora** (não afetam o gap, que usa só a abertura). WIN 21/08/2025 (09:17–10:25) e 03/06/2025 (09:04–09:55): falha da B3 no mini índice; o WDO desses dias está completo. 26/10/2026 (WIN e WDO): circuit breaker depois do segundo turno. 05/10/2026 (WIN): leilões de 1 a 2 minutos depois do primeiro turno. WDO 27/09/2024 termina às 17:31, nas duas fontes, sem causa encontrada. Detalhes e fontes no README (Decisões pendentes).
- A coluna `SPREAD` dos arquivos do MT5 é um valor fixo, não medido. Não usar.

## 3. Convenções obrigatórias

### 3.1 Tempo — a regra mais importante do projeto

- **Todo dado padronizado fica em UTC** (`datetime64[ns, UTC]`). Converter para `America/Sao_Paulo` só para exibir.
- CSVs exportados pelo terminal MT5 usam horário sem fuso explícito; nas duas exportações ele é Brasília (abertura às 09:00), confirmado pelo usuário em 16/11/2026.
- O Brasil não tem horário de verão desde 2019. EUA, Europa e Japão/China têm regras próprias. Por isso o horário dos pregões estrangeiros em Brasília **muda durante o ano**. Nunca escrever janelas de horário estrangeiro fixas em horário de Brasília.
- Candles são rotulados pelo **horário de abertura**. O candle "08:59" fecha às 09:00.

### 3.2 Sem vazamento de informação (look-ahead)

- Todas as variáveis são **pré-abertura (`x_pre_`)**: só usam dados com **horário de abertura do candle ≤ 08:58 BRT do dia D**. O candle das 08:58 fecha às 08:59 e deixa 1 min de margem. Na Quarta-feira de Cinzas, que abre às 13:00 pelo calendário da B3, o corte é 12:58 (decisão de 16/11/2026): o dia vem do calendário da B3 (`exchange_calendars`), publicado antes, e a hora é fixa em `features.pre_open.special_cutoff_brt` (WIN e WDO abriram às 13:00 nas seis Cinzas da amostra). A hora de abertura da biblioteca não é usada: é a do mercado à vista (10:00 nos dias normais).
- O gap é a resposta (`y_gap`, com a classe em `y_gap_class`): do dia D, usa só o `open` do primeiro candle; nunca `high`, `low`, `close` ou `volume` desse candle, nem candles seguintes. As colunas `x_open_` (gap observado como variável das perguntas 2 e 3) saíram em 24/11/2026.
- Toda normalização, escolha de limiar (ex.: o que é "gap"), seleção de variáveis e ajuste de hiperparâmetros é feita **só com dados de treino** de cada janela do walk-forward.
- Nunca usar `shift(-1)` ou dados futuros em variáveis. Rótulos usam dados futuros por definição e ficam em colunas com prefixo `y_`.
- O projeto não tem testes automatizados. Estas garantias, e como conferi-las, estão no topo de `src/abertura/e03_feat_labels.py` e `src/abertura/e05_validacao.py`: nenhuma variável `x_pre_` usa candle com horário > 08:58 BRT do dia D (12:58 na Cinzas); o gap usa do dia D só o `open` do primeiro candle; o modelo só recebe `x_pre_` (`e05_validacao.check_features` bloqueia o resto).

### 3.3 Formato dos arquivos

- `data/raw/` — exatamente como baixado: `feature/` (ativos externos, um CSV por mês) e `target/` (WIN e WDO). Nunca editar. `/data` está no `.gitignore` para novos arquivos, mas os dados já versionados continuam rastreados pelo Git.
- `data/tratamento/<id>_m1.parquet` — 1 min padronizado: colunas `datetime` (UTC), `open, high, low, close`, ordenado e sem duplicatas. `volume` (contratos negociados) só em WIN e WDO; o volume da Dukascopy é descartado. O volume dos alvos não entra em variáveis: fica para conferências, como a abertura tardia do WIN (seção 2.4).
- `data/processed/daily.parquet` — uma linha por pregão da B3 e alvo (coluna `asset`): variáveis (`x_pre_`), rótulo (`y_gap`, `y_gap_class`), metadado `is_roll_day`.
- Parquet via `pyarrow`. CSV só para entregas pequenas em `reports/`.

## 4. Estrutura do repositório

```
AGENTS.md
README.md                 # como rodar tudo, do zero
pyproject.toml            # dependências Python gerenciadas com uv
uv.lock                   # versões resolvidas, versionado
.python-version           # Python 3.12 para o ambiente inicial
package.json              # ferramenta Dukascopy com versão fixa
package-lock.json
config/params.yaml        # ativos e fontes, download, janelas, limiares, custos, walk-forward
data/{raw,tratamento,processed}/   # gitignored
src/abertura/             # numerados na ordem dos dados (e = etapa); comandos: e01, e02, e04
  e01_download.py         # coleta da Dukascopy (comando)
  e02_tratamento.py       # leitura dos CSVs, emenda WIN/WDO e Parquet em data/tratamento/ (comando); calendário, resumo dos dias e rolagens (antes: e03_filtros)
  e03_feat_labels.py      # variáveis x_pre_ e rótulo y_gap / y_gap_class (antes: e04_feat_labels)
  e04_daily.py            # monta data/processed/daily.parquet (comando; antes: e05_daily)
  e05_validacao.py        # validação comum: regra contra vazamento, walk-forward, métricas (antes: e05_models)
  modelo1_gap.py          # modelo final; --final roda o teste nos 12 meses reservados (uma vez) (comando)
  estudo_gap.py           # estudo que levou ao modelo: listas de variáveis x logística multinomial e dois binários (comando)
reports/                  # gráficos e tabelas finais
```

O desenvolvimento e a revisão seguem os módulos em `src/abertura`. Em 23/11/2026 saíram os
scripts de estudo antigos (`estudo_p1`, `estudo_ativos`); em 24/11/2026, o código das
perguntas 2 e 3 (`estudo_comportamento`, `analise_tempo`, rótulos de comportamento e faixa,
colunas `x_open_`). As conclusões que ficaram valendo estão no README (Decisões
pendentes). `reports/` guarda as previsões do teste final.

## 5. Definições (parâmetros em `config/params.yaml`)

- **Fechamento de referência (D-1):** `close` do último candle do pregão regular de D-1.
- **Abertura (D):** `open` do primeiro candle de D. Normalmente 09:00 BRT (13:00 na Quarta-feira de Cinzas); o primeiro candle pode vir minutos depois (seção 2.4) ou horas depois em falha da B3 (31/07/2026).
- **Gap (%):** `abertura_D / fechamento_D-1 - 1`, inclusive em dia de rolagem, sem ajuste entre contratos. Fica ausente somente quando falta o preço necessário, como o fechamento anterior ao primeiro WIN.
- **Classe do gap:** alta / baixa / normal por limiar `±k`. É o rótulo do modelo. `k` é fixo por alvo (`labels.gap_threshold`, 17/11/2026): 0,30% no WIN e 0,25% no WDO. O do WDO foi escolhido para deixar a mesma proporção de dias normais que o do WIN nos dois primeiros anos (44%), que só servem de treino; limiar móvel e limiar por quantil do treino foram testados e não foram melhores (estudo de 16/11/2026). Na tabela atual: WIN 26% alta, 21% baixa, 54% normal; WDO 21% alta, 20% baixa, 59% normal.
- **Pregão incluído:** todo dia com dados do alvo dentro de `sample`, inclusive Cinzas e rolagem (a tabela guarda o dia; o modelo tira a rolagem). O primeiro dia do histórico de cada alvo não vira linha, porque pode começar no meio do pregão; no período, isso tira só o WIN de 15/10/2020 (primeira vela às 11:49, sem D-1). Não interpolar preços.
- **Variáveis de cada ativo externo:** retorno entre o horário do fechamento da B3 em D-1 e 08:58 BRT de D, ou 12:58 na Quarta-feira de Cinzas (`overnight`) e volatilidade realizada no mesmo intervalo (`night_vol`). A tabela guarda, de cada ativo, o `overnight` e a `night_vol`; cada modelo escolhe quais usa. A `night_vol` por ativo saiu da tabela em 17/11/2026, trocada pela média do log (`x_pre_night_vol_mean`), e voltou em 23/11/2026, a pedido do usuário; a média saiu no mesmo dia. Do alvo: amplitude média dos 5 pregões anteriores e posição do fechamento de D-1, medidas dentro dos pregões para não incluir a rolagem. Todas são `x_pre_` (seção 3.2). Retornos da última 1h/3h, do dia anterior lá fora e do pregão asiático foram cortados: são pedaços do `overnight` ou não têm relação com o gap.
- **Preço externo conhecido:** último `close` com candle aberto até o instante. As variáveis externas só existem se (1) o ativo teve alguma vela depois do fechamento da B3 em D-1 e até o corte (feriado lá fora na madrugada) e (2) o preço de partida, no fechamento da B3 em D-1, tem no máximo `max_start_age_hours` (24 h) (feriado lá fora em D-1: sem isso, o overnight somava dias que a B3 já tinha negociado). Nos dois casos a variável fica ausente na tabela em vez de virar zero; na pergunta 1, o vazio vira zero só na entrada do modelo (decisão de 23/11/2026: mercado fechado, preço parado; nos dias completos não muda o resultado e evita dias sem previsão). Se o ativo negociou e parou (pane da bolsa), vale o último preço. A regra (2) entrou em 23/11/2026 e esvazia 105 noites (Hang Seng 57, A50 13, FTSE 10, Europe 50 8, demais 2 ou 3); nenhuma idade fica entre 18 e 24 h. O antigo limite de 7 dias (`max_price_age_minutes`) nunca agia e saiu no mesmo dia.
- **Pausas do Brent e do cobre:** só a reabertura da troca de contrato (pausa longa, seção 2.4) é corrigida: nela conta só o que a vela andou, da abertura ao fechamento. As demais pausas e os fins de semana entram integralmente. A correção perde o movimento real durante a pausa da troca (em média 0,2% no Brent) e não pega trocas que não alongam a pausa.
- **Variáveis do histórico do alvo:** `x_pre_target_range_5d` mede a amplitude média dos cinco pregões anteriores e `x_pre_target_close_position` mede onde D-1 fechou entre a mínima (0) e a máxima (1) do dia. São conhecidas antes da abertura. O retorno do pregão anterior (`x_pre_target_return_prev`) saiu em 17/11/2026: mede o mesmo efeito que a posição do fechamento e foi mais fraco no estudo da pergunta 1.

## 6. Modelos

- **Linha de base:** frequência histórica (as proporções de cada classe no treino de cada janela).
- **Modelo escolhido** (`modelo1_gap.py`, 23/11/2026): dois binários com regressão logística (alta contra o resto e baixa contra o resto; normal é o que sobra), L2 com C = 0,1, escala ajustada no treino, sem recalibração. Variáveis por alvo: 11 no WIN e 10 no WDO. Random forest, gradient boosting, regressão linear, multinomial, Lasso, recalibração de Platt e treinos mais curtos foram testados e não foram melhores.
- Avaliar com log loss (principal), Brier, calibração (ECE e tabela por faixa de probabilidade), AUC e matriz de confusão, sempre contra a frequência histórica.
- Poucos dados (~1.500 pregões por alvo): preferir modelos simples, poucas variáveis e regularização. Desconfiar de resultado bom demais.

## 7. Validação

- **Walk-forward:** treino com os 2 anos anteriores, teste nos 3 meses seguintes, avança 3 meses. Nunca embaralhar no tempo.
- **Período reservado (decisão de 17/11/2026):** os estudos e escolhas usam só os dados até `walk_forward.dev_end` (06/11/2025). Os 12 meses seguintes ficam para o teste final, lido uma única vez (lido em 23/11/2026; resultado no README).

## 8. Roteiro por fases

1. **Dados** (concluída): download dos externos, exportações do MT5, emenda e padronização em UTC.
2. **Limpeza** (concluída): calendário e padronização; exclusões de pregões e correções de rolagem retiradas por decisão do usuário.
3. **Tabela diária** (em revisão): revisão módulo a módulo desde 16/11/2026; `e01` a `e04` revisados (23/11/2026: `e03_filtros` incorporado ao `e02` e módulos seguintes renumerados; conferência contra vazamento do `e03_feat_labels` rodada em dois dias reais), `e05_models` virou `e05_validacao` (validação comum; os modelos ficam em `modeloN_*.py`); decisões pendentes no README.
4. **Análise exploratória:** primeira análise apresentada no checkpoint; atualizar com os novos ativos e as mudanças solicitadas.
5. **Modelo:** concluído em 23/11/2026 (`modelo1_gap.py`; teste final lido uma vez, resultado no README). Perguntas 2 e 3 fora do escopo desde 24/11/2026, com o código retirado.
6. **Backtest:** fora do escopo desde 24/11/2026 (dependia das perguntas 2 e 3).
7. **Relatório final.**

Cada fase termina com: código em `src/`, README atualizado e um resumo curto do que foi encontrado.

Referência anterior às mudanças: o código do checkpoint está no histórico do Git (commit
`4a7bf1d`, 11/11/2026). A cópia local com dados e previsões do checkpoint
(`data/snapshots/`) foi apagada em 23/11/2026, a pedido do usuário, depois de registrada no
README a comparação da pergunta 1 com o checkpoint. Em 12/11/2026 o usuário confirmou a
retirada das exclusões de pregões e das correções de rolagem. As regras atuais estão na
seção 5; o corte contra vazamento continua valendo.

## 9. Regras de trabalho para o agente

- Python 3.11+, ambiente inicial Python 3.12. Gerenciar dependências em `pyproject.toml` e `uv.lock`; executar com `uv run --locked`. Adicionar bibliotecas de modelos/visualização nas fases correspondentes. `requirements.txt`, se necessário para entrega, deve ser exportado do lockfile, nunca mantido à mão.
- Funções pequenas, com type hints e docstrings curtas em português. Toda lógica fica em `src/`.
- Evitar defesas para entradas hipotéticas, verificações repetidas e informações sem uso. Manter tratamentos necessários aos dados reais, às regras do projeto e à prevenção de vazamento. Ao avaliar uma verificação, explicar sua utilidade concreta, não apenas se é executada.
- Pode delegar tarefas a subagentes Terra com esforço proporcional à complexidade para economizar tokens, preservando a qualidade. O agente principal revisa e verifica o resultado.
- Nunca inventar dados nem preencher buracos de preço por interpolação. Dias incompletos permanecem na amostra por decisão do usuário; apontar essa limitação na leitura dos rótulos.
- Antes de mudar uma definição da seção 5, explicar o motivo e atualizar este arquivo.
- O projeto não tem testes automatizados, por decisão do usuário. Cada módulo de `src/abertura` começa com um texto curto que explica o que ele faz e como, para quem abrir o arquivo; ao alterar o módulo, manter esse texto em dia.
- Manter o controle proporcional ao risco. Validar o que foi baixado e poder retomar já bastam. Não acrescentar logs, registros ou outra infraestrutura sem pedido do usuário, e apagar temporários ao terminar. Nada do projeto é gravado fora do repositório: sem caches de ferramentas, e temporários em `data/staging/`.
- Quando uma suposição não puder ser verificada (ex.: regra de rolagem do WDO), registrar em `README.md` → "Suposições em aberto".
