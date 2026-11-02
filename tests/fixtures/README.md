# Amostra Dukascopy

`dukascopy_m1.csv` contém o cabeçalho e os três primeiros candles reais de
`usa500idxusd`, bid, M1, UTC, coletados com dukascopy-node 1.51.1 em
2026-11-02 para o intervalo [2026-10-29, 2026-10-31). Os testes modificam
cópias dessa amostra para verificar rejeição de dados inválidos.

`mt5_win.tsv` e `mt5_wdo.tsv` são os três primeiros candles reais dos CSVs
do professor, com o cabeçalho original TAB. `mt5_api.csv` representa o primeiro
candle de WIN no formato da API, com epoch segundos UTC e preços/volumes
preservados, para testar a distinção de formato; não é um download novo do MT5.
