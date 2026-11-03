# AGENTS.md — Modelo 3: Classificação de Abertura da B3

Trabalho da disciplina "Data Science para Mercado Financeiro" (UFG). Leia este arquivo inteiro antes de qualquer tarefa.

## 1. Objetivo do projeto

Usar o que acontece **entre o fechamento da B3 e a abertura do dia seguinte** (bolsas estrangeiras, câmbio, commodities, juros) para prever o comportamento dos **primeiros minutos do pregão** do mini índice (WIN) e do mini dólar (WDO), e transformar isso numa regra de day trade.

Perguntas que o modelo responde, sempre como **probabilidades**:

1. **Tipo de abertura:** gap de alta, gap de baixa ou normal.
2. **Comportamento pós-abertura** (janela padrão: 60 min, parametrizável): **tendência** (o preço segue a direção do gap), **reversão** (o gap fecha) ou **lateral**.
3. **Volatilidade / faixa operacional:** tamanho esperado do movimento (máxima e mínima a partir da abertura), usado para alvo e stop.

Ponto conceitual importante: na abertura o gap **já é conhecido** (o leilão de pré-abertura mostra o preço teórico). O grupo não carrega posição de um dia para o outro. Então a operação acontece **depois** da abertura, e o valor do modelo está nas perguntas 2 e 3. A pergunta 1 é contexto: o gap **observado** entra como variável nas outras duas, e a previsão do gap só é usada nelas se demonstrar informação adicional nos testes.

Validação: **walk-forward** com **custos e slippage** (seção 7).

## 2. Dados

### 2.1 Fontes

| Fonte | O quê | Como |
|---|---|---|
| MetaTrader 5 (conta demo de corretora brasileira) | WIN e WDO, candles de 1 min | Lib `MetaTrader5`, ainda sem código no projeto (**só roda no Windows**, com o terminal MT5 aberto e logado) |
| Dukascopy (gratuita) | Ativos externos, candles de 1 min | `python -m abertura.download`, que usa a ferramenta `dukascopy-node` (precisa do Node.js) |
| Arquivos do professor | `WIN.csv`, `WDO.csv` (MT5, separados por TAB, colunas `<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>`) | Em `data/raw/target/`. Fonte inicial no Linux; comparar com MT5 quando o grupo fornecer o download |

### 2.2 Lista de ativos (fica em `config/assets.yaml`)

| id | Fonte | Símbolo | Papel |
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

**Período solicitado:** de 2020-09-01 até o último dia útil completo disponível.
Registrar também o período efetivamente recebido; não encurtar toda a base
automaticamente por falha de um ativo. A coleta inicial encerra em 2026-10-30
(limite superior exclusivo 2026-10-31 UTC).

### 2.3 Comando da Dukascopy (referência)

```bash
npx dukascopy-node -i usa500idxusd -from 2020-09-01 -to now -t m1 -f csv -v -dir data/raw/feature -ch
```

- O horário sai em **UTC** (padrão, `-utc 0`). Não altere.
- `-v` inclui volume. Na Dukascopy é volume de tick/CFD, **não é volume real**. Não use como variável relevante.
- `-ch` usa cache local. Isso permite retomar se cair no meio.
- Se der erro de WAF/bloqueio, rodar uma vez `npx dukascopy-node --install-browser`.

Na implementação, usar a versão local **dukascopy-node 1.51.1**, fixada em
`package.json` e `package-lock.json`, sem atualizar implicitamente via npx.
Baixar blocos
mensais com preço bid, volume e cache fora do projeto; validar antes de publicar
cada CSV. Piloto separado em `data/raw/feature_pilot/`.
Datas seguem intervalos `[início, fim)` em UTC. Retomada revalida o CSV existente;
arquivo vazio ou malformado não representa download concluído.

### 2.4 Problemas conhecidos nos dados da B3 (já verificados nos arquivos do professor)

- **Rolagem de contrato sem ajuste.** A série `_N` emenda contratos sem ajustar preço. O WIN vence na quarta-feira mais próxima do dia 15 dos meses pares. Nesses dias aparece um gap falso de ~+1,6% em média (diferença de preço entre contratos); feriado passa a troca ao pregão seguinte (2022-10-13). O WDO vence no 1º dia útil de cada mês, mas na série a troca aparece no **último pregão do mês anterior**: gap médio de +0,44%, com 87% de dias positivos, e vizinhos perto de zero. O tamanho acompanha o diferencial de juros entre Brasil e EUA, por isso fica invisível no ruído em 2020–21 (Selic a 2%). A regra está em `src/abertura/clean.py`.
- **Buracos internos medidos no calendário BVMF:** WIN — 114 pregões ausentes, incluindo 2023-06-05 a 2023-10-16 (93), 2021-11-16 a 2021-12-01 (12) e 2022-07-15 a 2022-07-27 (9). WDO — 91, incluindo 2023-06-05 a 2023-09-19 (75), 2022-07-15 a 2022-07-28 (10) e 2021-11-24 a 2021-12-01 (6). Limites anteriores/posteriores ao histórico são contados separadamente.
- **Fim diferente:** o WDO do professor acaba em 2026-04-01 e o WIN em 2026-09-25.
- **Horário de fechamento muda** ao longo do ano (último candle às 17:54/17:59 ou 18:24/18:29, conforme o horário de verão americano). Detectar a partir dos dados; nunca fixar no código.
- **Abertura depois das 09:00 no WIN recente.** Não há candle às 09:00 em 56% dos pregões de 2025 T4, 27% de 2026 T1, 61% de 2026 T2 e 74% de 2026 T3; o primeiro candle costuma ser 09:02 ou 09:03. Entre 2021 T2 e 2025 T3 isso ficava em até 16%, e o WDO quase não tem esse padrão no mesmo período. Desde outubro de 2025, o volume até 09:10 é quase igual ao dos dias que abrem às 09:00, o que indica abertura real mais tarde, não candles perdidos. **Falta confirmar com a corretora.** Tabela por trimestre em `reports/qualidade_dados.md`.
- A coluna `SPREAD` muda de escala ao longo da série (fontes diferentes concatenadas). Não usar.

## 3. Convenções obrigatórias

### 3.1 Tempo — a regra mais importante do projeto

- **Todo dado padronizado fica em UTC** (`datetime64[ns, UTC]`). Converter para `America/Sao_Paulo` só para exibir.
- CSVs exportados pelo terminal MT5 usam horário sem fuso explícito; nos arquivos do professor ele parece ser Brasília (abertura às 09:00). **Confirmar** na corretora usada e documentar no README. A API Python `copy_rates_range` retorna timestamps UTC segundo sua documentação: não aplicar novamente o fuso do CSV a esse formato.
- O Brasil não tem horário de verão desde 2019. EUA, Europa e Japão/China têm regras próprias. Por isso o horário dos pregões estrangeiros em Brasília **muda durante o ano**. Nunca escrever janelas de horário estrangeiro fixas em horário de Brasília.
- Candles são rotulados pelo **horário de abertura**. O candle "08:59" fecha às 09:00.

### 3.2 Sem vazamento de informação (look-ahead)

- As variáveis têm dois grupos, conforme o momento em que ficam conhecidas:
  - **Pré-abertura (`x_pre_`):** só usam dados com **horário de abertura do candle ≤ 08:58 BRT do dia D**. O candle das 08:58 fecha às 08:59 e deixa 1 min de margem. São as únicas permitidas na pergunta 1 (prever o gap).
  - **Abertura observada (`x_open_`):** o gap e sua classe. Do dia D, só usam o `open` do primeiro candle; nunca `high`, `low`, `close` ou `volume` desse candle, nem candles seguintes. Entram apenas nas perguntas 2 e 3, cuja decisão ocorre depois da abertura.
- Toda normalização, escolha de limiar (ex.: o que é "gap"), seleção de variáveis e ajuste de hiperparâmetros é feita **só com dados de treino** de cada janela do walk-forward.
- Nunca usar `shift(-1)` ou dados futuros em variáveis. Rótulos usam dados futuros por definição e ficam em colunas com prefixo `y_`.
- O projeto não tem testes automatizados. Estas garantias, e como conferi-las, estão no topo de `src/abertura/features.py` e `src/abertura/models.py`: nenhuma variável `x_pre_` usa candle com horário > 08:58 BRT do dia D; nenhuma variável `x_open_` usa do dia D mais que o `open` do primeiro candle; o modelo da pergunta 1 não recebe `x_open_` (`models.check_features` bloqueia).

### 3.3 Formato dos arquivos

- `data/raw/` — exatamente como baixado: `feature/` (ativos externos, um CSV por mês) e `target/` (WIN e WDO). Nunca editar. Fica no `.gitignore`.
- `data/interim/<id>_m1.parquet` — 1 min padronizado: colunas `datetime` (UTC), `open, high, low, close, volume`, ordenado e sem duplicatas.
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
config/assets.yaml        # lista de ativos, fonte, símbolo, período
config/params.yaml        # janelas, limiares, custos, slippage, walk-forward
data/{raw,interim,processed}/   # gitignored
src/abertura/             # cada etapa roda com `python -m abertura.<módulo>`
  download.py             # coleta da Dukascopy
  io.py                   # leitura de CSV do MT5 e da Dukascopy -> DataFrame padrão
  interim.py              # padronização em data/interim/
  clean.py                # datas de rolagem de WIN e WDO
  sessions.py             # calendário de pregões da B3, abertura/fechamento por dia
  quality.py              # diagnósticos de cobertura e buracos
  features.py             # variáveis x_pre_ e x_open_
  labels.py               # rótulos y_
  daily.py                # monta data/processed/daily.parquet
  models.py               # modelos, walk-forward e métricas
  backtest.py             # walk-forward, regra de operação, custos, métricas
notebooks/                # só exploração; lógica reutilizável vai para src/
reports/                  # gráficos e tabelas finais
```

O roteiro de padronização e auditoria é
`notebooks/01_dados_e_qualidade.ipynb`, com saídas calculadas dos dados reais.
As células chamam leitores/conversão/diagnósticos em `src/abertura`.
Executar com o grupo uv `notebook`; não levar regras reutilizáveis só para células.

## 5. Definições (parâmetros em `config/params.yaml`)

- **Fechamento de referência (D-1):** `close` do último candle do pregão regular de D-1.
- **Abertura (D):** `open` do primeiro candle de D. A referência é 09:00 BRT (13:00 na Quarta-feira de Cinzas), mas o primeiro candle pode vir minutos depois (seção 2.4).
- **Gap (%):** `abertura_D / fechamento_D-1 - 1`. Inválido em dia de rolagem (`is_roll_day`) ou quando o pregão anterior não existe nos dados.
- **Classe do gap:** alta / baixa / normal por limiar `±k`. `k` é escolhido no treino (por quantil ou valor fixo, ex.: 0,3%). No WIN, com dados limpos: |gap| > 0,3% ≈ 23% alta, 21% baixa, 55% normal.
- **Janela pós-abertura:** padrão 60 min, contados a partir do primeiro candle de D.
- **Pregão elegível:** pregão regular (fora a Quarta-feira de Cinzas) com primeiro candle até `max_open_delay_minutes` (padrão 15) depois da referência e sem minutos faltando na janela pós-abertura. Nos dados, os atrasos vão até 10 min e o seguinte já passa de 2 h, então o limite separa abertura tardia de dia truncado na fonte. É um critério de qualidade dos dados: não ajustá-lo olhando retornos.
- **Tendência / reversão / lateral:** só em dias com gap alta ou baixa, porque sem gap relevante não há direção a seguir nem gap a fechar. Reversão = toca o fechamento de D-1 dentro da janela; tendência = fecha a janela além da abertura, na direção do gap, por mais de `m` (`trend_margin`, 0,1%); caso contrário, lateral. Reversão tem prioridade sobre tendência.
- **Faixa:** máxima e mínima da janela relativas à abertura (MFE/MAE), em %.
- **Variáveis overnight de cada ativo externo:** retorno entre o horário do fechamento da B3 em D-1 e 08:58 BRT de D; retorno nas últimas 1h/3h antes da abertura; volatilidade realizada da madrugada; retorno do dia anterior. Para a Ásia: retorno do pregão inteiro. Mais a volatilidade recente do alvo, medida dentro dos pregões para não incluir a rolagem. Todas são `x_pre_`; o gap observado é `x_open_` (seção 3.2).
- **Preço externo conhecido:** último `close` com candle aberto até o instante. No corte, preço com mais de `max_price_age_minutes` (60) é ausente, e o dia sai da amostra. Na referência (fechamento da B3 em D-1), aceita-se preço mais antigo (`reference_max_age_minutes`): mercado externo fechado em D-1 só faz o retorno cobrir mais dias.
- **Variáveis alinhadas ao gap:** na pergunta 2, cada retorno externo é multiplicado pelo sinal do gap, medindo se o exterior confirma ou contraria a abertura. Como dependem do gap, são `x_open_aligned_`.

## 6. Modelos

- **Linha de base primeiro:** frequência histórica (prevê sempre a classe mais comum) e regressão logística.
- Depois: árvores de gradient boosting (LightGBM ou `HistGradientBoostingClassifier`).
- As probabilidades precisam ser **calibradas**. Avaliar com log loss, Brier score e curva de calibração, além de AUC.
- Poucos dados (~1.300–1.400 pregões): preferir modelos simples, poucas variáveis e regularização. Desconfiar de resultado bom demais.

## 7. Backtest

- **Walk-forward:** treino em janela móvel ou crescente (padrão: 2 anos), teste nos 3 meses seguintes, avança 3 meses. Nunca embaralhar no tempo.
- **Execução realista:** entrada no `open` do candle seguinte ao primeiro candle de D (nunca no primeiro), mais slippage. Com abertura às 09:00, é o candle 09:01.
- **Contratos:** WIN — 1 ponto = R$ 0,20 e tick de 5 pontos (= R$ 1,00) por contrato. WDO — 1 ponto = R$ 10,00 e tick de 0,5 ponto (= R$ 5,00) por contrato.
- **Slippage padrão:** 1 tick por lado (parametrizável; testar 0, 1 e 2).
- **Custos:** emolumentos e corretagem por contrato e por lado, como parâmetro.
- **Saída:** alvo/stop derivados da faixa prevista, ou fim da janela, o que vier primeiro. Se alvo e stop caírem no mesmo candle, assumir o **pior** caso.
- **Métricas:** resultado líquido, nº de operações, taxa de acerto, payoff, Sharpe, máximo drawdown. Sempre comparar com as linhas de base: não operar, sempre seguir o gap, sempre apostar no fechamento do gap.

## 8. Roteiro por fases

1. **Dados:** download, padronização em UTC, verificação contra os arquivos do professor.
2. **Limpeza:** calendário de pregões, buracos, rolagem (WIN e WDO), relatório de qualidade.
3. **Tabela diária:** variáveis overnight e rótulos.
4. **Análise exploratória:** correlações, distribuição dos gaps, taxas de fechamento de gap.
5. **Modelos:** linhas de base, depois modelos melhores, com calibração.
6. **Backtest:** walk-forward com custos e slippage.
7. **Relatório final.**

Cada fase termina com: código em `src/`, garantias dos módulos conferidas, README atualizado e um resumo curto do que foi encontrado.

## 9. Regras de trabalho para o agente

- Python 3.11+, ambiente inicial Python 3.12. Gerenciar dependências em `pyproject.toml` e `uv.lock`; executar com `uv run --locked`. `MetaTrader5` no extra `mt5`, restrito ao Windows. Adicionar bibliotecas de modelos/visualização nas fases correspondentes. `requirements.txt`, se necessário para entrega, deve ser exportado do lockfile, nunca mantido à mão.
- Funções pequenas, com type hints e docstrings curtas em português. Nada de lógica importante só em notebook.
- Nunca inventar dados nem preencher buracos de preço por interpolação. Buraco é marcado e o dia sai da amostra.
- Antes de mudar uma definição da seção 5, explicar o motivo e atualizar este arquivo.
- O projeto não tem testes automatizados, por decisão do usuário. Ao alterar um módulo de `src/abertura`, conferir as garantias documentadas no topo dele e mantê-las atualizadas.
- Manter o controle proporcional ao risco. Validar o que foi baixado e poder retomar já bastam. Não acrescentar logs, registros ou outra infraestrutura sem pedido do usuário, e apagar temporários ao terminar. Caches de ferramentas ficam nos locais padrão do sistema, nunca em `data/`.
- Quando uma suposição não puder ser verificada (ex.: fuso do servidor MT5, regra de rolagem do WDO), registrar em `README.md` → "Suposições em aberto".
