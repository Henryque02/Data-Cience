# Qualidade inicial dos datasets

Gerado pelo notebook notebooks/01_dados_e_qualidade.ipynb com os dados reais.

Foram padronizados 27,703,105 candles em 15 Parquets UTC. Duplicatas idênticas removidas: 0.

## Cobertura observada

| asset | source | rows | first_utc | last_utc | utc_dates_with_data | parquet_mb |
| --- | --- | --- | --- | --- | --- | --- |
| win | professor | 757716 | 2020-10-15 14:49:00+00:00 | 2026-09-25 21:24:00+00:00 | 1368 | 12.49 |
| wdo | professor | 717232 | 2020-09-17 17:08:00+00:00 | 2026-04-01 19:07:00+00:00 | 1288 | 10.41 |
| spx | dukascopy | 2081188 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:14:00+00:00 | 1919 | 45.5 |
| ndx | dukascopy | 2111355 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:14:00+00:00 | 1919 | 52.02 |
| sx5e | dukascopy | 1166863 | 2020-09-01 06:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1577 | 20.22 |
| ftse | dukascopy | 2063447 | 2020-09-01 00:00:00+00:00 | 2026-10-30 21:00:00+00:00 | 1900 | 48.02 |
| nikkei | dukascopy | 2013398 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:14:00+00:00 | 1916 | 33.9 |
| a50 | dukascopy | 1713745 | 2020-09-01 01:00:00+00:00 | 2026-10-30 20:29:00+00:00 | 1581 | 29.09 |
| brent | dukascopy | 1976028 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1593 | 32.37 |
| gold | dukascopy | 2186890 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1917 | 43.99 |
| dxy | dukascopy | 1929215 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1595 | 29.19 |
| usdmxn | dukascopy | 2270278 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1926 | 61.62 |
| copper | dukascopy | 2133764 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1917 | 34.23 |
| eurusd | dukascopy | 2287051 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1928 | 38.08 |
| usdjpy | dukascopy | 2294935 | 2020-09-01 00:00:00+00:00 | 2026-10-30 20:59:00+00:00 | 1928 | 38.25 |

## WIN e WDO

| ativo | dias_observados | pregoes_ausentes_internos | antes_do_historico | apos_o_historico | janela_inicial_incompleta | abertura_tardia | abertura_acima_do_limite | pregoes_elegiveis | fora_do_calendario | abertura_regular_mais_frequente |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| win | 1368 | 114 | 30 | 24 | 8 | 214 | 4 | 1351 | 0 | 09:00 |
| wdo | 1288 | 91 | 11 | 146 | 8 | 118 | 3 | 1272 | 0 | 09:00 |

Referência: exchange-calendars 4.13.2, BVMF apenas para datas e aberturas especiais. Futuros regulares usam 09:00 BRT como referência; a abertura é o primeiro candle observado, e os fechamentos são observados, sem horário fixo.

## Aberturas depois da referência

Pregões regulares cujo primeiro candle veio depois da referência. São elegíveis se o atraso for de até 15 minutos e a janela de 60 minutos, contada do primeiro candle, estiver completa.

| trimestre | win_pregoes | win_com_atraso | win_pct | wdo_pregoes | wdo_com_atraso | wdo_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 2020Q3 | <NA> | <NA> | <NA> | 10 | 7 | 70.0 |
| 2020Q4 | 52 | 12 | 23.1 | 61 | 18 | 29.5 |
| 2021Q1 | 59 | 15 | 25.4 | 59 | 23 | 39.0 |
| 2021Q2 | 62 | 1 | 1.6 | 62 | 15 | 24.2 |
| 2021Q3 | 64 | 4 | 6.2 | 64 | 12 | 18.8 |
| 2021Q4 | 49 | 8 | 16.3 | 55 | 9 | 16.4 |
| 2022Q1 | 61 | 2 | 3.3 | 61 | 2 | 3.3 |
| 2022Q2 | 62 | 5 | 8.1 | 62 | 2 | 3.2 |
| 2022Q3 | 56 | 3 | 5.4 | 55 | 1 | 1.8 |
| 2022Q4 | 61 | 7 | 11.5 | 61 | 3 | 4.9 |
| 2023Q1 | 62 | 3 | 4.8 | 62 | 1 | 1.6 |
| 2023Q2 | 42 | 0 | 0.0 | 42 | 1 | 2.4 |
| 2023Q3 | <NA> | <NA> | <NA> | 8 | 1 | 12.5 |
| 2023Q4 | 50 | 5 | 10.0 | 60 | 1 | 1.7 |
| 2024Q1 | 60 | 2 | 3.3 | 60 | 2 | 3.3 |
| 2024Q2 | 63 | 2 | 3.2 | 63 | 6 | 9.5 |
| 2024Q3 | 66 | 2 | 3.0 | 66 | 2 | 3.0 |
| 2024Q4 | 61 | 0 | 0.0 | 61 | 2 | 3.3 |
| 2025Q1 | 60 | 0 | 0.0 | 60 | 1 | 1.7 |
| 2025Q2 | 61 | 5 | 8.2 | 61 | 3 | 4.9 |
| 2025Q3 | 66 | 8 | 12.1 | 66 | 3 | 4.5 |
| 2025Q4 | 62 | 35 | 56.5 | 62 | 3 | 4.8 |
| 2026Q1 | 60 | 16 | 26.7 | 60 | 1 | 1.7 |
| 2026Q2 | 61 | 37 | 60.7 | 1 | 0 | 0.0 |
| 2026Q3 | 62 | 46 | 74.2 | <NA> | <NA> | <NA> |

### Ausências internas — WIN

| first_date | last_date | missing_sessions | reason |
| --- | --- | --- | --- |
| 2023-06-05 00:00:00 | 2023-10-16 00:00:00 | 93 | missing_session_internal |
| 2021-11-16 00:00:00 | 2021-12-01 00:00:00 | 12 | missing_session_internal |
| 2022-07-15 00:00:00 | 2022-07-27 00:00:00 | 9 | missing_session_internal |

### Ausências internas — WDO

| first_date | last_date | missing_sessions | reason |
| --- | --- | --- | --- |
| 2023-06-05 00:00:00 | 2023-09-19 00:00:00 | 75 | missing_session_internal |
| 2022-07-15 00:00:00 | 2022-07-28 00:00:00 | 10 | missing_session_internal |
| 2021-11-24 00:00:00 | 2021-12-01 00:00:00 | 6 | missing_session_internal |

## Limites desta auditoria

O fuso dos CSVs MT5 é uma hipótese configurável, ainda sem confirmação da corretora. Datas e horários observados ajudam a avaliar sua coerência, mas não são confirmação externa.

Intervalos externos não são falhas confirmadas: ainda precisamos do calendário e das convenções da fonte CFD. Nenhum preço foi interpolado, nenhum ajuste de rolagem foi aplicado e nenhum dia foi apagado do interim. O padrão de abertura tardia do WIN indica abertura real mais tarde, mas ainda falta confirmação da corretora. A elegibilidade trata só da qualidade dos dados: rolagem e variáveis ainda podem tirar dias da amostra.

Os CSVs brutos são preservados. Proveniência e SHA256 ficam em data/metadata/interim; diagnósticos em data/quality.
