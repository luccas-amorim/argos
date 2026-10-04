"""A configuração de um consumidor: qual léxico, quais fontes, onde gravar.

    {
      "lexico": "lexico.json",
      "diretorio": "dados",
      "desde": "2026-09-01",
      "margem_dias": 2,
      "guardar_texto": true,
      "catalogo": {"arquivo": "catalogo.csv", "nivel_minimo": 2},
      "fontes": [{"tipo": "rss", "id": "rss:exemplo", "url": "https://..."}]
    }

Caminhos relativos são resolvidos a partir do arquivo de configuração. Em `diretorio`
moram `estado/`, `corpus/` e `saidas/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Config:
    lexico: Path
    diretorio: Path
    fontes: tuple[dict, ...]
    desde: date | None = None
    # Quanto voltar antes da última rodada: fonte que publica com atraso ou com data
    # retroativa não escapa. O estado impede a releitura do que já foi visto.
    margem_dias: int = 2
    # False: o texto integral é lido, triado e descartado; nada vai para `corpus/`.
    guardar_texto: bool = True
    # {"arquivo": "catalogo.csv", "nivel_minimo": 2}: mantém o catálogo CSV cumulativo.
    catalogo: dict | None = None

    @property
    def catalogo_csv(self) -> Path | None:
        if not self.catalogo:
            return None
        return self.diretorio / self.catalogo.get("arquivo", "catalogo.csv")

    @property
    def estado(self) -> Path:
        return self.diretorio / "estado"

    @property
    def corpus(self) -> Path:
        return self.diretorio / "corpus"

    @property
    def saidas(self) -> Path:
        return self.diretorio / "saidas"


def carregar(caminho: str | Path) -> Config:
    caminho = Path(caminho)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    base = caminho.parent
    fontes = dados.get("fontes") or []
    if not fontes:
        raise ValueError(f"{caminho}: nenhuma fonte configurada")
    ids = [f.get("id") for f in fontes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{caminho}: ids de fonte repetidos")
    return Config(
        lexico=(base / dados["lexico"]).resolve(),
        diretorio=(base / dados.get("diretorio", "dados")).resolve(),
        fontes=tuple(fontes),
        desde=date.fromisoformat(dados["desde"]) if dados.get("desde") else None,
        margem_dias=int(dados.get("margem_dias", 2)),
        guardar_texto=bool(dados.get("guardar_texto", True)),
        catalogo=dados.get("catalogo"),
    )
