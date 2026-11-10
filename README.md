# Classificação da abertura da B3

Projeto da disciplina Data Science para Mercado Financeiro (UFG). Usa o que acontece
no exterior entre o fechamento da B3 e a abertura do dia seguinte para prever os
primeiros 60 minutos do pregão do mini índice (WIN) e do mini dólar (WDO). As
definições e regras completas estão no [AGENTS.md](AGENTS.md).

**Estado atual:** os dados estão coletados, tratados e reunidos na tabela diária. Os
módulos estão em revisão, um por vez, antes da análise exploratória e dos modelos (ver
"Para onde vai o projeto").

## Enunciado do professor (quadro)

Transcrição do quadro com os modelos propostos na disciplina; o Modelo 1 não aparece
na foto. Este projeto é o **Modelo 3**. A classificação pedida no quadro corresponde à
pergunta 1 do projeto; as perguntas 2 e 3 são extensões do grupo (AGENTS.md, seção 1).

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
uv run --locked python -m abertura.e01_download --end 2026-11-07   # externos (~16 min)
uv run --locked python -m abertura.e02_tratamento                   # Parquets (~40 s)
uv run --locked python -m abertura.e06_daily                        # tabela diária (~5 s)
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
| `e02_tratamento.py` | sim | lê os CSVs, converte para UTC, emenda WIN/WDO e grava um Parquet por ativo em `data/tratamento/` |
| `e03_filtros.py` | não (usado pelo e06) | calendário da B3, pregões elegíveis e dias de rolagem |
| `e04_features.py` | não (usado pelo e06) | variáveis `x_pre_` e `x_open_` |
| `e05_labels.py` | não (usado pelo e06) | rótulos `y_` |
| `e06_daily.py` | sim | tabela diária `data/processed/daily.parquet` |
| `e07_models.py` | não (análise) | modelos, walk-forward e métricas |

## Configuração

Tudo fica em `config/params.yaml`:

- `targets`: WIN e WDO, os dois arquivos de cada um, a data de troca entre eles e o fuso.
- `externals`: os 13 ativos externos e o código de cada um na Dukascopy.
- `download`: início, paralelismo, tentativas e tempo limite da coleta.
- `features`, `sample`, `labels`, `models`, `walk_forward`, `backtest`: parâmetros das
  etapas seguintes. O período de análise (`sample`) vai de 15/10/2020 a 06/11/2026.

## Dados

| Pasta | Conteúdo |
|---|---|
| `data/raw/feature/<ativo>/<início>_<fim>.csv` | externos da Dukascopy, um CSV por mês, UTC, preço bid |
| `data/raw/target/` | WIN e WDO exportados do MetaTrader (ver abaixo) |
| `data/tratamento/<ativo>_m1.parquet` | 1 minuto padronizado: `datetime` (UTC), `open`, `high`, `low`, `close`, `volume` |
| `data/processed/daily.parquet` | uma linha por pregão e alvo, com variáveis, rótulos e marcações |
| `data/staging/` | temporários do download |

Toda a pasta `data/` fica fora do Git. `data/raw/` nunca é editado.

**WIN e WDO** emendam duas exportações do terminal MetaTrader, em horário de Brasília:

- `WIN-professor.csv` e `WDO-professor.csv`: arquivos do professor, usados até 05/11/2021.
- `WIN-metaTrader.csv` e `WDO-metaTrader.csv`: séries `WIN$N` e `WDO$N` exportadas do
  MT5 da Genial em 08/11/2026, usadas a partir de 08/11/2021. A Genial guarda só cerca
  de 5 anos; por isso o começo vem do professor. Nos dias em comum, 99,99% das velas
  das duas fontes são idênticas.

**Externos:** S&P 500, Nasdaq 100, Europe 50, FTSE 100, Nikkei, China A50, Brent, ouro,
DXY, USD/MXN, cobre, EUR/USD e USD/JPY. São CFDs da Dukascopy, não os índices oficiais
nem os futuros em bolsa. O volume da Dukascopy não é volume real negociado.

**Rolagem do Brent e do cobre:** esses dois CFDs seguem o contrato futuro e trocam de
vencimento na pausa diária da Dukascopy, com um salto falso de preço (no Brent, em média
−0,9% e até −7% em 2026, quando a curva do petróleo ficou extremamente inclinada). Os
retornos desses dois ignoram a variação de toda reabertura depois de pausa de 30 min a
12 h (`daily_pause_assets` em `config/params.yaml`); a reabertura de fim de semana é
mantida, porque concentra notícia real (ex.: +16% em 09/03/2026, guerra com o Irã).
Custo: perde o movimento real da pausa, em média 0,2% no Brent e 0,04% no cobre.

**Amostra no período de análise:** 1.510 pregões, todos com dados nos dois alvos.

| | WIN | WDO |
|---|---:|---:|
| Pregões elegíveis | 1.493 | 1.498 |
| Fora por Quarta-feira de Cinzas | 6 | 6 |
| Fora por janela de abertura incompleta | 10 | 6 |
| Fora por ser o 1º dia do histórico (15/10/2020) | 1 | 0 |
| Dias de rolagem (gap vazio) | 36 | 73 |

`reports/` guarda resultados de uma análise anterior à emenda e ao download atual (relatório
de qualidade, correlações, matrizes de confusão, gráficos e uma pesquisa de índices
asiáticos não adotados). Os números ali não refletem os dados atuais e serão refeitos
na análise exploratória.

## Para onde vai o projeto

1. **Revisão dos módulos (em andamento):** `e01` a `e04` revisados; faltam `e05_labels`,
   `e06_daily` e `e07_models`.
2. **Decisões pendentes** (abaixo), antes de escolher as variáveis dos modelos.
3. **Análise exploratória:** correlações, distribuição dos gaps e taxas de fechamento do
   gap, com os dados atuais.
4. **Modelos:** linhas de base e regressão logística, depois gradient boosting, com
   probabilidades calibradas, em walk-forward (2 anos de treino, 3 meses de teste).
5. **Backtest** (`e08_backtest.py`, ainda não existe): entrada na vela seguinte à
   abertura, alvo e stop pela faixa prevista, custos e slippage.
6. **Relatório final.**

## Decisões pendentes

### Regra de negociação para `prev_day` e `session`

**Quando decidir:** antes de escolher as variáveis dos modelos.

Cada variável externa só existe se o ativo teve alguma vela no intervalo que ela mede;
senão fica vazia, em vez de virar zero num feriado lá fora. Para `overnight`,
`last_60m`, `last_180m` e `night_vol` isso está decidido (28 pregões do WIN ficam com
algum desses vazios, quase todos feriados lá fora). A mesma regra está aplicada, **ainda
sem decisão**, ao `prev_day` (vela entre D-2 e D-1) e à `session` asiática (vela no
pregão local).

Com ela, os pregões elegíveis do WIN com todas as variáveis preenchidas são 1.434 de
1.493; sem ela, seriam 1.456.

1. Manter (estado atual): mesma lógica para todas as variáveis.
2. Voltar `prev_day` e `session` a zero em feriado lá fora.

### Limiar do gap

O AGENTS.md (seção 5) pede que o limiar entre gap e abertura normal seja escolhido só
com dados de treino. Hoje ele está fixo em 0,3% (`labels.gap_threshold`). Decidir na
revisão do `e05_labels`.

### Custos

Emolumentos e corretagem por contrato estão vazios em `backtest.contracts`. Precisam
ser definidos antes do backtest.

## Suposições em aberto

- **Fuso das exportações do MetaTrader:** assumido como Brasília. É coerente com os dados
  (abertura às 09:00, 13:00 na Quarta-feira de Cinzas), mas falta confirmação da corretora.
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
