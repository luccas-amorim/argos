"""Constantes e atalhos compartilhados pelos testes de rodada."""

from datetime import date

from argos import config, fontes, lexico, rodada

FEED = "https://tribunal.exemplo.jus.br/rss"
BASE = "https://tribunal.exemplo.jus.br/noticias/2026/10"


def _rodar(caminho, rede, **kw):
    c = config.carregar(caminho)
    casador = lexico.Casador(lexico.carregar(c.lexico))
    instancias = [fontes.construir(f, rede) for f in c.fontes]
    return c, rodada.rodar(c, instancias, casador, hoje=date(2026, 10, 4), **kw)
