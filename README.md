# Argos

<sub>O nome vem de Argos Panoptes. [Por quê?](MITO.md) O pacote Python ainda se chama `atalaia`, nome anterior do projeto.</sub>

**Vigilância determinística de fontes abertas, com léxico como dado e descarte auditável.**

Um motor que olha, em intervalo fixo, um conjunto de fontes na internet (tribunais,
diários oficiais, imprensa, repositórios acadêmicos, arquivos da web), baixa o texto
integral do que encontra, confronta com um vocabulário declarado em arquivo e separa o
que merece leitura humana do que não merece. O que ele descarta sai **nomeado, com o
motivo**. O que ele aceita sai com **proveniência**: URL, data de captura, hash do texto.

Não é um buscador. É o que fica entre a fonte e a pessoa que precisa ler: a rotina que
garante que nada publicado sobre um assunto passe em silêncio, e que ninguém precise ler
trezentas páginas por semana para descobrir isso.

> Nasceu do [Sentinela](https://github.com/luccas-amorim/atlaspen/blob/main/docs/os-robos.md)
> do AtlasPen, que vigia a Seção 1 do Diário Oficial em busca de lei penal nova. O Argos
> é a generalização: a mesma disciplina (texto integral, triagem em níveis, falso
> positivo aceitável, falso negativo não), separada do direito penal para servir a
> qualquer domínio que caiba num léxico.

---

## Os dois primeiros usos

| Caso | Fontes | Léxico | Saída |
|---|---|---|---|
| **Jurisprudência do AtlasPen** | DataJud (CNJ), STF, STJ | os tipos penais de `crimes.json`: nomes, artigos, rótulos de lei | decisões ligadas a cada tipo, para `data/jurisprudencia.json` |
| **Observatório do Massacre do Carandiru** | imprensa (RSS), repositórios acadêmicos, Wayback Machine | o universo léxico já catalogado pela pesquisa | corpus com proveniência, exportável para descrição arquivística |

Dois domínios sem nada em comum além da forma. É de propósito: se o motor serve aos dois
sem código específico de nenhum, ele é geral. Código que só um dos dois usa fica no
repositório daquele uso, não aqui.

---

## O que ele faz e o que não faz

**Faz.** Lista o que uma fonte publicou desde a última rodada. Baixa o texto **integral**
de cada item (nunca decide pelo resumo). Confronta com o léxico e classifica em níveis.
Grava cada item aceito com proveniência. Escreve o relatório da rodada em dois tamanhos:
completo (um item por linha, aceitos e descartados) e resumo (o que pede ação). Lembra o
que já viu, para não reapresentar.

**Não faz.** Não escreve em base de dados de ninguém: entrega arquivo e quem consome
decide. Não infere: onde o léxico não decide, o item vai para "pede juízo" com o trecho
que gerou a dúvida. Não usa modelo de linguagem na triagem. Um nível final com modelo
pode existir, mas é opt-in, marcado na saída como tal e nunca é o único critério de
aceitação.

**Não faz, por política.** Não ignora `robots.txt`. Não ultrapassa o limite de
requisições que cada adaptador declara. Não compila dados sobre pessoas além do texto
que a própria fonte publicou, e não cruza fontes para montar perfil de ninguém. Guarda o
texto porque fontes somem; guarda a proveniência porque texto sem origem não serve à
pesquisa.

---

## Arquitetura

```
fontes (adaptadores)        captura             léxico (dado)        triagem            saídas
 datajud, stf, stj,   ──▶   texto integral  ──▶  termos, variantes ──▶ níveis 0..3  ──▶  JSONL, CSV
 rss, wayback, dou          + proveniência       exclusões, pesos      descarte nomeado    issue, arquivística
                                 │                                          │
                                 └────────────── estado (já visto) ◀────────┘
```

Cinco peças, cada uma com um contrato pequeno e um diretório:

| Diretório | Peça | O que garante |
|---|---|---|
| `atalaia/fontes/` | **Adaptadores** | um por origem; mesmo contrato para todos (abaixo) |
| `atalaia/captura.py` | **Captura** | texto integral normalizado em UTF-8, hash, data; respeita limite da fonte; grava `.part` e só promove quando a sentinela de integridade passa |
| `atalaia/lexico.py` | **Léxico** | carrega e valida o vocabulário contra `exemplos/lexico.schema.json`; expande variantes; nunca contém termo em código |
| `atalaia/triagem.py` | **Triagem** | níveis, motivo de descarte, trecho que decidiu |
| `atalaia/saidas/` | **Saídas** | JSONL (canônico), CSV, issue no GitHub, export arquivístico |

O estado é um arquivo (`estado/<fonte>.json`) com os hashes já vistos e a data da última
rodada por fonte. Apagar o estado equivale a reler tudo. Nada mais é guardado entre
rodadas.

### O contrato do adaptador

Um adaptador é um módulo com três funções e um bloco de metadados. Está em
[`atalaia/contrato.py`](atalaia/contrato.py) como `Protocol`, com docstring por função.

```python
class Fonte(Protocol):
    id: str                      # "datajud", "stf", "rss:folha"
    limite_por_minuto: int       # declarado, não negociado
    respeita_robots: bool        # True, salvo fonte que publique API própria

    def listar(self, desde: date) -> Iterable[Referencia]: ...
    def baixar(self, ref: Referencia) -> Documento: ...
    def sentinela(self, doc: Documento) -> bool: ...
```

- `listar` devolve referências (URL, título, data de publicação, id na fonte). Pode ser
  paginado. Não baixa texto.
- `baixar` devolve o documento inteiro: texto, HTML cru quando houver, cabeçalhos
  relevantes. Normaliza codificação aqui, uma vez só.
- `sentinela` diz se o documento está íntegro: página de erro com HTTP 200, texto
  truncado e "resultado não encontrado" são rejeitados aqui, antes de chegar à triagem.

Todo adaptador vem com **fixtures** (HTML ou JSON reais, gravados) e testes que rodam sem
rede. Fonte que muda de forma quebra o teste, não a rodada em silêncio.

### O léxico como dado

```json
{
  "id": "atlaspen-tipos-penais",
  "versao": "2026-10-02",
  "termos": [
    {
      "chave": "cp-art-121",
      "formas": ["homicídio", "art. 121 do Código Penal", "art. 121, CP", "121 do CP"],
      "exclusoes": ["homicídio culposo na direção"],
      "peso": 1.0,
      "nota": "A exclusão aponta para o art. 302 do CTB, que é outro registro."
    }
  ],
  "contexto": {
    "exige_qualquer": ["pena", "condenação", "absolvição", "denúncia", "recurso"],
    "nota": "Sem um destes no texto, o item fica no nível 1 e não sobe."
  }
}
```

O léxico tem dono fora deste repositório. O do AtlasPen é gerado a partir de
`crimes.json`; o do Carandiru é mantido pela pesquisa que o catalogou. O Argos valida
o formato e aplica. Mudar um termo é um commit em dado, não em código.

### A triagem em níveis

| Nível | Significa | Vai para |
|---|---|---|
| 0 | nenhuma forma do léxico no texto | descartado, motivo `sem_termo` |
| 1 | termo presente, sem contexto exigido | descartado, motivo `sem_contexto`, com o trecho |
| 2 | termo e contexto presentes | **pede juízo**: entra no relatório, com trecho |
| 3 | termo, contexto e marcador forte da fonte (ementa, dispositivo, manchete) | **aceito**: entra na saída com proveniência |

O corte não apaga: nível 0 e 1 saem no relatório completo, uma linha cada, com o motivo.
É isso que torna o filtro auditável e permite retriar quando o léxico mudar, porque o
texto integral da rodada fica guardado.

---

## Como o AtlasPen usa

O Argos é **dependência** do AtlasPen, fixada por tag. O AtlasPen não copia código daqui.

```
argos/   (este repositório)              atlaspen/  (consumidor)
  fontes/datajud.py                         scripts/robos/jurisprudencia/
  fontes/stf.py                               lexico.py      ← gera o léxico a partir de crimes.json
  fontes/stj.py                               mapear.py      ← traduz a saída JSONL para data/jurisprudencia.json
  triagem.py, captura.py, saidas/jsonl.py     workflow       ← roda toda segunda, depois do Vigia
```

O que é geral (falar com tribunal, baixar inteiro teor, triar) mora aqui. O que é do
AtlasPen (quais termos, como uma decisão vira linha de `data/jurisprudencia.json`, qual
registro recebe o quê) mora lá. A fronteira é o JSONL: o Argos entrega documentos
aceitos com proveniência e as chaves do léxico que casaram; o AtlasPen decide o que fazer
com isso, com a mesma regra dos outros robôs: o que não é inequívoco vira pergunta na
issue, não dado.

Vantagens de estar separado, em vez de ser o sexto robô dentro do AtlasPen:

- **Fixtures de tribunal não poluem o repositório do catálogo.** Inteiro teor é grande e
  muda de layout; o lugar dele é junto do adaptador que o lê.
- **Correção em um lugar serve aos dois usos.** Quando o STJ mudar a página de busca, o
  conserto é um PR aqui e um bump de versão lá.
- **O catálogo continua "sem servidor, sem banco, só arquivo"**, porque a vigilância é
  processo e o AtlasPen continua sendo dado.
- O Sentinela pode migrar para cá quando fizer sentido, como adaptador `dou`. Não é
  pré-requisito e não há pressa: ele funciona onde está.

## Como o observatório do Carandiru usa

Mesmo desenho, outro consumidor: um repositório do observatório com o léxico, a lista de
fontes (RSS de veículos, Google Notícias por consulta, SciELO, BDTD, Zenodo, Wayback
para o que já saiu do ar) e o mapeamento da saída para o formato de descrição que a
pesquisa adota. O adaptador `wayback` é o que mais importa ali: fonte que sumiu ainda tem
texto, e o texto tem data de captura.

A saída arquivística (`saidas/arquivistica.py`) escreve os campos mínimos de proveniência
num formato que o grupo escolher; a primeira versão vai mirar o que já existe no
[atlas-of-resistance](https://github.com/mmillenaa/atlas-of-resistance), para que o
corpus possa entrar no grafo sem retrabalho.

---

## Roadmap

- **v0.1** motor: contrato, captura com `.part` e sentinela, léxico com schema e
  validação, triagem em níveis, estado, saída JSONL, relatório em dois tamanhos.
  Um adaptador de cada família para provar o contrato: `rss` (genérico) e `datajud`.
- **v0.2** jurisprudência: `stf`, `stj` com fixtures; exemplo de consumidor em
  `exemplos/atlaspen/`. Primeira rodada real contra o léxico gerado de `crimes.json`.
- **v0.3** observatório: `wayback`, `google-noticias`, `scielo`; saída arquivística;
  exemplo de consumidor em `exemplos/observatorio/` com léxico de amostra.
- **depois** saída issue no GitHub, nível opt-in com modelo (marcado), migração do `dou`.

## Rodar

```bash
python -m atalaia rodar --config exemplos/atlaspen/config.json       # uma rodada
python -m atalaia rodar --config ... --desde 2026-09-01 --sem-estado  # reler tudo
python -m atalaia validar-lexico exemplos/lexico.exemplo.json
python -m pytest                                                      # sem rede, contra fixtures
```

Saídas: `0` nada a ler; `2` erro de execução ou fonte fora do ar; `3` há itens que pedem juízo.

## Licença

Código sob MIT. Os léxicos e as saídas pertencem a quem os mantém e seguem a licença de
cada repositório consumidor.
