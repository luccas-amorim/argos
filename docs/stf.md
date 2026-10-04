# STF: plano

O STF é o tribunal mais difícil dos três, e o que mais importa ao catálogo do AtlasPen:
uma ADI pode tirar um tipo penal do ordenamento, uma tese de repercussão geral muda a
aplicação de um atributo em todo o país. Este documento separa o que se sabe, o que
falta sondar e a ordem de trabalho.

## Onde o STF não está

| Caminho | Situação | Fonte |
|---|---|---|
| DataJud (CNJ) | **fora**: o STF não está sob o CNJ, e o índice não existe | documentação do DataJud; `datajud.py` |
| DJEN | **fora**: o STF publica no próprio DJe e não aderiu ao DJEN | [LegalCloud](https://legalcloud.com.br/tribunais-utilizando-djen/) (a conferir de novo antes de cada versão) |
| Pesquisa de jurisprudência (`jurisprudencia.stf.jus.br`) | **bloqueia acesso automatizado** (WAF) | README do AtlasPen, linha "Robô dos tribunais" |

O Argos não contorna o WAF: nem navegador automatizado, nem troca de IP, nem
cabeçalho de navegador para se passar por pessoa. É bloqueio deliberado, e a política do
projeto manda respeitar.

## O que o AtlasPen precisa do STF

O recorte é pequeno, e isso ajuda: **centenas de itens por ano, não milhares.**

1. **Controle concentrado** (ADI, ADPF, ADO) sobre norma penal ou processual penal:
   cautelar, julgamento de mérito, interpretação conforme, modulação. É o que muda o
   catálogo diretamente.
2. **Teses de repercussão geral** em matéria penal: novas, alteradas, canceladas.
3. **Súmulas vinculantes** penais.
4. **Julgados paradigmáticos** em HC e RHC, que o próprio Tribunal destaca no Informativo.

O `data/avisos.json` do AtlasPen já registra "ADI em curso" e "tese de repercussão
geral" com a data em que a fonte foi consultada. O robô do STF é quem mantém esse
arquivo honesto: o que ele achar vira pergunta na issue semanal, nunca dado direto.

## Fontes candidatas, por ordem de valor sobre custo

Nenhuma foi sondada ainda: a rede do ambiente em que este plano foi escrito bloqueava
os hosts do STF. A coluna "a sondar" é o roteiro da primeira sessão com rede, **a partir
de IP brasileiro** (o DJEN e o STJ já mostraram que tribunal brasileiro pode recusar
acesso de fora do país).

| # | Fonte | Entrega | Adaptador | A sondar |
|---|---|---|---|---|
| A | **Teses de repercussão geral** (portal, menu Repercussão Geral) | tema, caso paradigma, tese, situação | `lista`: lê uma tabela e compara com a rodada anterior | se a lista tem endereço estável e se responde sem WAF; se há exportação |
| B | **Súmulas vinculantes** (portal) | número, enunciado, situação | `lista`, o mesmo | idem |
| C | **Corte Aberta** (`transparencia.stf.jus.br`) | painéis com exportação em CSV: decisões, histórico de repercussão geral, plenário virtual ([Corte Aberta](https://transparencia.stf.jus.br/extensions/corte_aberta/corte_aberta.html)) | `csv` genérico, se a exportação tiver endereço estável | os painéis são Qlik; se o CSV só sai por clique, a exportação vira tarefa humana mensal, e o Argos lê o arquivo baixado (`arquivo`) |
| D | **Informativo STF** | resumo semanal dos julgados relevantes, organizado por ramo do direito, com seções de penal e processual penal | `rss`, se houver feed; senão, `lista` sobre o índice das edições | formato (HTML ou PDF) e se há feed |
| E | **Acompanhamento processual** de ações conhecidas | andamento de cada ADI ou ADPF da lista do `avisos.json` | `stf-processo`: uma página por ação, com o número vindo do AtlasPen | se a página do processo está atrás do mesmo WAF da pesquisa |
| F | **DJe do STF** | acórdãos publicados, texto integral | `stf-dje` | listagem por data e formato; volume alto, então só depois de A a E |

O adaptador **`lista`** é a peça nova que A, B e talvez D pedem, e é geral: serve a
qualquer página que seja uma tabela que muda devagar. O id de cada linha é o número do
item (tema, súmula) mais o hash do conteúdo da linha. Assim tese **alterada** volta a
ser lida, como o processo que ganhou movimento no `datajud`, e tese **cancelada**
aparece como linha que sumiu.

## Caminho institucional

Se as fontes A a E estiverem todas atrás do WAF, sobra um caminho que não é técnico: o
pedido. O programa Corte Aberta (Resolução STF 774/2022) trata de governança de dados
processuais, e a Lei de Acesso à Informação permite pedir formalmente os conjuntos de
que o projeto precisa, ou a liberação de acesso automatizado identificado. É mais lento
e é o caminho certo. Um projeto de pesquisa aberto, com User-Agent próprio, limite
declarado e código público, é o tipo de consumidor que essas políticas dizem querer.

## Ordem de trabalho

1. **Sondagem com IP brasileiro** das fontes A a F: status, `robots.txt`, presença de
   desafio anti-robô, formato, paginação. Uma resposta real de cada fonte que responder
   vira fixture, como a do DataJud do STM.
2. **Adaptador `lista`** e as fontes A e B. É o menor esforço com o maior ganho: teses e
   súmulas mudam pouco e cada mudança importa.
3. **Fonte E** sobre as ações do `avisos.json`, se o acompanhamento processual responder.
4. **Fonte D** (Informativo), para os julgados que não são tese nem controle concentrado.
5. **Fonte C** (Corte Aberta), automática ou com exportação humana mensal.
6. **Pedido por LAI**, em paralelo, se a sondagem mostrar bloqueio generalizado.
7. **Fonte F** (DJe), só se as anteriores deixarem lacuna que o volume justifique.
