# Plano de implementação da coleta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Baixar e verificar os datasets brutos autorizados, com retomada.

**Architecture:** Python coordena a CLI local dukascopy-node fixada pelo npm.
Blocos mensais recebem manifesto de aquisição e SHA256 após validação.
O histórico só começa após o piloto confirmar os formatos reais.

**Tech Stack:** Python 3.12, uv, PyYAML, pytest, Node.js e dukascopy-node 1.51.1.

**Spec:** docs/superpowers/specs/2026-11-02-coleta-dados-design.md

## Global Constraints

- UTC; candles M1 rotulados pela abertura; preço bid; incluir volume e cache.
- Nunca editar CSV bruto nem fabricar preços ou preencher buracos.
- Janela desde 2020-09-01; limite superior exclusivo no início do dia UTC.
- Dados e caches fora do Git; dependências e ferramentas com lockfile.
- Sem dependência do MT5 no Linux; arquivos do professor preservados.

## Review Focus

- Interrupções não podem certificar arquivos parciais como concluídos.
- Retomada deve conferir conteúdo e configuração, não apenas existência.
- Datas mensais devem ser contíguas e exclusivas no limite superior.
- CSV vazio, cabeçalho alterado ou preços inválidos devem aparecer como falha.
- Falha de um ativo não deve apagar os blocos válidos dos demais.

## Task 1: Ambiente e inventário

**Files:** pyproject.toml, .python-version, package.json, config/assets.yaml,
config/params.yaml, .gitignore e AGENTS.md.

**Interfaces:** inventário YAML com id/fonte/símbolo e defaults de download.

- [x] Criar configuração com os 13 ativos e exclusões acordadas.
- [x] Instalar com uv e npm, gerando lockfiles e registrando versões reais.
- [x] Atualizar AGENTS.md para uv e decisões de aquisição, sem mudar seção 5.

## Task 2: Coleta retomável e testes

**Files:** src/abertura/download.py, scripts/download_dukascopy.py,
scripts/download_dukascopy.sh, scripts/download_dukascopy.ps1,
tests/test_download.py e tests/fixtures/.

**Interfaces:** month_windows(start: date, end: date); inspect_csv(path, start,
end) -> dict; download_chunk(...) -> dict; main(argv=None) -> int.

- [x] Escrever e executar testes para meses, CSV UTC inválido e retomada.
- [x] Implementar execução sem shell, gravação atômica e manifesto SHA256.
- [x] Conferir sucesso, falhas, arquivos alterados e reexecução sem rede nos testes.
- [x] Rodar uv run pytest antes da coleta.

## Task 3: Piloto e histórico

**Files:** data/raw/dukascopy/, data/raw/professor/, data/metadata/,
README.md e reports/coleta_dados.md.

- [x] Executar piloto para 2020-09-01–03 e 2026-10-29–31.
- [x] Conferir cabeçalho real e timestamps; documentar ativos indisponíveis.
- [x] Executar histórico mensal com cache, logs e retomada.
- [x] Copiar arquivos do professor sem alterar bytes e registrar SHA256.
- [x] Consolidar cobertura e falhas, atualizar README e rodar pytest.
- [x] Fazer revisão independente do coletor e corrigir problemas relevantes.

## Registro de execução

Ruling: executar na pasta compartilhada solicitada, sem commits ou worktree
adicional; preservar todos os arquivos e alterações pré-existentes.
Ruling: autorização mais recente permite executar downloads; substitui a
preferência inicial por execução manual. Não pedir nova aprovação funcional;
solicitar apenas liberações de rede exigidas pelo sandbox.

Task 1: complete — uv sync e npm install concluídos, lockfiles gerados.
Task 2: complete — 20 testes passando. Os dois problemas de interrupção/retomada da revisão independente foram reproduzidos em testes falhando e corrigidos.
Piloto: 26/26 blocos válidos nos 13 ativos, incluindo DXY M1; cópias do professor com SHA256.
Ruling: após o piloto, usar lote padrão 10 da ferramenta e quatro trabalhadores na coleta histórica; cache e blocos anteriores preservados no reinício.

Task 3: coleta histórica concluída — 962/962 blocos, zero falhas; hashes históricos, piloto e professor conferidos. Auditoria: data/metadata/audit_20261102.json.
