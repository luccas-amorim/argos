# Fontes judiciais: o que se mediu

O plano de uso da jurisprudência no AtlasPen mudou de casa e mora com o consumidor:
[`.superpowers/specs/2026-10-04-jurisprudencia.md`](https://github.com/luccas-amorim/atlaspen/blob/main/.superpowers/specs/2026-10-04-jurisprudencia.md)
e, para o STF,
[`2026-10-04-stf.md`](https://github.com/luccas-amorim/atlaspen/blob/main/.superpowers/specs/2026-10-04-stf.md).
Lá também estão o gerador de léxico (`scripts/robos/jurisprudencia/lexico.py`) e o mapa
de volta ao catálogo (`mapear.py`).

Fica aqui o que vale para qualquer consumidor das fontes judiciais, medido em 04/10/2026:

| Fonte | Adaptador | O que se mediu |
|---|---|---|
| DataJud (CNJ) | `datajud` | Índice carregado com atraso (no STM, o registro mais recente era de 11 dias antes) e lento (22 a 40 s por consulta no servidor). Margem padrão de 30 dias e tempo limite de 180 s. Sem texto de decisão. O STF não está no DataJud. |
| DJEN (Comunica PJe) | `djen` | CloudFront com **bloqueio por país**: só responde a IP brasileiro. O STJ publica nele desde 28/11/2024; o STF não aderiu. |
| Dados abertos do STJ | (a escrever) | Recusou acesso de fora do Brasil. |
| STF | `lista` (teses, súmulas) | Pesquisa de jurisprudência atrás de WAF, que o Argos não contorna. Plano no AtlasPen. |

Consequência prática: rodada que use DJEN ou dados do STJ precisa sair de IP brasileiro
(runner próprio registrado no GitHub Actions, máquina local ou VM em região de São
Paulo). O Argos acusa o caso com `BloqueadoPorPais`.
