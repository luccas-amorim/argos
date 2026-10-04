# Observatório do Massacre do Carandiru: como chegar perto de "tudo"

Pergunta de partida: é possível um robô vasculhar, incrementalmente, **toda** a internet
sobre o massacre do Carandiru e catalogar cada achado com o universo léxico da pesquisa?

Resposta curta: **"toda" não se garante; "quase toda, com a lacuna medida", sim.** Nenhum
sistema, nem o Google, enumera tudo o que existe sobre um tema. O que dá para construir
é um robô que descobre por vários canais independentes, nunca esquece o que achou,
guarda o texto e a data de captura, e **estima quanto ainda falta**. A última parte é a
que transforma "toda a internet" de promessa em número.

---

## Duas tarefas diferentes

| | Varredura (o passivo) | Vigilância (o fluxo) |
|---|---|---|
| Pergunta | o que já foi publicado desde 1992? | o que saiu desde a última rodada? |
| Volume | grande, uma vez | pequeno, toda semana |
| Canais | Wayback, Common Crawl, acervos, repositórios | RSS, GDELT, buscas periódicas |
| No Argos | `rodar --desde 1992-10-02 --sem-estado`, fonte a fonte | `rodar` agendado |

O contrato do adaptador serve às duas: `listar(desde)` com uma data antiga é a
varredura; com a data da última rodada, é a vigilância. O estado garante que nada
seja relido nem esquecido: item que falhou fica **pendente** e volta em toda rodada.

## Por que não "raspar o Google"

- **Não há API.** A Custom Search JSON API fechou para novos clientes, e a opção de
  buscar a web inteira termina em 1º/01/2027
  ([Brave](https://brave.com/learn/google-api-shutdown/),
  [DEV](https://dev.to/booyaka101/google-kills-the-custom-search-json-api-on-2027-01-01-here-is-a-self-hosted-drop-in-3nk0)).
  A Bing Search API foi desligada em 11/08/2025
  ([Microsoft](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)).
- **O `robots.txt` do Google proíbe `/search`**, e o Argos não ignora `robots.txt`, por
  política escrita no README. Serviços pagos de SERP existem; usá-los seria contornar
  a mesma regra por intermediário.
- **"Centenas de milhares de resultados" é estimativa do buscador**, não contagem. A
  busca não pagina além de algumas centenas de resultados por consulta, e boa parte do
  número é duplicata, republicação e página de listagem. O Argos deduplica por hash do
  texto; o número que importa é o de **textos distintos**, e ele é bem menor.

O que o Google indexa, porém, quase sempre existe em outro lugar que se pode ler com
licença: no Common Crawl, no Wayback, no próprio site de origem.

## Os canais, por ordem de rendimento esperado

Cada canal vira um adaptador do Argos. Os que exigem rede ainda não foram sondados (o
ambiente em que a v0.1 foi escrita bloqueava esses hosts); a coluna "a sondar" diz o que
conferir antes de escrever o adaptador.

| Canal | O que entrega | Técnica | A sondar |
|---|---|---|---|
| **Wayback Machine (CDX)** | toda URL arquivada de um domínio cujo endereço contenha um termo, com data de cada captura, inclusive de páginas que saíram do ar | `cdx/search/cdx?url=<domínio>&matchType=domain&filter=original:.*carandiru.*&collapse=urlkey`, domínio a domínio, a partir de uma lista de veículos, universidades e órgãos | paginação (`showNumPages`) e limite de requisições |
| **Common Crawl** | o mais perto de "o índice do Google" que é aberto: bilhões de páginas por coleta, coletas periódicas desde 2008 | índice colunar por URL (`url LIKE '%carandiru%'`, recorte `.br`) e, para achar texto que não tem o termo na URL, leitura dos WET de um recorte de domínios | custo de processar WET; começar pelo índice de URL |
| **GDELT DOC 2.0** | notícias do mundo inteiro, busca por texto, em 65 línguas | `api/v2/doc/doc?query=carandiru&mode=artlist` | a janela é móvel, de cerca de três meses ([GDELT](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)): serve à vigilância, não ao passivo |
| **RSS** | o fluxo de cada veículo e do Google Notícias por consulta | adaptador `rss`, **já pronto na v0.1** | os links do Google Notícias são redirecionamentos codificados; conferir se resolvem sem JavaScript e se o `robots.txt` permite |
| **Produção acadêmica** | artigos, teses, dissertações | OpenAlex e Crossref (API aberta), SciELO, BDTD e repositórios institucionais (OAI-PMH), Zenodo | OAI-PMH é um adaptador só, que serve a dezenas de repositórios |
| **Wikipédia e Wikidata** | as referências que editores já reuniram, em várias línguas | API do MediaWiki (`extlinks` dos verbetes do massacre) | é semente, não acervo: alimenta a lista de domínios do Wayback |
| **Processos** | as ações penais e cíveis do caso, os recursos no STJ e no STF | DataJud por número CNJ (**adaptador pronto**); DJEN para o texto publicado | o e-SAJ do TJSP tem CAPTCHA: fica fora, por política |
| **Imprensa histórica (1992 em diante)** | o que nunca esteve na web aberta | Hemeroteca Digital Brasileira; acervos da Folha e do Estadão | sem API e, nos acervos, atrás de assinatura: entra por lista curada ou convênio, não por robô |

O Wayback é o canal que mais importa ao observatório, como o README já dizia: fonte que
sumiu ainda tem texto, e o texto tem data de captura. Ele tem uma limitação que muda o
desenho: **não há busca por texto no Wayback**, só por URL. Por isso ele trabalha em
dupla com os outros canais. Os outros descobrem domínios e URLs; o Wayback devolve todas
as capturas desses domínios cujo endereço tenha o termo, e recupera o texto das que
morreram.

## Medir o que falta: captura e recaptura

Com dois canais razoavelmente independentes, a sobreposição entre eles estima o total.
Se o Common Crawl acha `n1` textos distintos, o GDELT acha `n2`, e `m` estão nos dois, o
total estimado é `N ≈ n1 · n2 / m` (estimador de Lincoln-Petersen, o mesmo que se usa
para contar populações de animais). Com três ou mais canais há estimadores melhores, e a
saída do Argos já traz o que eles precisam: fonte, URL e hash do texto de cada item.

A ressalva é honesta e precisa constar em qualquer relatório: os canais **não** são
independentes. Todos favorecem o que é popular e bem ligado, então a estimativa é
**piso**, não teto. Mesmo assim, é a diferença entre dizer "achamos 40 mil" e dizer
"achamos 40 mil de no mínimo 55 mil estimados, e a curva parou de subir em março".

## O léxico da pesquisa

O universo léxico da sua colega entra como dado, no formato de
`exemplos/lexico.schema.json`, mantido no repositório do observatório. Três recursos do
formato foram pensados para este caso:

- **`formas`**: as grafias que contam como cada termo ("massacre do Carandiru",
  "chacina do Carandiru", "Pavilhão 9", "111 presos"), sem distinguir maiúsculas nem
  acentos.
- **`exclusoes`**: o que parece mas não é. "Carandiru, o filme", "estação Carandiru",
  o bairro. A ocorrência que cai dentro de uma exclusão não conta, e o item que só tem
  essas ocorrências sai descartado com o motivo `so_exclusao`, para conferência.
- **`categorias`**: as facetas de catalogação de cada termo (evento, lugar, pessoa,
  desdobramento jurídico, memória, período). Vão para a saída junto com a chave, e são
  elas que fazem do corpus um catálogo, e não só uma pilha.

Quando o léxico mudar, `python -m argos retriar` reaplica o léxico novo a todo o corpus
guardado, sem rede. Nada precisa ser baixado de novo.

## Ordem de trabalho proposta

1. **Léxico real** no formato do schema, validado por `argos validar-lexico`. É o passo
   que depende da pesquisa e destrava todo o resto.
2. **`wayback`**: adaptador CDX por domínio, com a lista inicial de domínios vinda da
   Wikipédia e de uma curadoria de veículos e universidades.
3. **`openalex`** e **`oai-pmh`**: a produção acadêmica, que tem as APIs mais estáveis.
4. **`commoncrawl`** pelo índice de URL; depois, se a estimativa de lacuna pedir, pelo
   texto.
5. **`gdelt`** e RSS dos principais veículos, agendados, para a vigilância.
6. **Saída arquivística**, mirando o formato do
   [atlas-of-resistance](https://github.com/mmillenaa/atlas-of-resistance).

## Decisões que são da pesquisa, não do código

- **Onde mora o corpus.** *Decidido em 04/10/2026:* o observatório guarda um **catálogo
  CSV** com três colunas, `id`, `url` e `identificadores` (as chaves do léxico que
  decidiram pelo item na primeira vez), e não guarda o texto (`"guardar_texto": false`).
  O CSV cabe em git e cresce sem reescrever linha. O preço é conhecido: sem texto,
  `retriar` não funciona, e um léxico novo exige baixar de novo; e página que sair do ar
  só se recupera pelo Wayback. Configuração:
  `"guardar_texto": false, "catalogo": {"arquivo": "catalogo.csv", "nivel_minimo": 2}`.
- **O que se publica.** O Argos guarda o texto porque fontes somem. Republicar o texto
  integral de terceiros é outra questão (direito autoral); publicar o catálogo com URL,
  data, captura do Wayback e trecho é o caminho seguro.
- **Pessoas.** Vítimas, familiares e réus aparecem nos textos. Por política, o Argos não
  cruza fontes para montar perfil de ninguém; o catálogo descreve documentos, não pessoas.
