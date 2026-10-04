# Observatório do Massacre do Carandiru

Este plano mudou de casa: o que é do observatório (léxico, fontes, catálogo, estimativa e
o plano de trabalho) mora no repositório
[`luccas-amorim/observatory`](https://github.com/luccas-amorim/observatory), que usa o
Argos como dependência fixada por commit.

O que ficou aqui é o que serve a qualquer consumidor:

- os adaptadores `wayback`, `openalex`, `gdelt` e `rss` (`argos/fontes/`);
- o catálogo CSV cumulativo e o modo `"guardar_texto": false` (`argos/saidas/catalogo.py`);
- a estimativa de cobertura por captura e recaptura, com canais por prefixo e estratos
  (`argos/estimativa.py`, comando `argos estimar`).
