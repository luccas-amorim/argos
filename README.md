# Argos

<sub>O nome vem de Argos Panoptes. [Por quê?](MITO.md)</sub>

**Vigilância determinística dos tribunais superiores e do CNJ para o AtlasPen, com léxico
como dado e descarte auditável.**

O Argos olha, em intervalo fixo, o que os tribunais superiores e o CNJ publicam, baixa o
texto integral do que encontra, confronta com um vocabulário gerado do catálogo do
[AtlasPen](https://github.com/luccas-amorim/atlaspen) e separa o que merece leitura
humana do que não merece: a decisão que muda o entendimento de um tipo penal, a tese de
repercussão geral, o recurso repetitivo, a súmula, a ação que tira uma norma penal do
ordenamento. O que ele descarta sai **nomeado, com o motivo**. O que ele aceita sai com
**proveniência**: URL, data de captura, hash do texto.

Não é um buscador. É o que fica entre o tribunal e a pessoa que mantém o catálogo: a
rotina que garante que nada decidido sobre um tipo penal passe em silêncio, e que
ninguém precise ler trezentas decisões por semana para descobrir isso.

> Nasceu do [Sentinela](https://github.com/luccas-amorim/atlaspen/blob/main/docs/os-robos.md)
> do AtlasPen, que vigia a Seção 1 do Diário Oficial em busca de lei penal nova. O Argos
> faz o mesmo do lado dos tribunais, com a mesma disciplina: texto integral, triagem em
> níveis, falso positivo aceitável, falso negativo não.

**Expansão em estudo:** estudos de precatórios e processamento de grandes volumes de
dados em planilha. Cenários em [docs/precatorios.md](docs/precatorios.md).

---

## O que ele vigia

| Fonte | Tribunal | O que entrega | Adaptador |
|---|---|---|---|
| **DJEN** (Diário de Justiça Eletrônico Nacional) | STJ (desde 28/11/2024) e os demais que aderiram | texto das decisões publicadas; a ementa é o destaque | `djen` |
| **DataJud** (API pública do CNJ) | STJ, STM e todos os demais, menos o STF | classe, assuntos da TPU, órgão e movimentos; sem texto | `datajud` |
| **Páginas de precedentes** | STF: teses de repercussão geral, súmulas vinculantes | tabela que muda devagar; linha alterada volta a ser lida | `lista` |
| **Notícias dos tribunais** | STF, STJ, CNJ (feeds a conferir) | o aviso do julgamento, antes do acórdão | `rss` |

A sondar (plano em [docs/jurisprudencia.md](docs/jurisprudencia.md) e
[docs/stf.md](docs/stf.md)): dados abertos do STJ (espelhos e íntegras), Informativo e
acompanhamento processual do STF, os atos normativos do CNJ que mexem em execução e
processo penal, e o **TSE**, porque o catálogo tem crimes do Código Eleitoral.

O STF não está no DataJud nem no DJEN, e a pesquisa de jurisprudência dele bloqueia
acesso automatizado. O Argos não contorna: usa as páginas de precedentes e, se elas
também forem bloqueadas, o pedido formal de acesso.

---

## O que ele faz e o que não faz

**Faz.** Lista o que uma fonte publicou desde a última rodada. Baixa o texto **integral**
de cada item (nunca decide pelo resumo). Confronta com o léxico e classifica em níveis.
Grava cada item aceito com proveniência. Escreve o relatório da rodada em dois tamanhos:
completo (um item por linha, aceitos e descartados) e resumo (o que pede ação). Lembra o
que já viu, para não reapresentar.

**Não faz.** Não escreve no AtlasPen: **lê** o catálogo dele e entrega arquivo; quem
mantém o AtlasPen decide o que entra. Não infere: onde o léxico não decide, o item vai
para "pede juízo" com o trecho que gerou a dúvida. Não usa modelo de linguagem na
triagem. Um nível final com modelo pode existir, mas é opt-in, marcado na saída como tal
e nunca é o único critério de aceitação.

**Não faz, por política.** Não ignora `robots.txt` nem contorna bloqueio (WAF, CAPTCHA,
bloqueio por país). Não ultrapassa o limite de requisições que cada adaptador declara.
Não compila dados sobre pessoas além do texto que a própria fonte publicou, e não cruza
fontes para montar perfil de ninguém: os destinatários das comunicações do DJEN (partes e
advogados) são descartados já na listagem. Guarda o texto porque decisões mudam de
endereço; guarda a proveniência porque texto sem origem não serve ao catálogo.

---

## Arquitetura

```
fontes (adaptadores)        captura             léxico (dado)        triagem            saídas
 djen, datajud,       ──▶   texto integral  ──▶  termos, variantes ──▶ níveis 0..3  ──▶  JSONL
 lista, rss                 + proveniência       exclusões, pesos      descarte nomeado    relatório
                                 │                                          │
                                 └────────────── estado (já visto) ◀────────┘
```

| Diretório | Peça | O que garante |
|---|---|---|
| `argos/fontes/` | **Adaptadores** | um por origem; mesmo contrato para todos (abaixo) |
| `argos/http.py` | **Cliente** | identifica o projeto, obedece o limite declarado e o `robots.txt`, tenta de novo em 429 e 5xx, acusa `BloqueadoPorPais` |
| `argos/captura.py` | **Captura** | texto integral normalizado em UTF-8, hash, data; grava `.part` e só promove quando a sentinela de integridade passa |
| `argos/lexico.py` | **Léxico** | carrega e valida o vocabulário contra `exemplos/lexico.schema.json`; nunca contém termo em código |
| `argos/triagem.py` | **Triagem** | níveis, motivo de descarte, trecho que decidiu |
| `argos/saidas/` | **Saídas** | JSONL (canônico) e relatório em dois tamanhos |
| `exemplos/atlaspen/` | **Consumidor** | gera o léxico do catálogo do AtlasPen e leva a rodada de volta aos registros, como relatório |

O estado é um arquivo (`estado/<fonte>.json`) com os hashes já vistos, a data da última
rodada por fonte e os **pendentes**: itens cuja captura falhou ou que a sentinela
reprovou. Pendente é tentado de novo em toda rodada, mesmo depois de sair da janela de
datas; sem isso, um item que falhou uma vez sumiria em silêncio. Apagar o estado equivale
a reler tudo. Além do estado, o corpus (o texto integral de cada item íntegro) é guardado
entre rodadas, e é ele que permite retriar quando o léxico muda.

### O contrato do adaptador

Um adaptador é um módulo com três funções e um bloco de metadados. Está em
[`argos/contrato.py`](argos/contrato.py) como `Protocol`, com docstring por função.

```python
class Fonte(Protocol):
    id: str                      # "djen:stj", "datajud:stm", "stf:sumulas"
    limite_por_minuto: int       # declarado, não negociado
    respeita_robots: bool        # True, salvo fonte que publique API própria

    def listar(self, desde: date) -> Iterable[Referencia]: ...
    def baixar(self, ref: Referencia) -> Documento: ...
    def sentinela(self, doc: Documento) -> bool: ...
```

- `listar` devolve referências (URL, título, data de publicação, id na fonte). Pode ser
  paginado. Não baixa texto.
- `baixar` devolve o documento inteiro: texto, cabeçalhos relevantes e os **destaques**
  (a ementa, os assuntos da TPU). Normaliza codificação aqui, uma vez só.
- `sentinela` diz se o documento está íntegro: página de erro com HTTP 200, texto
  truncado, processo em segredo de justiça e "resultado não encontrado" são rejeitados
  aqui, antes de chegar à triagem.

Todo adaptador vem com **fixtures** e testes que rodam sem rede. Fonte que muda de forma
quebra o teste, não a rodada em silêncio.

### O léxico como dado

O léxico do AtlasPen não se escreve à mão: `exemplos/atlaspen/lexico.py` o gera de
`data/crimes.json` e `data/diplomas.json`, um termo por artigo de cada diploma:

```json
{
  "chave": "cp-art-121",
  "formas": ["art. 121 … Código Penal", "art. 121 … CP", "CP, art. 121"],
  "exclusoes": ["art. 121 … Código Penal Militar"],
  "categorias": ["cp"]
}
```

O casamento ignora maiúsculas e acentos, exige palavra inteira e tolera quebra de linha
onde a forma tem espaço. Reticências (`…`) valem até 60 caracteres quaisquer, para casar
citações como "art. 121, § 2º, IV, do Código Penal". Ocorrência que cai dentro de uma
`exclusao` não conta: é assim que o art. 121 do CPM não vira art. 121 do CP. Mudar um
termo é mudar o catálogo do AtlasPen, não o código daqui.

### A triagem em níveis

| Nível | Significa | Vai para |
|---|---|---|
| 0 | nenhuma forma do léxico no texto | descartado, motivo `sem_termo` |
| 1 | termo presente, sem contexto decisório | descartado, motivo `sem_contexto`, com o trecho |
| 2 | termo e contexto presentes | **pede juízo**: entra no relatório, com trecho |
| 3 | termo, contexto e marcador forte da fonte (ementa, assuntos da TPU, manchete) | **aceito**: entra na saída com proveniência |

O corte não apaga: nível 0 e 1 saem no relatório completo, uma linha cada, com o motivo.
É isso que torna o filtro auditável e permite retriar quando o léxico mudar.

---

## Como o AtlasPen usa

**O AtlasPen é lido, nunca editado.** O Argos recebe o diretório de um clone dele, lê o
catálogo, gera o léxico, vigia os tribunais e entrega dois arquivos: o JSONL dos aceitos
e o relatório por registro (`exemplos/atlaspen/mapear.py`), separando o que foi ligado
por **citação** (segura) do que foi ligado só pelo **nome** do tipo (pede juízo). Levar
isso ao catálogo é decisão de quem mantém o AtlasPen, com a regra de lá: o que não é
inequívoco vira pergunta, não dado.

```bash
python exemplos/atlaspen/lexico.py --atlaspen ../atlaspen --saida exemplos/atlaspen/lexico.json
argos rodar --config exemplos/atlaspen/config.json --desde 2026-09-01
python exemplos/atlaspen/mapear.py dados-atlaspen/saidas/<rodada> --atlaspen ../atlaspen --md relatorio.md
```

Vantagens de estar separado, em vez de ser mais um robô dentro do AtlasPen: fixtures de
tribunal não poluem o repositório do catálogo; o catálogo continua "sem servidor, sem
banco, só arquivo"; e a vigilância, que precisa de IP brasileiro para o DJEN, roda onde
puder sem mudar nada lá.

---

## Expansão: precatórios e planilhas

Duas capacidades novas, ainda em estudo: **acompanhar precatórios** (as listas de ordem
cronológica que cada tribunal publica por ente devedor, o mapa anual, o regime especial)
e **processar grandes volumes de dados em planilha** (dezenas de arquivos XLSX e PDF,
com layouts diferentes, para uma tabela única com relatório de qualidade). Exigem peças
que o Argos ainda não tem: leitura de tabela, retrato no tempo, diferença entre
retratos, validadores de número CNJ, moeda e data. Os cenários, as fontes e o que decidir
estão em [docs/precatorios.md](docs/precatorios.md).

---

## Roadmap

- **v0.1** (feita) motor: contrato, captura com `.part` e sentinela, léxico com schema,
  triagem em níveis, estado com pendentes, JSONL, relatório em dois tamanhos; `rss` e
  `datajud`, com a primeira rodada real contra o DataJud do STM em 04/10/2026.
- **v0.2** tribunais: `djen` e `lista` (**feitos**), exemplo do AtlasPen (**feito**:
  gerador de léxico e mapa de volta). Faltam: primeira rodada real com IP brasileiro,
  fontes do STF (teses, súmulas, ADIs do `avisos.json`), `stj` sobre os dados abertos,
  atos normativos do CNJ, TSE.
- **v0.3** precatórios e planilhas, a partir do cenário que for escolhido.
- **depois** saída como issue no GitHub, nível opt-in com modelo (marcado), migração do
  `dou`.

## Rodar

Só biblioteca padrão; Python 3.11 ou mais novo.

```bash
pip install -e ".[dev]"
python -m argos rodar --config exemplos/config.exemplo.json         # uma rodada
python -m argos rodar --config ... --desde 2026-09-01 --sem-estado  # reler tudo
python -m argos retriar --config ...                                # léxico novo, corpus guardado, sem rede
python -m argos validar-lexico exemplos/lexico.exemplo.json
python -m pytest                                                      # sem rede, contra fixtures
```

Cada rodada escreve em `<diretorio>/saidas/<id>/`: `aceitos.jsonl` (nível 3, com
proveniência), `pede-juizo.jsonl` (nível 2), `itens.jsonl` (todos, com o motivo),
`relatorio-resumo.md`, `relatorio-completo.md` e `rodada.json`.

**Onde rodar.** O DJEN (CloudFront com bloqueio por país) e o portal de dados abertos do
STJ recusam conexão de fora do Brasil, medido em 04/10/2026. Runner hospedado do GitHub
sai dos EUA. Para essas fontes, a rodada precisa de IP brasileiro: runner próprio
registrado no GitHub Actions, máquina local ou VM em região de São Paulo. O Argos acusa o
caso com `BloqueadoPorPais` no relatório.

Códigos de saída: `0` nada a ler; `2` erro de execução ou fonte fora do ar; `3` há itens
que pedem leitura (níveis 2 e 3).

## Licença

Código sob MIT. Os dados do AtlasPen usados como fixture seguem a licença deles (CC BY
4.0); os relatórios que o Argos gera pertencem a quem os consome.
