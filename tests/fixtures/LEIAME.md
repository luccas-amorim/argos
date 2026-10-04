# Fixtures

Os testes rodam sem rede, contra estes arquivos.

**Quase todos sintéticos, por ora.** A v0.1 foi escrita num ambiente cuja rede bloqueava
a maior parte das fontes (DJEN, dados abertos do STJ), então estes arquivos
imitam o formato documentado de cada origem. Cada um deve ser trocado por uma resposta
real, gravada, na primeira rodada com rede.

A exceção é `datajud/stm-real-2026-10-04.json`, gravada da API pública do DataJud com a
consulta do próprio adaptador. Ela já pagou o que custou: mostrou que, nos complementos
dos movimentos, `descricao` é o nome do campo e `nome` é o valor, o contrário do que a
fixture sintética supunha. Só traz metadado processual público (classe, assuntos,
órgão, movimentos), sem nome de parte.

| Arquivo | Imita |
|---|---|
| `rss/feed.xml` | RSS 2.0 das notícias de um tribunal |
| `rss/atom.xml` | Atom 1.0 de um repositório |
| `rss/noticia-tese.html` | notícia de tese em repetitivo, em windows-1252 declarado como iso-8859-1; o Tema 9.999 é fictício, para não atribuir tese a tribunal |
| `rss/noticia-outra.html` | notícia sem relação com o léxico |
| `rss/erro-200.html` | página de erro servida com HTTP 200 |
| `datajud/pagina1.json` | resposta de `_search` do DataJud, com assuntos aninhados e um processo em sigilo |
| `datajud/stm-real-2026-10-04.json` | **real**: `_search` no índice do STM, dois processos |
| `djen/stj-2026-10-01.json` | página da API do DJEN: um acórdão com ementa, um despacho, uma decisão monocrática; com destinatários fictícios, para provar que são descartados |
| `lista/sumulas.html` | página com duas tabelas (menu e lista), cabeçalho em `<th>`, linha sem número; números fictícios (901 a 903) para não atribuir texto a súmula real |
| `atlaspen/data/` | **real**: recorte de `crimes.json` e `diplomas.json` do AtlasPen (73 registros de sete artigos), copiado sem alteração do clone em 04/10/2026; CC BY 4.0, Luccas de Amorim |
| `lexico-penal.json` | léxico de amostra no formato que `exemplos/atlaspen/lexico.py` gera |
