# Coleta dos dados de abertura

Implementar e executar a coleta autorizada dos ativos externos em M1, UTC,
com volume, preço bid e cache. A janela começa em 2020-09-01 e termina no
início do dia UTC corrente, excluindo candles do dia ainda incompleto.

Decisões do usuário: uv com pyproject.toml e uv.lock; piloto antes do histórico;
processo principal no Linux, recebendo MT5 depois. Coletar spx, ndx, sx5e,
ftse, nikkei, a50, brent, gold, dxy, usdmxn, copper, eurusd e usdjpy.
Excluir US T-Bond, TOPIX, CSI 300 e Shanghai Composite. Não ampliar agora
para candidatos que ainda não tiveram instrumento e fonte definidos.

Alternativas discutidas: coleta enxuta de oito ativos ou coleta ampla.
O usuário escolheu a ampla. O acesso MT5 pelo Windows fica independente;
copiar os CSVs existentes do professor preservando os originais e seus hashes.

Baixar primeiro pequenas amostras em 2020 e em outubro de 2026. Inspecionar o
cabeçalho real, o timestamp, os preços e a disponibilidade de cada instrumento.
Depois coletar em blocos mensais, com arquivos brutos imutáveis, manifesto
SHA256, log e retomada por blocos verificados. Um bloco vazio não comprova
ausência de mercado e não deve ser certificado como concluído.

Não definir agora regras de operação, rótulos, modelos ou tratamento de rolagem.
O resultado desta etapa são arquivos brutos, metadados de aquisição e um resumo
da cobertura recebida; padronização Parquet e limpeza vêm depois.
