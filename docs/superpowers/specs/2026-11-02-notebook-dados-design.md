# Notebook de padronização e diagnóstico

O usuário autorizou padronizar os dados em Parquet UTC e auditar horários,
buracos e cobertura, depois definiu o notebook como roteiro para ver os
datasets e acompanhar os ajustes. Executar esta etapa agora; não voltar a
pedir aprovação do mesmo escopo.

Entregar `notebooks/01_dados_e_qualidade.ipynb`, em português, com saídas reais,
tabelas e gráficos: inventário; exemplos brutos; conversão de horário;
padronização dos 15 ativos; cobertura mensal; aberturas/fechamentos B3;
datas ausentes e intervalos sem candles; diagnóstico das fontes externas;
conclusões e parâmetros editáveis para a exploração.

Comparação de abordagens: concentrar lógica no notebook ou chamar funções
reutilizáveis de src. A escolha preserva ambas as necessidades: notebook
como interface e narrativa, leitores/conversão/auditoria em src conforme
AGENTS.md. Não incluir regras operacionais ou modelos nesta etapa.

CSV Dukascopy usa epoch milissegundos UTC; CSV MT5 do professor usa data e
hora sem fuso, com parâmetro America/Sao_Paulo por hipótese documentada.
Leitor de exportação da API MT5 usa epoch segundos UTC, sem segundo ajuste
de fuso. Volume do professor usa <VOL>; outros tipos ficam explícitos.

Parquet: datetime64[ns, UTC], open/high/low/close/volume numéricos, ordenado,
sem duplicatas. Remover apenas duplicatas idênticas; conflitos de preço ou
volume provocam erro. Nunca interpolar nem editar raw. Manter dias suspeitos
no interim; sinalizar qualidade em metadados, para futura exclusão da amostra.

Usar calendário BVMF de exchange-calendars para datas e aberturas especiais,
sem aplicar seu horário de ações aos futuros WIN/WDO. Abertura regular dos
alvos: 09:00 local. Fechamentos detectados dos candles, sem fixar horário.
Não chamar intervalo vazio externo de falha comprovada sem calendário da fonte.
Não ajustar rolagens ou criar labels. Hipóteses ficam no README e notebook.

Conversão reexecutável, com SHA256 dos arquivos de entrada e saída e gravação
atômica. Manter apenas um ativo completo na memória por vez. Dependências
de notebook em grupo uv separado. Executar o notebook integralmente e pytest.
