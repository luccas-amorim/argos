"""Catálogo cumulativo em CSV: uma linha por URL, com o que decidiu buscá-la.

Três colunas, e só três:

| Coluna            | Conteúdo                                                        |
|-------------------|-----------------------------------------------------------------|
| `id`              | os 16 primeiros dígitos do sha256 da URL: estável entre rodadas |
| `url`             | o endereço do item                                              |
| `identificadores` | as chaves do léxico que casaram na primeira vez, separadas por `;` |

O arquivo cresce entre rodadas e nunca reescreve uma linha: a URL que volta numa rodada
seguinte, ou por outro canal, mantém os identificadores da primeira vez. O nível, o
motivo e o trecho de cada item continuam nos relatórios da rodada; o catálogo é o índice.
"""

from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

from argos.rodada import TRIADO, Rodada

COLUNAS = ("id", "url", "identificadores")


def id_da_url(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


def ler(caminho: Path) -> list[dict[str, str]]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def atualizar(rodada: Rodada, caminho: Path, nivel_minimo: int = 2) -> int:
    """Acrescenta as URLs novas da rodada com nível >= `nivel_minimo`. Devolve quantas."""
    caminho = Path(caminho)
    linhas = ler(caminho)
    conhecidos = {linha["id"] for linha in linhas}
    novas = 0
    for item in rodada.linhas:
        if item.situacao != TRIADO or (item.nivel or 0) < nivel_minimo:
            continue
        ident = id_da_url(item.ref.url)
        if ident in conhecidos:
            continue
        conhecidos.add(ident)
        linhas.append(
            {"id": ident, "url": item.ref.url, "identificadores": ";".join(item.resultado.chaves)}
        )
        novas += 1
    if novas or not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho.with_suffix(".csv.part")
        with temporario.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
            escritor.writeheader()
            escritor.writerows(linhas)
        os.replace(temporario, caminho)
    return novas
