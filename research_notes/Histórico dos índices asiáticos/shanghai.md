# Histórico M1 gratuito do Shanghai Composite

## Existe fonte gratuita cobrindo setembro de 2020 até o presente?

### Takeaway
Não foi verificada uma fonte gratuita, reproduzível e atualizável com OHLC M1 do Shanghai Composite para toda a janela 2020-09-01–2026-11-02. Há APIs gratuitas recentes que funcionaram em amostras reais, um arquivo acadêmico aberto de fechamento M1 publicado em 2022 e fornecedores de arquivos longos pagos. Isto não demonstra inexistência absoluta de arquivo gratuito; significa que as alternativas localizadas não comprovaram atender ao requisito completo.

### Cited Findings
- A documentação oficial do AKShare informa que `index_zh_a_hist_min_em` fornece apenas dados recentes e não todo o histórico. Para período `1`, a disponibilidade é descrita como atual; para outros períodos, recente. O parâmetro de data não constitui garantia de profundidade. — [Documentação AKShare](https://github.com/akfamily/akshare/blob/main/docs/data/index/index.md)
- O código do AKShare torna a limitação concreta: o ramo M1 usa `push2his.eastmoney.com/api/qt/stock/trends2/get`, com `ndays="5"`, e só filtra `start_date`/`end_date` depois de receber os dados. — [Código original, função index_zh_a_hist_min_em](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/index/index_zh_em.py)
- Teste HTTP real em 2026-11-02, sem autenticação: Eastmoney `secid=1.000001` respondeu `code=000001`, `market=1`, `name=上证指数` e 1.205 linhas, da primeira `2026-10-27 09:30` à última `2026-11-02 15:00`. Isto confirma o índice Shanghai, em vez da ação Ping An Bank `sz000001`, e cinco pregões recentes; não demonstra arquivo desde 2020. Parte dos campos `open` antigos veio como zero e demanda auditoria antes de uso OHLC. — [Endpoint testado](https://push2his.eastmoney.com/api/qt/stock/trends2/get?fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=5&secid=1.000001)
- Tencent: pedido real `param=sh000001,m1,,10` retornou dez candles entre `202611021451` e `202611021500`, identificando o instrumento como 上证指数. Repetir com `param=sh000001,m1,2020-09-02,10` retornou `code=0`, mas zero candles; não foi demonstrada paginação M1 antiga. — [Endpoint recente testado](https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh000001,m1,,10); [pedido antigo testado](https://ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh000001,m1,2020-09-02,10)
- Sina: pedido real `symbol=sh000001&scale=1&ma=no&datalen=10` retornou dez registros no pregão 2026-11-02, com `day, open, high, low, close, volume, amount`. Pedido `datalen=2000` retornou JSON `null`. Não existe data inicial no formato deste endpoint que tenha demonstrado cobrir 2020. — [Endpoint Sina testado](https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol=sh000001&scale=1&ma=no&datalen=10)
- A biblioteca pública Ashare usa datas para o endpoint diário, mas o ramo Tencent de minutos constrói a URL só com símbolo, frequência e quantidade: a variável `end_date` não é enviada ao endpoint. Portanto, não se deve inferir paginação histórica apenas porque a função recebe esse argumento. — [Código Ashare](https://raw.githubusercontent.com/mpquant/Ashare/main/Ashare.py)
- A documentação oficial SSE Info lista dados históricos de minuto em serviço de assinatura e distribuição; não apresentou download aberto integral. — [Descrição oficial do produto SSE Info](https://www.sseinfo.com/services/assortment/znsj/znfwnr/c/10767767/files/1e1427dfec484ab288fd67201b73e561.pdf)
- Yucezhe anuncia Shanghai Composite `sh000001` e outros índices em 1/5/15/30 minutos desde 2007. Entretanto, a página mostra compra por ano, com preço de ¥30/ano e amostra gratuita; o produto não é arquivo integral gratuito. O código `sh000000` usado no anúncio para CSI300 também merece esclarecimento antes de eventual aquisição. Nenhuma compra foi feita. — [Página do fornecedor](https://www.yucezhe.com/product?name=main-index-min-data)
- Maliquant anuncia arquivos M1 de Shanghai, CSI300 e outros índices por ¥29,90, com data de atualização exibida de 2024-02-09 e gratuidade condicionada a alunos de curso; não é acesso aberto geral e não demonstra atualização até 2026. — [Página do fornecedor](https://www.maliquant.com/data-index-mid)
- Um repositório que anuncia dados históricos via funções `get_index_history` depende do serviço `data.diemeng.chat`, conta, API key e autorização da categoria "histórico de índices"; o README não estabelece gratuidade integral nem período disponível. Não foi tratado como fonte gratuita validada. — [README original](https://github.com/1018466411/openclaw-stock-data-skill)

### Inferences
- Reexecutar AKShare com blocos de 2020 não contorna a janela de cinco dias da fonte: o código simplesmente não pede esse passado no ramo M1.
- Tencent e Sina são candidatos para coleta prospectiva recente, mas não resolvem retroativamente os seis anos pedidos.
- Os retornos M1 frequentemente contêm 15:00 como timestamp final; a convenção abertura/fechamento do candle deve ser verificada. Não aplicar diretamente a regra do projeto de candles rotulados pela abertura sem documentação.

### Gaps
- Não foi possível provar inexistência de acervo gratuito em toda a internet. Foram procurados termos ingleses e chineses, incluindo Shanghai Composite/SSEC/sh000001/上证指数, M1/minute/分钟, GitHub, Kaggle, Hugging Face, Zenodo e publicações acadêmicas.
- Ausência de fonte pública validada não exclui acesso institucional UFG a Wind, CSMAR ou outros fornecedores. Nenhuma conta universitária foi consultada.
- Não foram comprados dados, criadas contas, contornadas restrições, instalados pacotes no repositório nem baixados anos completos.

## Há arquivos acadêmicos abertos úteis, mesmo parciais?

### Takeaway
Foi encontrado arquivo acadêmico real de fechamento a cada minuto do SH000001 sob licença declarada CC BY 4.0. Ele não comprova OHLC nem cobertura completa até o presente e não deve ser anunciado como solução do requisito original.

### Cited Findings
- Mendeley Data, **Financial empirical data**, DOI `10.17632/v27t7jvxkn.1`, de Shijia Song / Beijing Normal University, publicado em 11/11/2022, descreve preços de fechamento M1 para SH000001, SZ399001, SPX e NASDAQ, originados de Wind. A página declara CC BY 4.0. — [Página primária](https://data.mendeley.com/datasets/v27t7jvxkn/1)
- A API pública foi consultada efetivamente e retornou só uma versão, `1`, publicada em `2022-11-11T13:39:36.112Z`. Existe um arquivo `data.rar`, 32.377.884 bytes, SHA256 `b2c8503bc06a4e17880303c884b918f8fbcbb492004269961250967c3ffb85af`, sem início/fim das observações nos metadados. Não foi baixado integralmente por ser arquivo grande sem possibilidade de confirmar intervalo por metadados. A licença ressalva eventuais conteúdos identificados como pertencentes a terceiros. — [API pública verificada](https://data.mendeley.com/public-api/datasets/v27t7jvxkn)
- O repositório acadêmico **aqua**, relativo a Dynamic Quantile Function Models, liga arquivos de preços M1 para dez índices, incluindo Shanghai Composite, Nikkei, FTSE e outros. A própria documentação delimita 1996-01-03 a 2016-05-24: período sem interseção com a amostra pretendida. — [Repositório dos autores](https://github.com/wilson-ye-chen/aqua)
- Um trabalho sobre Shanghai Composite descreve dados de alta frequência de 2023-09-25 a 2024-09-24, mas em **5 minutos**, originados de Wind, e não apresenta no material consultado um acervo M1 aberto completo. — [Artigo original](https://www.aimspress.com/aimspress-data/math/2025/7/PDF/math-10-07-729.pdf)
- O repositório a-share-data possui acervo aberto extenso, mas explicita **oito índices diários**, não M1. — [Descrição do próprio repositório](https://github.com/noblechang/a-share-data)

### Inferences
- O arquivo Mendeley publicado em 2022 não pode conter observações reais de 2023–2026 na versão publicada; serve no máximo a um estudo parcial anterior e não oferece canal documentado de atualização.
- Mesmo que seus preços M1 fossem aproveitados, não se deve inventar `open/high/low/volume` para satisfazer o schema OHLCV padronizado.
- A existência de um dataset em pesquisa acadêmica não significa que os dados possam ser obtidos gratuitamente: vários estudos usam fornecedores pagos.

### Gaps
- Datas internas exatas, formato dos arquivos contidos no RAR e se há timestamps por registro no Mendeley permanecem sem verificação. O relatório não deve inventar um intervalo para esse arquivo.
- Não foi localizada outra versão pública do mesmo dataset com atualizações após 2022.

## É possível usar uma frequência diferente sem abandonar o índice?

### Takeaway
Como alternativa de desenho, retornos diários do pregão chinês podem ser úteis antes da abertura brasileira, mas são outra especificação de dado. Essa alternativa não satisfaz M1 nem permite calcular as mesmas variáveis intradiárias.

### Cited Findings
- A metodologia oficial identifica o SSE Composite como índice de ações e CDRs elegíveis da bolsa de Shanghai. Isto distingue o índice correto das ações com código semelhante e de CSI300. — [Metodologia SSE](https://english.sse.com.cn/indices/indices/list/indexmethods/c/000001_000001en_EN.pdf)
- AKShare documenta `index_zh_a_hist` para OHLC e volume diário/semanal/mensal dos índices, com intervalo inicial e final, separadamente da interface recente de minutos. — [Documentação original](https://github.com/akfamily/akshare/blob/main/docs/data/index/index.md)
- Pesquisa empírica disponibilizada pelos próprios autores descreve uso de dados diários do Shanghai Composite de 1990-12-20 a 2023-06-02 obtidos de Sina; isto é evidência de profundidade diária em outro período, não teste de atualização até 2026. — [Artigo PLOS One](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0299164)

### Inferences
- O pregão regular chinês termina antes das 09:00 em São Paulo; uma variável de retorno do pregão completo poderia ser usada quando o dado estivesse publicado antes do corte brasileiro. Seria necessário validar calendário, fechamento e horário efetivo de disponibilidade em cada fonte.
- Não basta conhecer a data do candle diário: tabelas publicadas só após a abertura brasileira não seriam elegíveis naquele dia.
- Se o grupo mantiver a exigência de M1, a recomendação é deixar Shanghai Composite pendente por enquanto e seguir com China A50, explicitamente identificado como outro instrumento. Se aceitar variáveis diárias, abrir uma especificação separada de frequência e metadados, sem transformar diário em M1 artificial.

### Gaps
- O momento de publicação histórica das barras diárias do provedor escolhido ainda teria de ser documentado; não foi validada retrospectivamente uma política de disponibilidade ponto a ponto.
