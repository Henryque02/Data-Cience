# AGENTS.md — Modelo 3: Classificação de Abertura da B3

Trabalho da disciplina "Data Science para Mercado Financeiro" (UFG). Leia este arquivo inteiro antes de qualquer tarefa.

## 1. Objetivo do projeto

Usar o que acontece **entre o fechamento da B3 e a abertura do dia seguinte** (bolsas estrangeiras, câmbio, commodities, juros) para prever o comportamento dos **primeiros minutos do pregão** do mini índice (WIN) e do mini dólar (WDO), e transformar isso numa regra de day trade.

O modelo responde três perguntas:

1. **Tipo de abertura** (entrega principal: é a classificação pedida no quadro do professor), prevista antes da abertura, só com dados até 08:58 BRT: gap de alta, gap de baixa ou normal, como probabilidades. É onde o exterior tem sinal forte: na amostra, os 13 ativos externos explicam cerca de 61% do gap do WIN e 53% do gap do WDO. Sozinha não gera operação (ver abaixo).
2. **Comportamento depois da abertura**, previsto na abertura, com o gap já conhecido (janela padrão: 60 min, parametrizável), como probabilidades: **tendência** (o preço segue a direção do gap: operar a favor), **reversão** (o preço volta ao fechamento de D-1: operar contra o gap) ou **lateral** (não operar). Abertura normal também não gera operação. É a pergunta que decidiria a operação.
3. **Faixa operacional**, prevista no mesmo momento e na mesma janela: até onde o preço sobe e até onde desce, **medido a partir da abertura**. Define alvo e stop.

Por que prever o gap não gera operação: o preço de abertura sai do leilão de pré-abertura, e só ganha o gap quem já estava posicionado na véspera; o grupo não carrega posição de um dia para o outro. As perguntas 2 e 3 investigam se sobra algo operável depois da abertura. Até aqui os dados mostram pouco: depois da entrada, a correlação do movimento externo da madrugada com o movimento de WIN e WDO fica entre −0,08 e +0,09 em qualquer trecho (5 min a fim do dia). O gap **observado** entra como variável nas perguntas 2 e 3.

Por que a faixa parte da abertura, e não do fechamento de D-1: alvo e stop são distâncias a partir da entrada, que fica junto da abertura. Medida do fechamento, a faixa incluiria o gap, que não pode ser ganho, e o modelo pareceria bom só por acertar o gap. Com a abertura conhecida, uma medida se converte na outra, então nada se perde.

Exemplo (WIN): fechou em 130.000 e abriu em 131.000, gap de alta de +0,77%. O modelo indica 55% de tendência, 30% de reversão e 15% de lateral, e faixa de +0,25% a −0,15% a partir da abertura. Leitura: o mais provável é o preço seguir o gap; a operação seria de compra, com alvo e stop tirados da faixa.

Validação: **walk-forward** com **custos e slippage** (seção 7).

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
| brent | Dukascopy | `brentcmdusd` | Petróleo |
| gold | Dukascopy | `xauusd` | Ouro |
| dxy | Dukascopy | `dollaridxusd` | Força global do dólar |
| usdmxn | Dukascopy | `usdmxn` | Proxy de moeda emergente (não há USD/BRL na Dukascopy) |
| copper | Dukascopy | `coppercmdusd` | Atividade industrial; não substituir minério de ferro |
| eurusd | Dukascopy | `eurusd` | Dólar frente ao euro |
| usdjpy | Dukascopy | `usdjpy` | Dólar frente ao iene |

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
tratadas em `e02_tratamento.py`; a elegibilidade de cada pregão, em `e03_filtros.py`.

### 2.4 Problemas conhecidos nos dados

- **Emenda de fontes.** WIN e WDO usam o arquivo do professor até 2021-11-05 e a exportação da Genial desde 2021-11-08 (`targets` em `config/params.yaml`). Nos dias em comum, 99,99% das velas são idênticas (provavelmente o mesmo feed). A Genial guarda só cerca de 5 anos, por isso o começo vem do professor. No período de análise, nenhum pregão fica sem dados.
- **Rolagem de contrato sem ajuste (WIN e WDO).** A série `$N` emenda contratos sem ajustar preço, e o dia da troca tem um gap falso. WIN: quarta-feira mais próxima do dia 15 dos meses pares (feriado passa ao pregão seguinte, como 2022-10-13); gap falso médio de +1,6% a +1,9%. WDO: vence no 1º dia útil do mês, mas a série troca no **último pregão do mês anterior**; gap falso médio de cerca de +0,5%, que acompanha o diferencial de juros Brasil–EUA. A regra está em `src/abertura/e03_filtros.py`, e o gap desses dias fica vazio.
- **Rolagem nos CFDs de Brent e cobre.** Esses dois CFDs da Dukascopy seguem o contrato futuro e saltam na troca de vencimento, numa reabertura depois do fechamento da B3. Tratamento: os retornos desses dois ignoram a variação de toda reabertura após pausa de 30 min a 12 h (`daily_pause_assets`); a reabertura de fim de semana é mantida, porque concentra notícia real. Os CFDs de índices acompanham o índice à vista e não têm o problema.
- **Horário de fechamento muda** ao longo dos anos (último candle às 17:54/17:59 ou 18:24/18:29). Detectar a partir dos dados; nunca fixar no código.
- **Abertura depois das 09:00 no WIN recente.** Desde out/2025, o primeiro candle costuma sair às 09:02 ou 09:03 na maioria dos pregões; o volume até 09:10 indica abertura real mais tarde. Em 2026-07-31, uma falha da B3 adiou a abertura de WIN e WDO para cerca de 12:33. A janela de abertura sempre parte do primeiro candle.
- A coluna `SPREAD` dos arquivos do MT5 é um valor fixo, não medido. Não usar.

## 3. Convenções obrigatórias

### 3.1 Tempo — a regra mais importante do projeto

- **Todo dado padronizado fica em UTC** (`datetime64[ns, UTC]`). Converter para `America/Sao_Paulo` só para exibir.
- CSVs exportados pelo terminal MT5 usam horário sem fuso explícito; nas duas exportações ele é tratado como Brasília (abertura às 09:00). Falta confirmação da corretora (README → "Suposições em aberto").
- O Brasil não tem horário de verão desde 2019. EUA, Europa e Japão/China têm regras próprias. Por isso o horário dos pregões estrangeiros em Brasília **muda durante o ano**. Nunca escrever janelas de horário estrangeiro fixas em horário de Brasília.
- Candles são rotulados pelo **horário de abertura**. O candle "08:59" fecha às 09:00.

### 3.2 Sem vazamento de informação (look-ahead)

- As variáveis têm dois grupos, conforme o momento em que ficam conhecidas:
  - **Pré-abertura (`x_pre_`):** só usam dados com **horário de abertura do candle ≤ 08:58 BRT do dia D**. O candle das 08:58 fecha às 08:59 e deixa 1 min de margem. São as únicas permitidas na pergunta 1 (prever o gap).
  - **Abertura observada (`x_open_`):** o gap e sua classe. Do dia D, só usam o `open` do primeiro candle; nunca `high`, `low`, `close` ou `volume` desse candle, nem candles seguintes. Entram apenas nas perguntas 2 e 3, cuja decisão ocorre depois da abertura.
- Toda normalização, escolha de limiar (ex.: o que é "gap"), seleção de variáveis e ajuste de hiperparâmetros é feita **só com dados de treino** de cada janela do walk-forward.
- Nunca usar `shift(-1)` ou dados futuros em variáveis. Rótulos usam dados futuros por definição e ficam em colunas com prefixo `y_`.
- O projeto não tem testes automatizados. Estas garantias, e como conferi-las, estão no topo de `src/abertura/e04_features.py` e `src/abertura/e07_models.py`: nenhuma variável `x_pre_` usa candle com horário > 08:58 BRT do dia D; nenhuma variável `x_open_` usa do dia D mais que o `open` do primeiro candle; o modelo da pergunta 1 não recebe `x_open_` (`e07_models.check_features` bloqueia).

### 3.3 Formato dos arquivos

- `data/raw/` — exatamente como baixado: `feature/` (ativos externos, um CSV por mês) e `target/` (WIN e WDO). Nunca editar. Fica no `.gitignore`.
- `data/tratamento/<id>_m1.parquet` — 1 min padronizado: colunas `datetime` (UTC), `open, high, low, close`, ordenado e sem duplicatas. `volume` (contratos negociados) só em WIN e WDO; o volume da Dukascopy é descartado.
- `data/processed/daily.parquet` — uma linha por pregão da B3 e alvo (coluna `asset`): variáveis (`x_pre_`, `x_open_`), rótulos (`y_`), metadados (`is_roll_day`, `has_gap_in_data`, etc.).
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
src/abertura/             # numerados na ordem dos dados (e = etapa); comandos: e01, e02, e06
  e01_download.py         # coleta da Dukascopy (comando)
  e02_tratamento.py       # leitura dos CSVs, emenda WIN/WDO e Parquet em data/tratamento/ (comando)
  e03_filtros.py          # calendário da B3, pregões elegíveis e dias de rolagem
  e04_features.py         # variáveis x_pre_ e x_open_
  e05_labels.py           # rótulos y_
  e06_daily.py            # monta data/processed/daily.parquet (comando)
  e07_models.py           # modelos, walk-forward e métricas
  e08_backtest.py         # (futuro) regra de operação, custos, métricas
  analise_tempo.py        # análise exploratória: tempo até o gap fechar e até o pico (comando)
reports/                  # gráficos e tabelas finais
```

O desenvolvimento e a revisão seguem os módulos em `src/abertura`. A pasta `reports/`
ainda não existe; é criada quando houver gráficos e tabelas da análise exploratória ou
finais.

## 5. Definições (parâmetros em `config/params.yaml`)

- **Fechamento de referência (D-1):** `close` do último candle do pregão regular de D-1.
- **Abertura (D):** `open` do primeiro candle de D. Normalmente 09:00 BRT (13:00 na Quarta-feira de Cinzas); o primeiro candle pode vir minutos depois (seção 2.4) ou horas depois em falha da B3 (31/07/2026).
- **Gap (%):** `abertura_D / fechamento_D-1 - 1`. Inválido em dia de rolagem (`is_roll_day`) ou quando o pregão anterior não existe nos dados.
- **Classe do gap:** alta / baixa / normal por limiar `±k`. É o rótulo da pergunta 1; observada na abertura, também escolhe os dias da pergunta 2 (só alta e baixa). `k` é escolhido no treino (por quantil ou valor fixo, ex.: 0,3%). No WIN, com dados limpos: |gap| > 0,3% ≈ 23% alta, 21% baixa, 55% normal.
- **Janela pós-abertura:** padrão 60 min, contados a partir do primeiro candle de D.
- **Pregão elegível:** pregão regular (fora a Quarta-feira de Cinzas), que não seja o primeiro dia do histórico (o arquivo do professor começa no meio do pregão), sem minutos faltando na janela pós-abertura. Não há limite de atraso da abertura: o único atraso grande, em 31/07/2026 (primeira vela às 12:33), foi uma falha real da B3, que adiou a abertura em mais de 2 h. É um critério de qualidade dos dados: não ajustá-lo olhando retornos.
- **Tendência / reversão / lateral:** só em dias com gap alta ou baixa, porque sem gap relevante não há direção a seguir nem gap a fechar. Reversão = toca o fechamento de D-1 dentro da janela; tendência = fecha a janela além da abertura, na direção do gap, por mais de `m` (`trend_margin`, 0,1%); caso contrário, lateral. Reversão tem prioridade sobre tendência.
- **Faixa:** máxima e mínima da janela relativas à abertura (MFE/MAE), em %.
- **Variáveis de cada ativo externo:** retorno entre o horário do fechamento da B3 em D-1 e 08:58 BRT de D (`overnight`) e volatilidade realizada no mesmo intervalo (`night_vol`). Do alvo: amplitude média dos 5 pregões anteriores e retorno do pregão anterior, medidos dentro dos pregões para não incluir a rolagem. Todas são `x_pre_`; o gap observado é `x_open_` (seção 3.2). Retornos da última 1h/3h, do dia anterior lá fora e do pregão asiático foram cortados: são pedaços do `overnight` ou não têm relação com o gap.
- **Preço externo conhecido:** último `close` com candle aberto até o instante, com no máximo `max_price_age_minutes` (7 dias). As variáveis externas só existem se o ativo teve alguma vela depois do fechamento da B3 em D-1 e até o corte. Sem negociação no intervalo (feriado lá fora), a variável fica ausente em vez de virar zero. Se o ativo negociou e parou (pane da bolsa), vale o último preço.
- **Pausas do Brent e do cobre:** nesses dois ativos, os retornos e a volatilidade ignoram a variação entre o fechamento e a reabertura de pausas de 30 min a 12 h, onde acontece a troca de contrato do CFD. Reaberturas de fim de semana entram normalmente.
- **Variáveis alinhadas ao gap:** na pergunta 2, cada retorno externo é multiplicado pelo sinal do gap, medindo se o exterior confirma ou contraria a abertura. Como dependem do gap, são `x_open_aligned_`.

## 6. Modelos

- **Linha de base primeiro:** frequência histórica (prevê sempre a classe mais comum) e regressão logística.
- Depois: árvores de gradient boosting (LightGBM ou `HistGradientBoostingClassifier`).
- As probabilidades precisam ser **calibradas**. Avaliar com log loss, Brier score e curva de calibração, além de AUC.
- Poucos dados (~1.500 pregões por alvo): preferir modelos simples, poucas variáveis e regularização. Desconfiar de resultado bom demais.

## 7. Backtest

- **Walk-forward:** treino em janela móvel ou crescente (padrão: 2 anos), teste nos 3 meses seguintes, avança 3 meses. Nunca embaralhar no tempo.
- **Execução realista:** entrada no `open` do candle seguinte ao primeiro candle de D (nunca no primeiro), mais slippage. Com abertura às 09:00, é o candle 09:01.
- **Contratos:** WIN — 1 ponto = R$ 0,20 e tick de 5 pontos (= R$ 1,00) por contrato. WDO — 1 ponto = R$ 10,00 e tick de 0,5 ponto (= R$ 5,00) por contrato.
- **Slippage padrão:** 1 tick por lado (parametrizável; testar 0, 1 e 2).
- **Custos:** emolumentos e corretagem por contrato e por lado, como parâmetro.
- **Saída:** alvo/stop derivados da faixa prevista, ou fim da janela, o que vier primeiro. Se alvo e stop caírem no mesmo candle, assumir o **pior** caso.
- **Métricas:** resultado líquido, nº de operações, taxa de acerto, payoff, Sharpe, máximo drawdown. Sempre comparar com as linhas de base: não operar, sempre seguir o gap, sempre apostar no fechamento do gap.

## 8. Roteiro por fases

1. **Dados** (concluída): download dos externos, exportações do MT5, emenda e padronização em UTC.
2. **Limpeza** (concluída): calendário de pregões, elegibilidade e rolagem de WIN e WDO.
3. **Tabela diária** (em revisão): variáveis e rótulos; revisão dos módulos `e05` a `e07` e decisões pendentes do README.
4. **Análise exploratória:** correlações, distribuição dos gaps, taxas de fechamento de gap, com os dados atuais.
5. **Modelos:** linhas de base, depois modelos melhores, com calibração.
6. **Backtest:** walk-forward com custos e slippage (`e08_backtest.py`).
7. **Relatório final.**

Cada fase termina com: código em `src/`, README atualizado e um resumo curto do que foi encontrado.

## 9. Regras de trabalho para o agente

- Python 3.11+, ambiente inicial Python 3.12. Gerenciar dependências em `pyproject.toml` e `uv.lock`; executar com `uv run --locked`. Adicionar bibliotecas de modelos/visualização nas fases correspondentes. `requirements.txt`, se necessário para entrega, deve ser exportado do lockfile, nunca mantido à mão.
- Funções pequenas, com type hints e docstrings curtas em português. Toda lógica fica em `src/`.
- Evitar defesas para entradas hipotéticas, verificações repetidas e informações sem uso. Manter tratamentos necessários aos dados reais, às regras do projeto e à prevenção de vazamento. Ao avaliar uma verificação, explicar sua utilidade concreta, não apenas se é executada.
- Pode delegar tarefas a subagentes Terra com esforço proporcional à complexidade para economizar tokens, preservando a qualidade. O agente principal revisa e verifica o resultado.
- Nunca inventar dados nem preencher buracos de preço por interpolação. Buraco é marcado e o dia sai da amostra.
- Antes de mudar uma definição da seção 5, explicar o motivo e atualizar este arquivo.
- O projeto não tem testes automatizados, por decisão do usuário. Cada módulo de `src/abertura` começa com um texto curto que explica o que ele faz e como, para quem abrir o arquivo; ao alterar o módulo, manter esse texto em dia.
- Manter o controle proporcional ao risco. Validar o que foi baixado e poder retomar já bastam. Não acrescentar logs, registros ou outra infraestrutura sem pedido do usuário, e apagar temporários ao terminar. Nada do projeto é gravado fora do repositório: sem caches de ferramentas, e temporários em `data/staging/`.
- Quando uma suposição não puder ser verificada (ex.: fuso do servidor MT5, regra de rolagem do WDO), registrar em `README.md` → "Suposições em aberto".
