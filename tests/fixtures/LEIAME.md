# Fixtures

Os testes rodam sem rede, contra estes arquivos.

**Quase todos sintéticos, por ora.** A v0.1 foi escrita num ambiente cuja rede bloqueava
a maior parte das fontes (DJEN, dados abertos do STJ, Wayback), então estes arquivos
imitam o formato documentado de cada origem. Cada um deve ser trocado por uma resposta
real, gravada, na primeira rodada com rede.

A exceção é `datajud/stm-real-2026-10-04.json`, gravada da API pública do DataJud com a
consulta do próprio adaptador. Ela já pagou o que custou: mostrou que, nos complementos
dos movimentos, `descricao` é o nome do campo e `nome` é o valor, o contrário do que a
fixture sintética supunha. Só traz metadado processual público (classe, assuntos,
órgão, movimentos), sem nome de parte.

| Arquivo | Imita |
|---|---|
| `rss/feed.xml` | RSS 2.0 de um veículo de imprensa |
| `rss/atom.xml` | Atom 1.0 de um repositório |
| `rss/materia-carandiru.html` | matéria em windows-1252 declarado como iso-8859-1 |
| `rss/materia-outra.html` | matéria sem relação com o léxico |
| `rss/erro-200.html` | página de erro servida com HTTP 200 |
| `datajud/pagina1.json` | resposta de `_search` do DataJud, com assuntos aninhados e um processo em sigilo |
| `datajud/stm-real-2026-10-04.json` | **real**: `_search` no índice do STM, dois processos |
| `djen/stj-2026-10-01.json` | página da API do DJEN: um acórdão com ementa, um despacho, uma decisão monocrática; com destinatários fictícios, para provar que são descartados |
| `lista/sumulas.html` | página com duas tabelas (menu e lista), cabeçalho em `<th>`, linha sem número; números fictícios (901 a 903) para não atribuir texto a súmula real |
| `wayback/cdx-p1.json`, `cdx-p2.json` | respostas do servidor CDX em JSON, a primeira com chave de retomada |
| `wayback/captura.html`, `nao-arquivada.html` | cópia arquivada (modo `id_`) e a página de "não arquivada" servida com 200 |
| `openalex/p1.json`, `p2.json` | `/works` com resumo em índice invertido e paginação por cursor |
| `gdelt/dia.json` | `artlist` em JSON do DOC 2.0 |
| `atlaspen/data/` | **real**: recorte de `crimes.json` e `diplomas.json` do AtlasPen (73 registros de sete artigos), copiado sem alteração do clone em 04/10/2026; CC BY 4.0, Luccas de Amorim |
| `lexico-carandiru.json` | léxico de amostra; o real é mantido pela pesquisa |
