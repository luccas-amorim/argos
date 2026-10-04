# Jurisprudência para o AtlasPen: STJ, STF e STM

Pergunta de partida: o AtlasPen pode começar a se beneficiar de decisões do STJ, do STF e
do STM que impactem o entendimento e a aplicação de normas penais, materiais e
processuais?

Resposta curta: **sim, em ordem de dificuldade crescente: STJ, STM, STF.** O STJ publica
no DJEN desde 28/11/2024 e mantém dados abertos com ementa e inteiro teor; o STM está no
DataJud (a adesão ao DJEN está por conferir); o STF não está no DataJud nem no DJEN e
bloqueia acesso automatizado à pesquisa de jurisprudência, o que exige um caminho
próprio, descrito em [stf.md](stf.md). O motor e os adaptadores `datajud` e `djen` estão
prontos; falta o gerador de léxico, que mora no AtlasPen.

**Restrição de infraestrutura, medida em 04/10/2026:** o DJEN recusa conexões de fora do
Brasil (CloudFront com bloqueio por país), e o portal de dados abertos do STJ também
recusou. Runner hospedado do GitHub sai dos EUA. A rodada de jurisprudência precisa de
**IP brasileiro**: runner próprio (uma máquina no Brasil registrada como self-hosted
runner do GitHub Actions) ou uma VM pequena em região de São Paulo. O Argos acusa o caso
com erro próprio (`BloqueadoPorPais`), em vez de um 403 genérico.

---

## O que cada fonte entrega

| Fonte | Tribunais | Texto da decisão? | Estado no Argos |
|---|---|---|---|
| **DataJud** (CNJ), API pública | STJ, STM e todos os demais, **menos o STF** | não: classe, assuntos da TPU, órgão e movimentos | **adaptador pronto** (`datajud`) |
| **DJEN** (Comunica PJe) | os que publicam no Diário de Justiça Eletrônico Nacional; o STJ desde 28/11/2024 | sim, o texto do ato publicado | **adaptador pronto** (`djen`), portado do Dikemetria; só responde a IP brasileiro |
| **Dados abertos do STJ** (CKAN) | STJ | sim: espelhos de acórdãos (ementa, órgão, referências) e íntegras de decisões terminativas e acórdãos | a escrever (`stj`); recusou acesso de fora do Brasil |
| **Pesquisa de jurisprudência do STF** | STF | sim | bloqueada por WAF a acesso automatizado (registrado no README do AtlasPen) |
| **Páginas de precedentes do STF** | STF | tese, súmula, ementa | plano em [stf.md](stf.md) |

**Medido em 04/10/2026**, na primeira rodada real do Argos (índice do STM no DataJud):
1.919 processos tiveram atualização entre 14/09 e 04/10; o mais recente era de 23/09, o
que mostra que o índice é carregado com atraso; cada página de consulta levou de 22 a
40 s no servidor. Daí a margem de 30 dias e o tempo limite de 180 s do adaptador. Os
assuntos vêm da TPU com nome legível ("Corrupção passiva", "Uso de documento falso"),
o que já permite ligar processo a tipo penal do catálogo pelo assunto, antes de haver
texto.

A técnica de conversar com tribunal já existe no Dikemetria e foi reaproveitada aqui: o
cliente educado (identificação, intervalo, nova tentativa em 429 e 5xx), a paginação do
DataJud por `search_after` e a chave pública com troca por variável de ambiente. O
Argos acrescentou o que o Dikemetria não precisava: `robots.txt`, sentinela de
integridade, estado entre rodadas e pendentes.

## Recorte: o que "impacta o entendimento" quer dizer em dado

Um robô que traga toda decisão penal do STJ traz centenas de milhares por ano, e
ninguém lê isso. O recorte proposto, do mais estreito ao mais largo:

1. **Precedentes qualificados**: recursos repetitivos e teses, repercussão geral,
   súmulas (novas, alteradas, canceladas), IAC, e no STF as ações de controle
   concentrado que atinjam norma penal. É o que muda o catálogo, como o README do
   AtlasPen já diz na linha "Robô dos tribunais".
2. **Acórdãos das turmas e seções criminais** (no STJ, Quinta e Sexta Turmas e Terceira
   Seção) que citem dispositivo vigiado pelo catálogo.
3. **Decisões monocráticas**, só se 1 e 2 se mostrarem estreitos demais.

O STM entra inteiro no recorte 2: quase tudo o que ele julga é penal militar, e o
volume é pequeno.

## O léxico, gerado de `crimes.json`

O léxico do AtlasPen não se escreve à mão: é gerado do catálogo, no repositório do
AtlasPen (`scripts/robos/jurisprudencia/lexico.py`, como o README do Argos propõe). Para
cada registro:

- **`chave`**: o id do registro (append-only, como a URL pública), para que a saída do
  Argos se ligue ao tipo sem ambiguidade.
- **`formas`**: o dispositivo com o diploma, nas grafias que os tribunais usam
  ("art. 121 do Código Penal", "art. 121 do CP", "art. 121, CP", "CP, art. 121") e o
  nome do tipo ("homicídio qualificado"). **Nunca o artigo sozinho**: "art. 121" existe
  em dezenas de diplomas.
- **`exclusoes`**: as que o próprio catálogo já conhece (o homicídio culposo na direção
  é o art. 302 do CTB, não o 121 do CP).
- **`categorias`**: lei, natureza (material ou processual), hediondez; servem de faceta.
- **`contexto.exige_qualquer`**: vocabulário decisório ("acórdão", "recurso", "ordem
  concedida", "tese", "dosimetria", "regime").

As normas **processuais** (CPP, LEP, Lei 9.099/95) não são tipos penais e não estão em
`crimes.json`. Se o recorte as incluir, o gerador lê também os atributos penais
(`data/atributos.json`), que já citam o dispositivo que os rege.

## Ordem de trabalho proposta

1. ~~**Adaptador `djen`**~~ **feito**: filtro por tribunal, por tipo de documento e pelo
   texto da própria API; a ementa do acórdão vira o destaque do nível 3; destinatários
   (partes e advogados) descartados na listagem. Falta a primeira rodada real, que
   depende de IP brasileiro.
2. **Adaptador `stj`** sobre os dados abertos: os espelhos têm a ementa, que é o
   destaque natural do nível 3 da triagem.
3. **Gerador de léxico no AtlasPen**, com teste que o valide por
   `argos validar-lexico`.
4. **Primeira rodada real** com `--desde` de alguns meses, só para medir o volume por
   nível antes de ligar o agendamento.
5. **`mapear.py` no AtlasPen**: o JSONL de aceitos vira `data/jurisprudencia.json`, e o
   que pede juízo vira pergunta na issue semanal, com a mesma regra dos outros robôs.
6. **STF**: o plano tem documento próprio, [stf.md](stf.md). O STF não está no DataJud:
   a versão anterior deste item sugeria buscar ADIs por lá, e estava errada.

## O que não fazer

- **Não contornar o WAF do STF** com navegador automatizado. É bloqueio deliberado, e a
  política do Argos manda respeitar.
- **Não decidir pelo resumo.** O DataJud diz que houve provimento, não o que foi
  decidido. Um item do DataJud aceito no nível 3 quer dizer "processo do assunto
  certo", não "decisão lida": o `mapear.py` do AtlasPen não deve transformar item só de
  metadado em jurisprudência sem buscar o texto.
- **Não gravar dado de parte.** Decisões penais trazem nomes de réus e vítimas. O corpus
  guarda o texto publicado, como a fonte publicou; o AtlasPen consome só a tese, o
  dispositivo e a referência do julgado.
