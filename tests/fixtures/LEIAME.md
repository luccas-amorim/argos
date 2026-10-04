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
| `lexico-carandiru.json` | léxico de amostra; o real é mantido pela pesquisa |
