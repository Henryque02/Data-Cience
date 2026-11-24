# Classificação da abertura da B3

Projeto da disciplina Data Science para Mercado Financeiro (UFG). Usa o que acontece
no exterior entre o fechamento da B3 e a abertura do dia seguinte para prever se o mini
índice (WIN) e o mini dólar (WDO) vão abrir com gap de alta, gap de baixa ou normal. As
definições e regras completas estão no [AGENTS.md](AGENTS.md).

## Enunciado do professor (quadro)

Transcrição do quadro com os modelos propostos na disciplina; o Modelo 1 não aparece
na foto. Este projeto é o **Modelo 3**. A classificação pedida no quadro (normal, gap de
alta, gap de baixa) é a pergunta 1 do projeto e, desde 24/11/2026, sua única entrega: as
perguntas 2 e 3 (comportamento e faixa depois da abertura) e o backtest saíram do escopo
(AGENTS.md, seção 1).

**Modelo 2: Previsão T(t+1), tendência**

- Gráfico do preço ($) no tempo, com faixas. Em t+1, um leque de trajetórias
  possíveis. Método citado: SARIMAX.
- Dois candles com abertura (O), fechamento (C), máxima (Mx) e mínima (Mn):
  um de alta (O embaixo, C em cima) e um de baixa (O em cima, C embaixo).
- Desenho de uma linha que se divide em duas (bifurcação).
- Saída:
  - f(x) = ALTA: máxima esperada, % de probabilidade, mínima esperada.
  - NDA (nada).
  - BAIXA: mínima, % de probabilidade, máxima.

**Modelo 3: Classificação de abertura**

- B3 (9h → 18h).
- Bolsas globais, europeias e americanas: principais índices.
- B3 = f(B1, B2, B3, …).
- B3 → {Normal, Gap alta, Gap baixa}.

**Modelo 4: Classificação por indicadores técnicos**

- {ALTA, BAIXA, NDA}: R = f(I1, I2, …, In).

## Como rodar

Requer [uv](https://docs.astral.sh/uv/) e Node.js 22 ou superior. Na raiz do repositório:

```bash
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
```

Depois, as três etapas, nesta ordem:

```bash
uv run --locked python -m abertura.e01_download --end 2026-11-07   # externos
uv run --locked python -m abertura.e02_tratamento                   # Parquets (~40 s)
uv run --locked python -m abertura.e04_daily                        # tabela diária (~1 min)
```

- O `e01` baixa de 01/10/2020 (`download.start`) até o dia anterior ao `--end`, que é
  exclusivo. Rodar de novo pula os meses já baixados. `--assets spx gold` baixa só alguns.
- WIN e WDO não são baixados: vêm de `data/raw/target/` (ver "Dados").
- O projeto não tem testes automatizados. Cada módulo começa com um texto que explica o
  que faz e como.
- Se uma entrega exigir `requirements.txt`:
  `uv export --locked --no-dev --format requirements.txt --output-file requirements.txt`.

## Módulos

Os módulos em `src/abertura` são numerados na ordem em que os dados passam por eles
(`e` de etapa; nome de módulo Python não pode começar com número):

| Módulo | Comando? | Faz |
|---|---|---|
| `e01_download.py` | sim | baixa os externos da Dukascopy para `data/raw/feature/` |
| `e02_tratamento.py` | sim | lê os CSVs, converte para UTC, emenda WIN/WDO e grava um Parquet por ativo em `data/tratamento/`; também tem as funções de pregão (calendário da B3, Cinzas, resumo dos dias e rolagens), usadas pelas etapas seguintes |
| `e03_feat_labels.py` | não (usado pelo e04) | variáveis `x_pre_` e o rótulo (`y_gap`, `y_gap_class`) |
| `e04_daily.py` | sim | tabela diária `data/processed/daily.parquet` |
| `e05_validacao.py` | não (usado pelo modelo e pelo estudo) | regra contra vazamento, frequência histórica, janelas do walk-forward (desenvolvimento e teste final), previsão fora da amostra e métricas (log loss, Brier, calibração, AUC, matriz de confusão) |
| `modelo1_gap.py` | sim | modelo final da pergunta 1 (variáveis, vazio como zero, dois binários, walk-forward de 2 anos); avalia no desenvolvimento e, com `--final`, no período reservado, gravando `reports/modelo1_gap_final.csv` |
| `estudo_gap.py` | sim (estudo) | pergunta 1: compara listas de variáveis (rodadas no topo do arquivo; listas congeladas em `LISTAS`) em logística multinomial e em dois binários, e o tratamento dos dias vazios (`--vazios`), só no desenvolvimento e sem rolagem |

## Configuração

Tudo fica em `config/params.yaml`:

- `targets`: WIN e WDO, os dois arquivos de cada um, a data de troca entre eles e o fuso.
- `externals`: as 20 séries externas e o código de cada uma na Dukascopy.
- `download`: início geral e por ativo, paralelismo, tentativas e tempo limite da coleta.
- `features`, `sample`, `labels`, `models`, `walk_forward`: parâmetros das etapas
  seguintes. O período de análise (`sample`) vai de 15/10/2020 a 06/11/2026.

## Dados

| Pasta | Conteúdo |
|---|---|
| `data/raw/feature/<ativo>/<início>_<fim>.csv` | externos da Dukascopy, um CSV por mês, UTC, preço bid |
| `data/raw/target/` | WIN e WDO exportados do MetaTrader (ver abaixo) |
| `data/tratamento/<ativo>_m1.parquet` | 1 minuto padronizado: `datetime` (UTC), `open`, `high`, `low`, `close`; `volume` (contratos) só em WIN e WDO |
| `data/processed/daily.parquet` | uma linha por pregão e alvo, com variáveis, rótulos e marcações |
| `data/staging/` | temporários do download |

Os dados originais e tratados já estão versionados no checkout (982 arquivos na
auditoria anterior à ampliação). Durante a execução, `/data` também foi incluído no
`.gitignore`; novos arquivos ficam ignorados, mas isso não retira os anteriores do
versionamento. A cópia de referência e os temporários ficam ignorados.
`data/raw/` nunca é editado.

**WIN e WDO** emendam duas exportações do terminal MetaTrader, em horário de Brasília
(fuso confirmado pelo usuário em 16/11/2026):

- `WIN-professor.csv` e `WDO-professor.csv`: arquivos do professor, usados até 05/11/2021.
- `WIN-metaTrader.csv` e `WDO-metaTrader.csv`: séries `WIN$N` e `WDO$N` exportadas do
  MT5 da Genial em 08/11/2026, usadas a partir de 08/11/2021. A Genial guarda só cerca
  de 5 anos; por isso o começo vem do professor. Nos dias em comum, 99,99% das velas
  das duas fontes são idênticas.

**Externos originais (13):** S&P 500, Nasdaq 100, Europe 50, FTSE 100, Nikkei, China A50,
Brent, ouro, DXY, USD/MXN, cobre, EUR/USD e USD/JPY. A Dukascopy fornece pares de câmbio
e CFDs; os dados não são negócios dos contratos futuros em bolsa. Seu volume não é
volume real negociado.

**Ampliação (6):** USD/ZAR, USD/CNH, USD/CHF, AUD/USD, BTC/USD e ETH/USD.
Euro já está representado por EUR/USD. Rand e yuan offshore não foram duplicados;
CNH não é o yuan doméstico CNY.

**Hang Seng (16/11/2026):** bolsa de Hong Kong (`hkgidxhkd`), coletada de 01/10/2020 a
06/11/2026 sem falhas. Fica vazia em 118 dias por alvo (feriados de Hong Kong: 61 na
madrugada e 57 em D-1, pela regra das 24 h), contra 28 da China A50.

**Sem contratos futuros:** o catálogo da Dukascopy (1.499 instrumentos) não tem
futuros; só câmbio à vista e CFDs. Alguns CFDs são cotados a partir de futuros:
Brent e cobre saltam na troca de vencimento, e os índices negociam quase 24 horas,
fora do horário das bolsas à vista. Os futuros existem nas bolsas (CME, ICE, Eurex,
SGX), mas o histórico de 1 minuto deles é pago.

**EUR/SAR e EUR/AED retirados (16/11/2026):** chegaram a ser coletados, mas saíram
da configuração, dos dados e da tabela. Rial e dirham têm câmbio fixo contra o dólar,
então os dois pares repetem o EUR/USD (correlação de 0,98), e só existem desde
setembro de 2024.

**Rolagens:** o gap de WIN/WDO no dia de troca inclui a diferença entre contratos e
fica marcado (`is_roll_day`); na pergunta 1, esses dias saem do treino e do teste. Nos CFDs de Brent e cobre, o salto da reabertura em que
o contrato troca é descontado (17/11/2026).

**Marcação de rolagem como variável:** `x_pre_roll_day` (16/11/2026) repetia `is_roll_day`
como variável e saiu em 23/11/2026, quando os dias de rolagem saíram da pergunta 1.

**Amostra no período de análise:** 1.509 dias no WIN e 1.510 no WDO.

| Medida | WIN: checkpoint | WIN: atual | WDO: checkpoint | WDO: atual |
|---|---:|---:|---:|---:|
| Dias incluídos | 1.493 | 1.509 | 1.498 | 1.510 |
| Gaps calculados | 1.461 | 1.509 | 1.425 | 1.510 |
| Dias de rolagem marcados | 36 | 36 | 73 | 73 |

O primeiro dia do WIN (15/10/2020) não vira linha: o arquivo do professor começa às
11:49 e não há fechamento anterior. Seu fechamento continua servindo de D-1 para o
gap de 16/10/2020, mas o dia parcial não entra no histórico do alvo: o retorno do
pregão anterior de 16/10/2020 e a amplitude de 5 dias de 22/10/2020 ficam vazios.
As colunas `is_eligible` e `has_gap_in_data` foram retiradas em 16/11/2026: tinham
o mesmo valor em todas as linhas.

## Para onde vai o projeto

1. **Revisão dos módulos (desde 16/11/2026):** `e01` a `e05` revisados. Os relatórios anteriores citam
   nomes antigos: em 17/11/2026, `e04_features` e `e05_labels` viraram `e04_feat_labels`;
   em 23/11/2026, `e03_filtros` entrou no `e02_tratamento` e os seguintes foram
   renumerados (`e04_feat_labels` → `e03_feat_labels`, `e05_daily` → `e04_daily`,
   `e06_models` → `e05_models`, que virou `e05_validacao` quando os modelos passaram para
   `modeloN_*.py`).
2. **Decisões pendentes** (abaixo), antes de escolher as variáveis dos modelos.
3. **Análise exploratória:** já houve correlações e descrição dos rótulos no checkpoint;
   atualizar a análise depois das mudanças solicitadas.
4. **Modelos:** pergunta 1 concluída em 23/11/2026 (`modelo1_gap.py`, teste final lido;
   ver "Teste final da pergunta 1"). Perguntas 2 (comportamento) e 3 (faixa) saíram do
   escopo em 24/11/2026, por decisão do usuário.
5. **Backtest:** fora do escopo desde 24/11/2026 (dependia das perguntas 2 e 3).
6. **Relatório final.**

## Decisões pendentes

### Variáveis da pergunta 1

**Resolvido em 23/11/2026** (`estudo_gap.py`, só desenvolvimento, sem rolagem). Listas
congeladas (`LISTAS` no estudo):

- **WIN (11):** retorno da madrugada de S&P, Europe 50, Nikkei, A50, USD/MXN, AUD/USD,
  USD/ZAR, cobre e Brent, mais `range_5d` e `close_position`.
- **WDO (10):** retorno da madrugada de DXY, USD/MXN, AUD/USD, USD/ZAR, USD/CNH, S&P e
  cobre, agitação da madrugada do Europe 50 (`night_vol`), mais `range_5d` e
  `close_position`.

Como se chegou a elas: proposta por grupos com motivo econômico, um representante por par
quase repetido (S&P no lugar do Nasdaq, DXY no lugar de EUR/USD e USD/CHF, A50 no lugar do
Hang Seng). Rodada 1, tirando um grupo de cada vez: fizeram falta histórico do alvo, S&P e
moedas emergentes no WIN; moedas emergentes e DXY no WDO. Rodada 2: o núcleo sozinho é
pior; os grupos fracos juntos melhoram o log loss em 0,022 a 0,026 no WIN e 0,034 no WDO
(2 a 3 vezes o erro). Dólar global, cripto e agitação não fazem falta no WIN; Japão e
cripto não fazem falta no WDO. Rodada 3 (conferência): o Lasso nas 40 colunas manteve em
todas as janelas quase as mesmas variáveis (10 de 11 no WIN, 7 de 10 no WDO, trocando
algumas por parecidas, como FTSE por Europe 50) e foi pior que as listas em log loss (2 a 3
vezes o erro). A seleção passo a passo (forward) não foi feita: com dezenas de comparações
nos mesmos dias, ajustaria a lista ao acaso. Log loss com as listas (dois binários):
0,613 no WIN e 0,555 no WDO, contra 0,93 e 0,87 da frequência histórica.

### Dias com variável vazia

**Resolvido em 23/11/2026 (pergunta 1): o vazio vira zero só na entrada do modelo (B);
a tabela diária continua com o vazio.** A troca é feita em `modelo1_gap.py`. O retorno da madrugada de um ativo
fica vazio quando aquele mercado não negociou entre o fechamento da B3 e o corte
(feriado lá fora na madrugada) ou quando ficou parado no dia D-1 inteiro (feriado lá
fora em D-1, regra das 24 h de 23/11/2026). São 56 dias por alvo com algum vazio entre
19 ativos (eram 28 antes da regra das 24 h), e 133 com o Hang Seng (118 só dele). O `e05` hoje descarta o dia inteiro: sem previsão nesse dia e
sem o dia no treino. Opções: (A) descartar, como hoje; (B) tratar o vazio como zero só na
entrada do modelo, mantendo a tabela vazia; (D) árvores, que aceitam vazio. Estudo de
23/11/2026 com as listas da pergunta 1 (`estudo_gap.py --vazios`): nos dias completos, B
não muda o resultado (log loss −0,002 ± 0,002 no WIN e −0,002 ± 0,001 no WDO); nos dias
com vazio (37 no WIN, sobretudo A50 e Europe 50; 15 no WDO), B prevê bem melhor que a
frequência histórica (log loss 0,50 contra 0,88 no WIN e 0,71 contra 0,95 no WDO, 2,4 a
3,8 vezes o erro). Com A, esses dias ficariam sem previsão.

### Formato da logística na pergunta 1

**Resolvido em 23/11/2026: dois binários (alta contra o resto e baixa contra o resto), com
C fixo em 0,1 (`models.logistic_c`).** Estudo de 23/11/2026 (`estudo_gap.py --formato`, listas congeladas, vazio como zero).
Dois binários contra multinomial, em log loss: no WIN, +0,006 ± 0,002 com C fixo (0,1) e
+0,005 ± 0,004 com C escolhido no treino; no WDO, +0,002 ± 0,002 e +0,002 ± 0,003
(empate). Com C escolhido no treino (mediana 0,22), o WIN piora um pouco (0,617 contra
0,609) e o WDO melhora um pouco (0,555 contra 0,560).

Árvores com as mesmas variáveis (`estudo_gap.py --arvores`, 24/11/2026): random forest
(500 árvores, folha mínima de 20) piora o log loss em 0,060 ± 0,011 no WIN e 0,047 ± 0,010
no WDO; gradient boosting (profundidade 3), em 0,160 ± 0,030 e 0,164 ± 0,032. A logística
fica.

### Teste só com retornos da madrugada (24/11/2026)

Pedido do usuário: escolher as variáveis só entre os retornos da madrugada (`overnight`),
sem agitação (`night_vol`) nem histórico do alvo, pelo mesmo processo (`estudo_gap.py
--overnight`, rodadas 1 a 3, só desenvolvimento). Regra escrita para passar da rodada 1 à 2,
que reproduz as escolhas de 23/11: núcleo é o grupo cuja retirada piora o log loss em mais
de duas vezes o erro; fraco, o que piora pelo menos 0,001 nos dois formatos; o resto sai.

- **WIN (6):** S&P, USD/MXN, AUD/USD, USD/ZAR (núcleo), Nikkei e A50 (fracos; o bloco melhora
  o núcleo em 2,0 a 2,1 vezes o erro). Europa e dólar global quase não fazem diferença;
  tirar as commodities melhorou um pouco.
- **WDO (8):** DXY, USD/MXN, AUD/USD, USD/ZAR, USD/CNH (núcleo), S&P, cobre e Nikkei (fracos;
  o bloco melhora o núcleo em 2,5 a 2,6 vezes o erro).
- **Lasso nos 19 retornos:** empata com as listas (WIN −0,007 ± 0,010; WDO −0,003 ± 0,008) e
  mantém em quase todas as janelas as mesmas variáveis, mais algumas parecidas.

Comparação com o modelo atual (`--comparar-overnight`: vazio como zero, dois binários, C =
0,1, mesmos dias), em log loss:

| | WIN | WDO |
|---|---|---|
| Modelo atual | 0,609 (11 variáveis) | 0,560 (10 variáveis) |
| Atual sem as que não são overnight | 0,659 (−0,050 ± 0,009) | 0,575 (−0,015 ± 0,007) |
| Só overnight, escolhidas de novo | 0,663 (−0,054 ± 0,011) | 0,574 (−0,014 ± 0,007) |
| Frequência histórica | 0,931 | 0,870 |

Só com retornos da madrugada, o modelo piora: muito no WIN (5 vezes o erro) e no limite no
WDO (2 vezes). A perda vem das variáveis retiradas (histórico do alvo e, no WDO, a agitação
do Europe 50), que dizem o tamanho provável do gap; escolher os retornos de novo não
compensa. O modelo atual fica como está. O ano reservado não foi usado neste teste.

### Teste final da pergunta 1

**Lido uma única vez em 23/11/2026** (`modelo1_gap.py --final`; previsões em
`reports/modelo1_gap_final.csv`). Período reservado de 07/11/2025 a 06/11/2026, sem
rolagem, 4 janelas de 3 meses, cada uma treinada com os 2 anos anteriores. Nada da
pergunta 1 muda por causa deste resultado.

| | WIN | WDO |
|---|---|---|
| Dias | 241 | 235 |
| Log loss (frequência histórica) | 0,710 (1,076) | 0,466 (0,870) |
| Melhora sobre a frequência | 0,366 ± 0,057 | 0,404 ± 0,042 |
| Brier | 0,425 | 0,268 |
| ECE | 0,054 | 0,059 |
| AUC baixa / normal / alta | 0,88 / 0,77 / 0,89 | 0,92 / 0,88 / 0,94 |
| Acerto (balanceado) | 68,5% (60,3%) | 82,6% (66,6%) |

Comparação com o desenvolvimento (log loss 0,609 no WIN e 0,560 no WDO): o WDO ficou
melhor; o WIN, pior em log loss, mas a vantagem sobre a frequência histórica cresceu e
a AUC se manteve. No WIN o ano reservado teve mais gaps (53% de dias normais, contra
cerca de 70% em 2024-2025), e o desvio de calibração se inverteu: o modelo, treinado com
anos calmos, subestimou o gap (prevista 0,63 de normal, observada 0,49). É o mesmo
atraso do treino de 2 anos visto no desenvolvimento, no sentido oposto. No WDO a
proporção ficou parecida com a do treino (67% normais). Alta e baixa não se confundiram
nenhuma vez nos dois alvos; o erro continua sendo chamar de normal um gap real (WIN 54%
dos gaps, WDO 50%). Quando prevê gap, o modelo acerta 77% a 79% no WIN e 92% a 100% no
WDO.

Comparação com o checkpoint (12/11/2026; 13 ativos, limiar de 0,30% nos dois alvos, dias
excluídos por filtros), nos mesmos dias e com o mesmo rótulo. Período inteiro (out/2022 a
nov/2026): WIN 0,676 → 0,637 (+0,039 ± 0,012), WDO 0,489 → 0,467 (+0,022 ± 0,012); mas
nos anos de desenvolvimento as escolhas atuais foram feitas com esses mesmos dias, o que
favorece o modelo atual. Só no ano reservado, a comparação honesta: WIN empata (−0,025 ±
0,034); WDO melhora (0,463 → 0,380, +0,083 ± 0,027). No WDO, 77 dias com rótulo diferente
(gap entre 0,25% e 0,30%) ficam fora, porque o limiar mudou.

### Calibração da pergunta 1

Estudo de 23/11/2026 (`estudo_gap.py --calibracao`, modelo fechado, desenvolvimento).
Probabilidades razoavelmente calibradas: erro médio de calibração (ECE) de 0,047 no WIN e
0,043 no WDO, igual ao da multinomial. AUC de 0,88 a 0,89 para alta e baixa e 0,80 para
normal. Desvio sistemático: o modelo superestima gap e subestima normal (WIN: previsto
0,62, observado 0,72 na faixa de 0,5 a 0,7 de normal). Causa provável: a proporção de
dias normais subiu de cerca de 0,4 em 2020-2022 para 0,7 em 2024-2025, e o treino de 2
anos fica atrasado. Recalibrar com Platt dentro do treino piorou o log loss (WIN −0,021 ±
0,007; WDO −0,010 ± 0,007): não adotado. Matriz de confusão: alta e baixa quase nunca se
confundem (5 dias no WIN, 2 no WDO); o erro é chamar de normal um gap real (cerca de 40%
dos gaps no WIN e 50% no WDO). Quando prevê gap, acerta 69% a 77% das vezes.

Treinos que acompanhassem melhor essa mudança (`estudo_gap.py --recencia`, mesmos dias de
teste) não ajudaram. No WIN, 18 meses, 1 ano e peso maior nos dias recentes ficam dentro do
acaso (o melhor, 1 ano: +0,004 ± 0,008). No WDO, todos pioram: 1 ano −0,024 ± 0,007; 2 anos
com meia-vida de 1 ano −0,010 ± 0,003; meia-vida de 6 meses −0,025 ± 0,006. Treino mais
curto também fica atrasado (a probabilidade média de normal sobe só de 0,58 para 0,60 no
WIN, com 0,63 observado) e tem menos dias para aprender. **Mantido o treino de 2 anos sem
peso;** o atraso é uma limitação a registrar no relatório.

### Quarta-feira de Cinzas

**Resolvido em 16/11/2026.** Seis dias por alvo, com abertura às 13:00. As variáveis
externas paravam às 08:58, e mais de 4 horas de movimento lá fora entravam no gap sem
aparecer nelas. Os dias ficam na amostra, e o corte nesses dias passou para 12:58, dois
minutos antes da abertura das 13:00 (`special_cutoff_brt`). O calendário da B3 só diz
qual dia é a Cinzas; a hora fixa entrou em 23/11/2026 no lugar da hora de abertura da
biblioteca, com os mesmos cortes.

### Buracos na primeira hora

São 10 dias no WIN e 6 no WDO com velas faltando nos primeiros 60 minutos, em três
situações (causas pesquisadas em 17/11/2026). O gap não é afetado, porque usa só a
abertura; os dias ficam na amostra:

- **Falha da B3 no WIN:** 21/08/2025 (17 velas; buraco de 09:17 a 10:25) e 03/06/2025
  (8 velas; buraco de 09:04 a 09:55). Em 21/08/2025 a B3 informou falha no canal de
  market data dos derivativos e normalização às 10h10, depois do cancelamento de ofertas
  pelas corretoras. Em 03/06/2025 há só um relato de imprensa de instabilidade no mini
  índice e no mini dólar. O WDO desses dias está completo.
- **Paradas reais nas eleições:** 26/10/2026 (WIN 51 velas, WDO 46): circuit breaker no
  Ibovespa, o primeiro desde 2020. Antes do buraco o WIN fica parado em 177.215 e o WDO em
  5.430, com quase nenhum negócio, e reabrem em 166.790 e 5.610 com volume alto.
  05/10/2026 (WIN 51 velas): buracos de 1 a 2 minutos na primeira meia hora, com volume
  alto, típicos de leilões por oscilação forte depois do primeiro turno.
- **Falta de 1 a 3 velas:** 12 dias, sem efeito relevante.

Em todo o pregão, 25 dias do WIN e 18 do WDO têm algum minuto faltando entre a primeira
e a última vela. Um caso afeta o fechamento de D-1: o WDO de 27/09/2024 termina às
17:31 (512 velas), nas duas fontes; o WIN do mesmo dia vai até 18:24. Esse fechamento é
o D-1 de 30/09/2024, que já é dia de rolagem do WDO. A última vela, das 17:31, tem
6.072 negócios contra 100 a 300 nos minutos anteriores, o que parece um encerramento de
verdade, mas não foi encontrada notícia de encerramento antecipado. Causa não confirmada.

Fontes: [B3 sobre 21/08/2025](https://entrealtasebaixas.com.br/b3-informa-falha-operacional-no-mercado-de-derivativos/),
[relato de 21/08/2025](https://www.reclameaqui.com.br/b3/problema-b3-mini-indice-21-08_S1DlCMU0KLdc1uKq/),
[instabilidade de 03/06/2025](https://www.mixvale.com.br/2025/06/03/b3-enfrenta-volatilidade-com-dolar-em-alta-e-incertezas-no-iof-com-haddad/),
[circuit breaker de 26/10/2026](https://www.seudinheiro.com/2026/bolsa-dolar/circuit-breaker-o-que-e-botao-do-panico-da-bolsa-acionado-apos-a-reeleicao-de-lula-lmrs/).

### Rolagem do WIN e do WDO

**Resolvido em 23/11/2026: na pergunta 1, os dias de rolagem saem do treino e do teste**
(substitui a opção A de 17/11, que mantinha os dias com a marcação). O gap do dia de
rolagem compara a abertura do contrato novo com o fechamento do velho, então o rótulo
"alta" nesses dias mede a troca de contrato. Com a marcação, o modelo acertava 18 de 18
no WIN só por saber o calendário; a marcação não corrige o rótulo. Nos dias sem rolagem,
as duas opções davam o mesmo resultado. O salto acompanha os juros (WIN +0,25% em 2020,
cerca de +2,1% em 2025-2026; WDO cerca de +0,5%, 7 de 73 negativas); corrigir o rótulo
pela média das rolagens anteriores foi considerado e não adotado. A tabela mantém os
dias e `is_roll_day`; a exclusão é feita no modelo.

### Rolagem do Brent e do cobre

**Resolvido em 17/11/2026: o salto é descontado.** A troca tem assinatura clara: a
pausa diária fica mais longa (Brent: 200–201 min em vez de 181, 55 vezes; cobre: 80–81
min em vez de 61, 24 vezes) e o salto sai quase sempre para o mesmo lado (Brent −0,9%
em média; cobre +0,5%). No Brent, o WTI não acompanha o salto. Na reabertura da troca
conta só o que a vela andou; exemplo: em 25/09/2026 o overnight do Brent passou de
−8,33% para −1,38%. Mudaram só essas noites (55 do Brent, 24 do cobre, por alvo). No
estudo da pergunta 1 as versões empataram; descontar foi levemente melhor nas noites
de troca e não perde dias, ao contrário de deixar a variável vazia.

### Período reservado

**Resolvido em 17/11/2026:** de 07/11/2025 a 06/11/2026 (cerca de 250 pregões por alvo)
fica reservado para o teste final, lido uma única vez, com todas as escolhas congeladas.
Os estudos usam só os dados até `walk_forward.dev_end`. Com 250 dias, a melhora do
modelo sobre a frequência histórica é medida com erro de cerca de ±0,04 (a melhora no
desenvolvimento é de 0,34). Ressalva: antes de 16/11/2026, alguns testes rápidos e os
relatórios do Codex usaram o período inteiro; as decisões que saíram deles foram
reconfirmadas só com o desenvolvimento.

### Estudo da pergunta 1 (16/11/2026)

O estudo da pergunta 1 (script e relatório apagados em 23/11/2026) comparou variáveis,
tratamentos de rolagem e limiares no período de desenvolvimento (até 06/11/2025; os 12
meses seguintes ficaram reservados). Aplicado em 17/11/2026: posição do fechamento no
lugar do retorno do pregão anterior, e média da `night_vol` no lugar das colunas por
ativo (em 23/11/2026 as colunas por ativo voltaram à tabela e a média saiu). Variáveis que ficaram dentro do acaso (melhora menor que duas vezes o erro) não
entram. Ainda à espera de decisão: limiar de 0,30% no WIN e 0,25% no WDO (no WDO, o
limiar móvel não foi melhor que 0,25%). Para a pergunta 1, o tratamento da rolagem do
Brent e do cobre não muda o resultado. Na rolagem do WIN/WDO, a marcação empata com o
rótulo vazio nos dias sem rolagem e é muito melhor nos dias de rolagem.

### Limiar do gap

**Resolvido em 17/11/2026:** 0,30% no WIN e 0,25% no WDO (`labels.gap_threshold`). O
do WDO deixa a mesma proporção de dias normais que o do WIN nos dois primeiros anos,
que só servem de treino. O limiar móvel e o limiar por quantil do treino foram testados
e não foram melhores. Com 0,25%, o WDO passou de 1.008 para 884 dias normais. Limitação:
os gaps encolheram de 2020 a 2023, e com limiar fixo os anos recentes têm menos dias
de gap.

## Suposições em aberto

- **Abertura tardia do WIN:** desde out/2025, o primeiro candle costuma sair às 09:02 ou
  09:03. O volume até 09:10 indica abertura real mais tarde, não candles perdidos. As duas
  fontes mostram o mesmo padrão, mas vêm do mesmo feed, então isso não é confirmação.
- **Rolagem do WDO:** a série troca no último pregão do mês, um dia antes do vencimento.
  A regra é confirmada nos dados, mas a causa não foi confirmada com a corretora.
- **Histórico da Genial:** a hipótese é que a corretora guarda só os últimos 5 anos. Uma
  nova exportação perderia o começo.
- **Dukascopy:** os dias mais recentes ainda podem ganhar velas depois; a ferramenta omite
  velas de volume zero. Uma parada da fonte no meio da noite é indistinguível de uma
  parada do mercado.
