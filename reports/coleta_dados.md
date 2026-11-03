# Coleta dos dados

Coleta realizada em 2 de novembro de 2026, com dukascopy-node 1.51.1, preço bid, M1, UTC, volume e cache.

Foram recebidos **962 blocos mensais dos 13 ativos**, com **26.228.157 candles** e **1.45 GB de CSV**, sem falhas de aquisição. O piloto anterior teve 26 blocos válidos. A conferência posterior de todos os hashes SHA256 não encontrou divergências.

Janela solicitada: `[2020-09-01, 2026-10-31)` UTC, incluindo até 30/10/2026. As datas abaixo são as efetivamente observadas, em UTC; dias UTC não equivalem a pregões da B3.

| Ativo | Primeiro candle UTC | Último candle UTC | Candles | Dias UTC com dados | Blocos |
|---|---|---|---:|---:|---:|
| spx | 2020-09-01 00:00:00 | 2026-10-30 20:14:00 | 2.081.188 | 1.919 | 74 |
| ndx | 2020-09-01 00:00:00 | 2026-10-30 20:14:00 | 2.111.355 | 1.919 | 74 |
| sx5e | 2020-09-01 06:00:00 | 2026-10-30 20:59:00 | 1.166.863 | 1.577 | 74 |
| ftse | 2020-09-01 00:00:00 | 2026-10-30 21:00:00 | 2.063.447 | 1.900 | 74 |
| nikkei | 2020-09-01 00:00:00 | 2026-10-30 20:14:00 | 2.013.398 | 1.916 | 74 |
| a50 | 2020-09-01 01:00:00 | 2026-10-30 20:29:00 | 1.713.745 | 1.581 | 74 |
| brent | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 1.976.028 | 1.593 | 74 |
| gold | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 2.186.890 | 1.917 | 74 |
| dxy | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 1.929.215 | 1.595 | 74 |
| usdmxn | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 2.270.278 | 1.926 | 74 |
| copper | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 2.133.764 | 1.917 | 74 |
| eurusd | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 2.287.051 | 1.928 | 74 |
| usdjpy | 2020-09-01 00:00:00 | 2026-10-30 20:59:00 | 2.294.935 | 1.928 | 74 |

## WIN e WDO do professor

`WIN.csv` e `WDO.csv`, em `data/raw/target/`, têm os mesmos hashes dos arquivos recebidos, listados abaixo com o nome original. Os horários abaixo são os gravados no CSV, ainda sem confirmação independente do fuso.

| Arquivo | Primeiro registro | Último registro | Candles | Datas observadas |
|---|---|---|---:|---:|
| WIN$N_M1.csv | 2020.10.15 11:49:00 | 2026.09.25 18:24:00 | 757.716 | 1.368 |
| WDO$N_M1.csv | 2020.09.17 14:08:00 | 2026.04.01 16:07:00 | 717.232 | 1.288 |

## Verificação e próximos passos

- CSVs externos verificados quanto a cabeçalho, timestamps M1 em UTC, ordem estrita, duplicatas, preços finitos, OHLC e limites de cada requisição.
- Retomada real reaproveitou blocos já recebidos após conferir parâmetros e SHA256. O coletor teve revisão independente e dois problemas de interrupção/retomada foram corrigidos, com testes de regressão.
- Sucesso da aquisição não demonstra ausência de buracos. Calendários, sessões, pausas, candles omitidos pelo volume zero e rolagens ainda serão auditados.
- Os dados permanecem brutos; o próximo passo é implementar os leitores e converter para Parquet UTC, preservando os CSVs.
- Download novo do MT5 depende dos arquivos fornecidos pelo colega no Windows. Não houve combinação automática de fontes B3.
- US T-Bond, TOPIX, CSI 300 e Shanghai Composite ficaram fora da coleta.

As instruções de execução estão no README.
