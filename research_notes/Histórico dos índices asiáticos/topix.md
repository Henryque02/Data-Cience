# Fontes gratuitas de TOPIX

Pesquisa em 2 de novembro de 2026. Critério: índice TOPIX, candles de um minuto, desde 2020-09-01 até a última sessão completa disponível, gratuitamente e com aquisição viável para projeto acadêmico em Linux. Futuros e ETFs são alternativas distintas, não substituições silenciosas do índice à vista.

## Existe TOPIX à vista M1 gratuito para toda a janela?

### Takeaway

Não foi confirmada uma fonte que satisfaça simultaneamente instrumento, granularidade, janela e gratuidade. Isso é resultado da busca, não prova de inexistência. As fontes oficiais consultadas distinguem claramente dados diários de índices e intradiários de ações.

### Cited Findings

- **J-Quants API:** a matriz oficial não inclui TOPIX no plano Free; os planos Light, Standard e Premium oferecem respectivamente cinco, dez e vinte anos de histórico diário. O add-on de minutos cobre ações, não índices. Portanto, nem assinar apenas o add-on resolve TOPIX M1. [Matriz oficial](https://jpx-jquants.com/en/spec/data-spec), [especificação M1, japonês](https://jpx-jquants.com/ja/spec/eq-bars-minute).
- **JPX FLEX Historical:** serviço contratado e pago; a descrição inclui TOPIX em mensagens/ticks, que exigiriam tratamento antes de gerar candles. O produto antigo Real time TOPIX aparece disponível somente até 2024-11-01; a continuidade posterior desse produto não está demonstrada nessa página. Há formulário específico de condições acadêmicas, sem promessa de gratuidade. [Serviço oficial](https://www.jpx.co.jp/english/markets/paid-info-equities/historical/01.html).
- **Yahoo Finance/yfinance:** a documentação da biblioteca limita intraday aos últimos sessenta dias, podendo haver limites mais estritos por intervalo; isso não é um arquivo M1 desde 2020. Não foi possível recuperar a pequena requisição de teste ao endpoint chart de `^TOPX` nesta ferramenta. Não se afirma que o símbolo ou a API estejam globalmente indisponíveis. [Documentação da biblioteca](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html).
- **Stooq:** páginas de catálogo e cotação TOPIX responderam com verificação JavaScript; a tentativa de CSV de três dias não produziu dados nesta sessão. Não foi comprovado TOPIX M1 na fonte. A existência de diário ou de intraday para outros mercados não comprova o arquivo pretendido. [Catálogo](https://stooq.com/db/h/), [cotação procurada](https://stooq.com/q/?s=%5Etpx), [teste diário](https://stooq.com/q/d/l/?s=%5Etpx&i=d&d1=20200901&d2=20200903).
- **Kabutan:** ajuda do fornecedor informa que candles de um minuto ficam limitados ao próprio dia, inclusive no quadro de usuários gratuitos. Não atende à profundidade histórica. [Ajuda de períodos](https://support.kabutan.jp/hc/ja/articles/10752841194905-%E6%A0%AA%E4%BE%A1%E3%83%81%E3%83%A3%E3%83%BC%E3%83%88%E3%81%A7%E8%A1%A8%E7%A4%BA%E3%81%A7%E3%81%8D%E3%82%8B%E6%9C%9F%E9%96%93).
- **Portara/CQG:** anuncia série chamada TOPIX Index/JTPX com intraday desde 1999, mas entrega por contratos e distingue amostra de compra/subscrição. Não é uma fonte gratuita integral comprovada; não confundir o rótulo comercial “Index” com índice spot. [Página do fornecedor](https://portaracqg.com/futures/int/jtpx/).
- **Interactive Brokers:** histórico via API depende de permissões/assinaturas e conta; a documentação alerta que dados de futuros expirados há mais de dois anos não estão disponíveis. Trial não fornece histórico de candles para a maioria dos instrumentos. Não foi identificada promessa de TOPIX spot M1 gratuito desde 2020. [Limitações](https://www.interactivebrokers.com/docs/tws-api/doc/md/market-data-limitations), [FAQ de integrações](https://www.interactivebrokers.com/docs/third-party-integrations/general-third-party-frequently-asked-questions).
- **Kaggle/JPX competition:** o conjunto famoso de previsão da bolsa japonesa contém preços diários de ações, não arquivo TOPIX M1. [Descrição original](https://www.kaggle.com/competitions/jpx-tokyo-stock-exchange-prediction/data).
- **Repositório kabu-json-topix:** o autor publica o último dia de negociação em JSON, não anuncia arquivo M1 desde 2020. [README primário](https://raw.githubusercontent.com/umihico/kabu-json-topix/main/README.md).
- **Mendeley:** foi encontrada publicação acadêmica de TOPIX Core 30 diário/mensal. É outro índice e outra frequência. [Página do conjunto](https://data.mendeley.com/datasets/59n7fm4wf6/1).

### Inferences

- Adoção imediata de TOPIX spot M1 exigiria uma fonte ainda não validada ou acesso institucional já contratado. Não há base para prometer que será gratuito.
- Acesso da universidade a terminal/provedor poderia mudar o quadro; não foi consultado nem contatado qualquer terceiro.
- Buscas em inglês e japonês, incluindo GitHub, Kaggle, Zenodo/Mendeley, JPX, corretoras e vendedores de dados, não localizaram um arquivo aberto comprovadamente compatível com toda a janela. Vários resultados eram Nikkei, ações individuais, diário, amostras ou futuros.

### Gaps

- Não foi validado download de amostra real TOPIX spot M1.
- Não houve cadastro, autenticação ou compra em qualquer fonte.
- Não foi auditada disponibilidade via assinatura institucional do usuário.

## Existe alternativa gratuita de futuros TOPIX com histórico suficiente?

### Takeaway

**Sim, há uma candidata concreta anunciada: 225Labo.** Oferece TOPIX futuro padrão e mini-TOPIX futuro M1, com cadastro gratuito. Não é o índice à vista, os arquivos ainda não foram baixados e os termos precisam ser esclarecidos para uso acadêmico em grupo.

### Cited Findings

- A categoria TOPIX futuro anuncia minutos desde 2001, com intervalos de 1 a 60 minutos e entradas anuais de 2020 a 2026. A categoria mini anuncia desde 2008. As páginas restringem download a membros e descrevem uso pessoal do próprio usuário, sem fornecimento a terceiros. [TOPIX futuro](https://225labo.com/modules/downloads_data/index.php?cid=4), [mini-TOPIX futuro](https://225labo.com/modules/downloads_data/index.php?cid=8).
- O formulário de adesão é explicitamente gratuito, pede e-mail, usuário, senha e confirmação por e-mail. Nenhum cadastro foi efetuado. [Registro](https://225labo.com/register.php).
- A página de 2026 de TOPIX futuro foi aberta e confirma M1–M60. Sem login ela mostra a exigência de autenticação, não o arquivo. Explica que a data da sessão noturna segue o dia útil seguinte segundo a Osaka Exchange e distingue quatro agregações de sessão/diário. [Item 2026](https://225labo.com/modules/downloads_data/index.php?cid=4&lid=161&page=singlefile).
- Os termos de download descrevem dados coletados/criados privadamente, sem garantia, e finalidade de aprendizado pessoal para melhorar a própria capacidade de negociação, excluindo outras finalidades. Não há autorização expressa de pesquisa acadêmica compartilhada nesses termos. [Condições específicas](https://225labo.com/document/download/about.html).

### Inferences

- Esta é uma **candidata condicional**, e seria incorreto dizer apenas que “TOPIX não tem dados gratuitos”. Há oferta de futuro gratuita com cadastro; o que falta é comprovar arquivos e adequação ao projeto.
- Antes de usar em grupo, seria necessário esclarecer com o fornecedor o alcance permitido. Isso não equivale a afirmar que pesquisa acadêmica é necessariamente proibida em qualquer circunstância, nem a exigir contato nesta tarefa: nenhum contato foi autorizado ou enviado.
- A data noturna não pode ser interpretada ingenuamente como data civil. Isso afeta UTC e o alinhamento com a abertura da B3.
- Se aceita, a série deve ter id próprio, por exemplo `topix_futures`, sem fingir ser TOPIX spot.

### Gaps

- Não foi possível baixar os arquivos sem cadastro; não foram auditados cabeçalho, cobertura, buracos, fuso, rotulação por abertura/fechamento do candle ou consistência de preços.
- As páginas dos itens 2020 TOPIX e mini deram cache miss na ferramenta; os títulos e descrições anuais são visíveis nos respectivos catálogos.
- Não foi encontrada regra clara de seleção de contrato, rolagem ou ajuste da série TOPIX nos materiais públicos examinados. Não transferir para TOPIX as regras de continuidade eventualmente documentadas para Nikkei.
- A página 2026 não demonstra até qual dia efetivo o arquivo está atualizado. Data de indexação da página não é data máxima do dataset.

## Dados diários poderiam servir como alternativa limitada?

### Takeaway

Em princípio, um retorno da sessão japonesa concluída pode ser usado antes da abertura brasileira; entretanto, o horário de publicação da fonte também precisa anteceder o corte. Isso não recupera volatilidade realizada intradiária nem retornos de janelas M1.

### Cited Findings

- J-Quants divulga TOPIX diário por volta de 16:30, no contexto japonês. A mesma API não o inclui no plano gratuito e fornece apenas diário para índices. [Horários de atualização](https://jpx-jquants.com/en/spec/data-update), [planos](https://jpx-jquants.com/en/spec/data-spec).
- A página oficial TOPIX apresenta valores históricos de referência por ano, sem comprovar nesta consulta um CSV público diário completo desde 2020. [JPX TOPIX](https://www.jpx.co.jp/english/markets/indices/topix/).
- kabu-json-topix diz publicar o último dia, e não um arquivo histórico amplo. A tentativa de acessar seu pequeno JSON público não retornou conteúdo pela ferramenta. [README](https://raw.githubusercontent.com/umihico/kabu-json-topix/main/README.md), [URL anunciada](https://d1rrtoo3h22gy6.cloudfront.net/kabu-json-topix/v1/topix.json).

### Inferences

- 16:30 JST corresponde a 07:30 UTC/04:30 BRT, antecedendo 08:58 BRT. Um produto diário com esse horário de disponibilidade é temporalmente compatível, sujeito a atraso real, calendário e validação de publicação.
- O fato de uma sessão ter acabado não basta para afirmar que um arquivo publicado apenas no fim do dia já estava disponível durante a decisão. Essa verificação deve ser por fonte.
- Fonte diária gratuita pode ser investigada como etapa separada, sem gerar candles M1 artificiais e sem declarar que atende ao pedido original.
- Recomendação para o plano atual: TOPIX spot M1 fica fora da base obrigatória por enquanto; 225Labo futuro permanece candidato opcional pendente de acesso, qualidade e condições de uso. O Nikkei da Dukascopy permite seguir com cobertura japonesa sem bloquear a Fase 1.

### Gaps

- Não há comprovação nesta pesquisa de arquivo TOPIX diário gratuito completo, atualizado e com horário de disponibilidade verificável para toda a janela.
- Nenhum teste de código do projeto foi adicionado ou executado por este pesquisador, pois o trabalho foi exclusivamente documental.
