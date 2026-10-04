"""O que já foi visto, por fonte. É a única memória entre rodadas.

`<raiz>/<fonte>.json` guarda a data da última rodada concluída, o hash do texto de cada
id já capturado e os **pendentes**: referências cuja captura falhou ou que a sentinela
reprovou. Pendente é tentado de novo em toda rodada, mesmo fora da janela de datas; sem
isso, um item que falhou uma vez sairia da janela e nunca mais seria lido, em silêncio.
Apagar o arquivo equivale a reler tudo.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from argos.captura import nome_seguro
from argos.contrato import Referencia


@dataclass
class Estado:
    fonte: str
    ultima_rodada: date | None = None
    vistos: dict[str, str] = field(default_factory=dict)  # id_na_fonte -> hash_texto
    pendentes: dict[str, dict] = field(default_factory=dict)  # id_na_fonte -> referência

    def visto(self, id_na_fonte: str) -> bool:
        return id_na_fonte in self.vistos

    def pendurar(self, ref: Referencia, motivo: str) -> None:
        anterior = self.pendentes.get(ref.id_na_fonte, {})
        dados = asdict(ref)
        dados["publicado_em"] = ref.publicado_em.isoformat() if ref.publicado_em else None
        dados["dados"] = dict(ref.dados) if ref.dados is not None else None
        self.pendentes[ref.id_na_fonte] = {
            "ref": dados,
            "motivo": motivo,
            "tentativas": anterior.get("tentativas", 0) + 1,
        }

    def resolver(self, id_na_fonte: str, hash_texto: str) -> None:
        self.pendentes.pop(id_na_fonte, None)
        self.vistos[id_na_fonte] = hash_texto

    def referencias_pendentes(self) -> list[Referencia]:
        refs = []
        for item in self.pendentes.values():
            dados = dict(item["ref"])
            if dados.get("publicado_em"):
                dados["publicado_em"] = date.fromisoformat(dados["publicado_em"])
            refs.append(Referencia(**dados))
        return refs


def caminho(raiz: Path, fonte: str) -> Path:
    return Path(raiz) / f"{nome_seguro(fonte)}.json"


def ler(raiz: Path, fonte: str) -> Estado:
    arquivo = caminho(raiz, fonte)
    if not arquivo.exists():
        return Estado(fonte)
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    ultima = dados.get("ultima_rodada")
    return Estado(
        fonte,
        date.fromisoformat(ultima) if ultima else None,
        dados.get("vistos", {}),
        dados.get("pendentes", {}),
    )


def gravar(raiz: Path, estado: Estado) -> None:
    arquivo = caminho(raiz, estado.fonte)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_suffix(".json.part")
    dados = {
        "fonte": estado.fonte,
        "ultima_rodada": estado.ultima_rodada.isoformat() if estado.ultima_rodada else None,
        "vistos": dict(sorted(estado.vistos.items())),
        "pendentes": dict(sorted(estado.pendentes.items())),
    }
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, arquivo)
