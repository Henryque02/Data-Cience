# Plano do notebook de dados

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar e executar notebook que padroniza os 15 ativos e mostra qualidade.
**Architecture:** Leitores e padronização em src/abertura/io.py e interim.py;
calendário e diagnósticos em sessions.py e quality.py. Notebook chama essas
funções, exibe dados e permite ajustar parâmetros de investigação.
**Tech Stack:** uv, pandas, numpy, pyarrow, exchange-calendars, Jupyter, matplotlib.
**Spec:** docs/superpowers/specs/2026-11-02-notebook-dados-design.md

## Global Constraints

- Raw imutável; nenhum preço inventado ou interpolado.
- datetime64[ns, UTC]; apenas exibição em America/Sao_Paulo.
- Duplicatas idênticas podem ser removidas; conflitantes geram erro.
- SPREAD descartado; volume escolhido por fonte sem misturar real e tick.
- Sem regras de estratégia ou decisões de rolagem nesta etapa.

## Review Focus

- Fuso do CSV MT5 versus epoch UTC da API; nenhuma dupla conversão.
- Arquivos sobrepostos e preços conflitantes não podem passar silenciosamente.
- Feriados, fim de semana e abertura especial não são buracos de preço.
- Calendário de ações não determina fechamento nem abertura regular de futuros.
- Notebook deve executar da primeira à última célula e limitar a memória usada.

## Task 1: Leitores e conversão

**Files:** src/abertura/io.py, src/abertura/interim.py,
scripts/build_interim.py, tests/test_io.py, tests/test_interim.py.
**Interfaces:** read_dukascopy_csv(path), read_mt5_csv(path, timezone),
read_mt5_api_csv(path), normalize_candles(frame), build_asset(id, ...), build_all(...).

- [ ] Criar fixtures pequenas a partir dos arquivos reais.
- [ ] Escrever e observar falhar testes de UTC, volume, schema, ordem e conflitos.
- [ ] Implementar leitores, validação e publicação Parquet atômica.
- [ ] Testar retomada e preservar saída anterior quando um dado novo conflitar.

## Task 2: Diagnósticos

**Files:** src/abertura/sessions.py, src/abertura/quality.py,
tests/test_quality.py, config/params.yaml.
**Interfaces:** b3_sessions(start,end), daily_sessions(frame),
coverage_table(...), missing_session_dates(...), candle_gaps(frame,...).

- [ ] Testes de feriados, abertura especial, ausência de pregão e intervalo intradiário.
- [ ] Implementar diagnóstico com classificações e limites explícitos.
- [ ] Registrar saídas detalhadas em data/quality e resumo em reports.

## Task 3: Notebook executado

**Files:** notebooks/01_dados_e_qualidade.ipynb, README.md,
pyproject.toml/uv.lock, reports/qualidade_dados.md.

- [ ] Instalar grupo notebook e calendário pelo uv.
- [ ] Criar narrativa, células editáveis, exemplos e gráficos.
- [ ] Executar padronização completa e todas as células com dados reais.
- [ ] Conferir schema e hashes dos Parquets, executar pytest e revisar código.

## Execução

Autorização: pedido direto do usuário para esta etapa, com notebook como roteiro.
Trabalhar no workspace compartilhado e preservar alterações anteriores.
Calendário de referência não elimina a necessidade de validar a fonte/corretora.
