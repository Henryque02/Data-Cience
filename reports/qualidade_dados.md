# Qualidade inicial dos datasets

Gerado pelo notebook `01_dados_e_qualidade.ipynb`, apagado em 08/11/2026, com os dados anteriores ao novo download (01/09/2020 a 30/10/2026).

Foram padronizados 27,703,105 candles em 15 Parquets UTC. Duplicatas idênticas removidas: 0.

## Cobertura observada

| ativo | inicio | fim | candles |
| --- | --- | --- | --- |
| win | 15/10/2020 | 25/09/2026 | 757716 |
| wdo | 17/09/2020 | 01/04/2026 | 717232 |
| spx | 01/09/2020 | 30/10/2026 | 2081188 |
| ndx | 01/09/2020 | 30/10/2026 | 2111355 |
| sx5e | 01/09/2020 | 30/10/2026 | 1166863 |
| ftse | 01/09/2020 | 30/10/2026 | 2063447 |
| nikkei | 01/09/2020 | 30/10/2026 | 2013398 |
| a50 | 01/09/2020 | 30/10/2026 | 1713745 |
| brent | 01/09/2020 | 30/10/2026 | 1976028 |
| gold | 01/09/2020 | 30/10/2026 | 2186890 |
| dxy | 01/09/2020 | 30/10/2026 | 1929215 |
| usdmxn | 01/09/2020 | 30/10/2026 | 2270278 |
| copper | 01/09/2020 | 30/10/2026 | 2133764 |
| eurusd | 01/09/2020 | 30/10/2026 | 2287051 |
| usdjpy | 01/09/2020 | 30/10/2026 | 2294935 |

## WIN e WDO: do calendário aos pregões elegíveis

| etapa | WIN | WIN saíram | WDO | WDO saíram |
| --- | --- | --- | --- | --- |
| Pregões no calendário, entre o 1º e o último dado | 1482 | – | 1379 | – |
| Com dados | 1368 | 114 | 1288 | 91 |
| Sem Quarta-feira de Cinzas | 1362 | 6 | 1282 | 6 |
| Abertura até 15 min depois da referência | 1358 | 4 | 1279 | 3 |
| Primeiros 60 min completos (elegíveis) | 1351 | 7 | 1272 | 7 |

Referência: exchange-calendars 4.13.2, BVMF apenas para datas e aberturas especiais. Futuros regulares usam 09:00 BRT como referência; a abertura é o primeiro candle observado, e os fechamentos são observados, sem horário fixo.

## Aberturas depois da referência

Pregões regulares cujo primeiro candle veio depois da referência. São elegíveis se o atraso for de até 15 minutos e a janela de 60 minutos, contada do primeiro candle, estiver completa.

| trimestre | WIN | WDO |
| --- | --- | --- |
| 2020Q3 |  | 70% |
| 2020Q4 | 23% | 30% |
| 2021Q1 | 25% | 39% |
| 2021Q2 | 2% | 24% |
| 2021Q3 | 6% | 19% |
| 2021Q4 | 16% | 16% |
| 2022Q1 | 3% | 3% |
| 2022Q2 | 8% | 3% |
| 2022Q3 | 5% | 2% |
| 2022Q4 | 12% | 5% |
| 2023Q1 | 5% | 2% |
| 2023Q2 | 0% | 2% |
| 2023Q3 |  | 12% |
| 2023Q4 | 10% | 2% |
| 2024Q1 | 3% | 3% |
| 2024Q2 | 3% | 10% |
| 2024Q3 | 3% | 3% |
| 2024Q4 | 0% | 3% |
| 2025Q1 | 0% | 2% |
| 2025Q2 | 8% | 5% |
| 2025Q3 | 12% | 4% |
| 2025Q4 | 56% | 5% |
| 2026Q1 | 27% | 2% |
| 2026Q2 | 61% | 0% |
| 2026Q3 | 74% |  |

### Ausências internas — WIN

| inicio | fim | pregoes |
| --- | --- | --- |
| 05/06/2023 | 16/10/2023 | 93 |
| 16/11/2021 | 01/12/2021 | 12 |
| 15/07/2022 | 27/07/2022 | 9 |

### Ausências internas — WDO

| inicio | fim | pregoes |
| --- | --- | --- |
| 05/06/2023 | 19/09/2023 | 75 |
| 15/07/2022 | 28/07/2022 | 10 |
| 24/11/2021 | 01/12/2021 | 6 |

## Limites desta auditoria

O fuso dos CSVs MT5 é uma hipótese configurável, ainda sem confirmação da corretora. Datas e horários observados ajudam a avaliar sua coerência, mas não são confirmação externa.

Intervalos externos não são falhas confirmadas: ainda precisamos do calendário e das convenções da fonte CFD. Nenhum preço foi interpolado, nenhum ajuste de rolagem foi aplicado e nenhum dia foi apagado do interim. O padrão de abertura tardia do WIN indica abertura real mais tarde, mas ainda falta confirmação da corretora. A elegibilidade trata só da qualidade dos dados: rolagem e variáveis ainda podem tirar dias da amostra.

Os CSVs brutos são preservados.
