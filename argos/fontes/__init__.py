"""Adaptadores de fonte. Um por origem, todos cumprindo `argos.contrato.Fonte`."""

from __future__ import annotations

from argos.contrato import Fonte
from argos.fontes.datajud import DataJud
from argos.fontes.djen import Djen
from argos.fontes.lista import Lista
from argos.fontes.rss import Rss
from argos.http import Transporte, transporte_urllib

TIPOS = {
    "rss": Rss,
    "datajud": DataJud,
    "djen": Djen,
    "lista": Lista,
}


def construir(cfg: dict, transporte: Transporte = transporte_urllib) -> Fonte:
    tipo = cfg.get("tipo")
    if tipo not in TIPOS:
        raise ValueError(f"tipo de fonte desconhecido: {tipo!r} (conhecidos: {sorted(TIPOS)})")
    if not cfg.get("id"):
        raise ValueError(f"fonte {tipo} sem id")
    return TIPOS[tipo].de_config(cfg, transporte)
