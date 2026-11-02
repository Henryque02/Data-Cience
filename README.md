# Classificação da abertura da B3

Projeto da disciplina Data Science para Mercado Financeiro, UFG. A coleta
preserva informações internacionais anteriores à abertura e candles M1 de
WIN/WDO para estudar o comportamento posterior. Já há tabela diária e uma
primeira avaliação em walk-forward; o backtest com custos fica para uma fase futura.

## Começar pelo notebook

O roteiro desta etapa é [01_dados_e_qualidade.ipynb](notebooks/01_dados_e_qualidade.ipynb).
Ele já está executado, com amostras reais, conversão de horário, os 15 Parquets,
mapa de cobertura mensal e diagnósticos de WIN/WDO. Abra no VS Code/Jupyter
e escolha o Python da pasta `.venv` para executar as células em ordem.

Na célula de parâmetros, você pode trocar o alvo, o ativo externo, o dia de
exemplo, o fuso assumido do CSV MT5 e o tamanho dos intervalos a investigar.
As funções reutilizáveis ficam em `src/abertura`; o notebook é o roteiro e a
interface de exploração. Reexecutar com as mesmas entradas reaproveita os
Parquets após conferir hashes e parâmetros.

## Ambiente

Usar [uv](https://docs.astral.sh/uv/) e Node.js 22 ou superior. A versão inicial
de Python é 3.12; `uv.lock` e `package-lock.json` fixam as dependências.

Na raiz do repositório, executar nesta ordem:

```bash
uv sync --locked --group notebook --cache-dir data/cache/uv
npm ci --ignore-scripts --no-audit --no-fund --cache data/cache/npm
uv run --locked --cache-dir data/cache/uv pytest
```

O grupo de desenvolvimento instala pytest por padrão. O extra `mt5` é reservado
ao Windows; a coleta dos externos funciona no Linux. O scikit-learn faz parte
das dependências principais; outras bibliotecas de modelos serão acrescentadas
quando houver código que as utilize. Caso uma entrega exija requirements.txt:

```bash
uv export --locked --no-dev --format requirements.txt --output-file requirements.txt
```

O grupo `notebook` contém ipykernel, nbformat, nbclient e matplotlib. O
calendário é `exchange-calendars/BVMF`, fixado no lockfile. NumPy fica abaixo
de 2.5 para evitar a descontinuação de timedelta genérico usada pelo pandas 2.x.

## Ativos definidos

`config/assets.yaml` contém os 13 externos: S&P 500, Nasdaq 100, Europe 50,
FTSE 100, Nikkei, China A50, Brent, ouro, DXY, USD/MXN, cobre, EUR/USD e USD/JPY.
São as séries disponíveis na Dukascopy: distinguir seus instrumentos/proxies
dos índices oficiais e dos futuros negociados em bolsa.

US T-Bond foi excluído pelo usuário. TOPIX, CSI 300 e Shanghai Composite ficam
fora da coleta atual. As fontes e limitações estão no relatório de pesquisa
em `reports/Histórico dos índices asiáticos.md`.

## Ordem da coleta

Primeiro, validar duas amostras de dois dias por ativo, em 2020 e 2026:

```bash
uv run --locked --cache-dir data/cache/uv python scripts/download_dukascopy.py --pilot
```

O piloto efetivamente executado retornou **26 blocos válidos e nenhuma falha**,
inclusive DXY M1. O cabeçalho real é
`timestamp,open,high,low,close,volume`: timestamp em milissegundos Unix UTC,
referente à abertura do candle. A amostra real reduzida está em tests/fixtures.

Depois, coletar o histórico. O limite superior é **exclusivo**; o comando
abaixo solicita até o fim de 30/10/2026, último dia útil completo quando esta
coleta começou:

```bash
uv run --locked --cache-dir data/cache/uv python scripts/download_dukascopy.py --start 2020-09-01 --end 2026-10-31 --workers 3
```

Repetir exatamente o comando retoma a coleta: blocos existentes só são
reutilizados se manifesto, parâmetros e SHA256 corresponderem. Os equivalentes
são `bash scripts/download_dukascopy.sh ...` e, no PowerShell,
`.\scripts\download_dukascopy.ps1 ...`.

Para atualizar futuramente, omitir `--end` usa o início do dia UTC corrente
como limite, preservando apenas dias UTC completos. Um mês parcial anterior
pode se sobrepor ao novo mês solicitado; a padronização futura deve conciliar
essas sobreposições e rejeitar preços conflitantes, preservando os brutos.

Para selecionar ativos ou conferir as requisições sem rede:

```bash
uv run --locked --cache-dir data/cache/uv python scripts/download_dukascopy.py --assets gold eurusd --start 2026-10-01 --end 2026-10-31 --plan
```

## Arquivos e integridade

- `data/raw/dukascopy/<id>/<início>_<fim-exclusivo>.csv`: saída original da CLI.
- `data/raw/dukascopy_pilot/<id>/`: amostras do piloto, separadas do histórico.
- `data/raw/professor/`: cópias idênticas dos arquivos de WIN/WDO em `gg/`.
- `data/metadata/`: parâmetros, cabeçalhos, períodos recebidos, SHA256 e resultados.
- `data/logs/`: saída da ferramenta por bloco.
- `data/cache/dukascopy/`: cache oficial da ferramenta para retomar requisições.
- `data/staging/`: temporários durante a aquisição, publicados após validação.

A importação dos arquivos do professor acontece ao final da coleta. Os
originais são preservados e seus hashes são registrados. Não juntar preços
de fontes B3 diferentes antes de comparar os períodos comuns e a continuidade.

CSV vazio, preços inválidos, timestamps fora do intervalo, desordem ou
duplicatas causam falha explícita. Nenhum preço é interpolado. Um bloco
recebido com sucesso **não comprova cobertura integral dos pregões**: feriados,
pausas normais, dias sem candles e buracos serão auditados na limpeza.
O volume é específico da fonte e não deve ser interpretado como volume
negociado real dos ativos de referência. `SPREAD` dos arquivos do professor
não será usado como variável.

Todo `data/` está ignorado no Git. Os brutos foram convertidos para os 15
arquivos `data/interim/<id>_m1.parquet`, com compressão Zstandard via pyarrow.
O schema tem seis colunas: datetime (datetime64[ns, UTC]), open, high, low,
close e volume (float64). Os dados estão ordenados e sem duplicatas.

Os leitores em `src/abertura/io.py` distinguem CSV TAB do MT5, exportação da
API MT5 (epoch em segundos UTC) e Dukascopy (epoch em milissegundos UTC).
O CSV do professor usa `<VOL>`, sem substituição silenciosa por `<TICKVOL>`.
Apenas duplicatas integralmente idênticas são removidas; preço ou volume
conflitante no mesmo timestamp interrompe a conversão. Não houve duplicatas
removidas nos arquivos atuais.

A mesma conversão do notebook está disponível em:

```bash
uv run --locked --cache-dir data/cache/uv python scripts/build_interim.py
```

Metadados com hashes, parâmetros e contagens ficam em `data/metadata/interim/`.
Manifests de aquisição existentes também precisam corresponder ao ativo,
símbolo, M1, UTC, lado bid e presença de volume. Arquivos colocados manualmente
sem manifesto recebem hash próprio, mas não são descritos como verificados
contra um registro de aquisição anterior.

## Auditoria inicial de qualidade

O notebook gerou [o relatório de qualidade](reports/qualidade_dados.md),
gráficos em `reports/figures/`, contagens pequenas em
`reports/cobertura_mensal.csv` e tabelas de diagnóstico em `data/quality/`.

No calendário de referência entre 01/09/2020 e 30/10/2026, foram identificados
**114 pregões esperados sem registros dentro do histórico de WIN e 91 no de
WDO**. Os limites anteriores e posteriores à cobertura de cada fonte ficam
separados dessas ausências internas.

O calendário BVMF fornece datas e aberturas especiais. Seu horário de ações
não é aplicado aos futuros: a referência regular de WIN/WDO é 09:00 BRT,
com 13:00 na Quarta-feira de Cinzas. O último candle é medido dia a dia,
sem impor fechamento fixo.

A abertura de cada dia é o primeiro candle observado, e a janela inicial é
contada a partir dele. Um pregão regular é elegível quando esse candle vem até
15 minutos depois da referência (`sample.max_open_delay_minutes`) e a janela
não tem minutos faltando. Atrasos maiores indicam dia truncado na fonte. Com
essa regra, **1.351 pregões de WIN e 1.272 de WDO são elegíveis**, 1.226 nos
dois ativos. Os dias continuam no interim; a elegibilidade é uma marcação em
`data/quality/`, e rolagem ou variáveis ainda podem tirar dias da amostra.

Para os externos, os intervalos vazios não são classificados como falhas
confirmadas sem o calendário da fonte CFD. Não se usa automaticamente o
calendário do índice à vista como se fosse o mesmo instrumento.

## Tabela diária e matriz de confusão

`data/processed/daily.parquet` tem uma linha por pregão e alvo, com variáveis
`x_pre_` e `x_open_`, rótulos `y_` e marcações como `is_roll_day`. Para gerar:

```bash
uv run --locked --cache-dir data/cache/uv python scripts/build_daily.py
```

O notebook [02_correlacao_e_matriz_confusao.ipynb](notebooks/02_correlacao_e_matriz_confusao.ipynb)
mostra a rolagem, as correlações e as matrizes de confusão, em walk-forward de
2 anos de treino e 3 meses de teste. Os números estão no
[relatório](reports/correlacao_e_matriz_confusao.md).

O tipo de abertura tem sinal nos dois alvos: o log loss cai de 0,965 para 0,671
no WIN e de 0,730 para 0,493 no WDO, contra a linha de base. O comportamento
depois da abertura não tem sinal nesta primeira avaliação: o log loss da
regressão logística fica acima da linha de base nos dois alvos. Ainda faltam
gradient boosting, curva de calibração e backtest com custos.

## Suposições em aberto

- Fuso dos CSVs do professor: hipótese America/Sao_Paulo. A abertura mais
  frequente é 09:00 nos dois ativos, coerente internamente com a hipótese;
  falta confirmação independente com a corretora. A API Python MT5 retorna
  UTC, um formato distinto.
- Símbolos e profundidade do histórico MT5 dependem da corretora do grupo;
  aguardar os arquivos do amigo que opera o terminal no Windows.
- Rolagem: as datas de WIN e WDO vêm de regra de calendário confirmada nos gaps
  da série, sem ajustar preços. A causa exata da troca do WDO um pregão antes do
  vencimento não foi confirmada com a corretora. Possíveis mudanças de contrato
  nos instrumentos externos não foram investigadas.
- Disponibilidade dos externos: no corte de 08:58 BRT, de 98,7% a 100% dos
  pregões têm preço com até 5 minutos, conforme o ativo. Acima de 60 minutos a
  idade salta para dias inteiros. As datas parecem feriados daquele mercado, mas
  não foram conferidas em calendário, e o EUR/USD tem uma falha aparente em
  2024-12-05.
- O padrão da ferramenta omite candles de volume zero; ausência de candle
  pode representar essa regra, fechamento normal ou falha. Não inferir a causa
  antes da auditoria por instrumento.
- Abertura tardia: o primeiro candle veio depois das 09:00 em até 74% dos
  pregões recentes do WIN (tabela por trimestre no relatório de qualidade). A
  hipótese é abertura real mais tarde, apoiada pelo volume até 09:10 e pelo WDO
  abrir às 09:00 nesses dias. Falta confirmar com a corretora ou o professor; se
  for falha da fonte, a regra de entrada e a elegibilidade precisam ser revistas.
- Custos reais, rótulos de comportamento e regra de saída continuam pendentes;
  valores iniciais em config/params.yaml não representam estratégia validada.

## Resultado da coleta inicial

Em 02/11/2026, o histórico solicitado foi concluído: **962 blocos, 26.228.157 candles e 1.45 GB de CSV**, nos 13 ativos, sem falhas. Os hashes dos 962 blocos, dos 26 arquivos do piloto e das duas cópias do professor foram conferidos. Veja [períodos e quantidades por ativo](reports/coleta_dados.md).

A padronização reuniu **27.703.105 candles nos 15 Parquets UTC**, incluindo
WIN/WDO do professor. A auditoria inicial e os gráficos estão salvos no
notebook.
