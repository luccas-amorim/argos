# -*- coding: utf-8 -*-
"""O contrato que todo adaptador de fonte cumpre.

Três funções e um bloco de metadados. O motor não sabe o que é um tribunal
nem um jornal: sabe listar, baixar e perguntar se o que baixou está íntegro.
Tudo o que for específico da origem fica dentro do adaptador, com fixture e
teste que rodam sem rede.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, Protocol


@dataclass(frozen=True)
class Referencia:
    """O que `listar` devolve: o suficiente para decidir baixar, nada mais."""
    fonte: str              # id do adaptador, p.ex. "datajud"
    id_na_fonte: str        # identificador estável dentro da origem
    url: str
    titulo: str | None = None
    publicado_em: date | None = None


@dataclass
class Documento:
    """O que `baixar` devolve: o item inteiro, com proveniência."""
    ref: Referencia
    texto: str                              # normalizado em UTF-8, sem marcação
    capturado_em: datetime
    hash_texto: str                         # sha256 do texto normalizado
    bruto: bytes | None = None              # HTML/JSON cru, quando houver
    cabecalhos: dict[str, str] = field(default_factory=dict)


class Fonte(Protocol):
    """Um adaptador. Instâncias são configuradas pelo consumidor (chaves, consultas)."""

    id: str
    limite_por_minuto: int      # declarado pelo adaptador; o motor obedece
    respeita_robots: bool       # True, salvo fonte que publique API própria

    def listar(self, desde: date) -> Iterable[Referencia]:
        """Enumera o que a fonte publicou a partir de `desde`.

        Pode paginar internamente. Não baixa texto. Deve ser idempotente:
        chamar duas vezes com a mesma data devolve as mesmas referências.
        """

    def baixar(self, ref: Referencia) -> Documento:
        """Baixa o item inteiro e normaliza codificação aqui, uma vez só.

        Nunca decide pelo resumo: se a origem só dá o resumo na listagem,
        é aqui que se busca o integral.
        """

    def sentinela(self, doc: Documento) -> bool:
        """Diz se o documento está íntegro.

        Página de erro com HTTP 200, texto truncado, "nenhum resultado" e
        captcha são rejeitados aqui, antes da triagem. Falhar é barato;
        aceitar texto ruim contamina a rodada em silêncio.
        """
