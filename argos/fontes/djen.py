"""Diário de Justiça Eletrônico Nacional (DJEN, Comunica PJe): o texto dos atos publicados.

O DJEN reúne as comunicações processuais dos tribunais que aderiram a ele (Resolução CNJ
455/2022): sentenças, acórdãos, decisões, despachos, intimações. O STJ publica nele desde
28/11/2024. O STF não aderiu. Cada comunicação traz o texto do ato e os destinatários.

Técnica herdada do Dikemetria (`dikemetria/coleta/djen.py`): um dia por vez, página a
página, filtro por tipo de documento sem distinguir acento. Diferença deliberada: aqui os
destinatários (partes e advogados) são descartados já na listagem e nunca chegam ao
estado nem ao corpus. O Argos guarda o texto que a fonte publicou, e só ele.

**Bloqueio por país.** Medido em 04/10/2026: a API está atrás de um CloudFront configurado
para recusar conexões de fora do Brasil. De um runner hospedado do GitHub (EUA) ou de
qualquer nuvem fora do país, a listagem falha com `BloqueadoPorPais`. A rodada precisa
sair de IP brasileiro.

Configuração:
    {"tipo": "djen", "id": "djen:stj", "tribunal": "STJ",
     "tipos_documento": ["Acórdão"], "texto": "Código Penal",
     "itens_por_pagina": 100, "limite_por_minuto": 20, "minimo_caracteres": 200}

`texto` é o filtro de texto da própria API: estreita a listagem antes do download, o
que importa num tribunal que publica milhares de atos por dia. É opcional, e o léxico
decide do mesmo jeito; um filtro largo demais só custa tempo, um estreito demais perde
item em silêncio.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from argos.captura import montar_documento
from argos.contrato import Documento, Referencia
from argos.http import Cliente, Transporte, transporte_urllib
from argos.texto import dobrar, html_para_texto, normalizar

URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"

# Dado pessoal que a API devolve e o Argos não guarda.
CAMPOS_DESCARTADOS = ("destinatarios", "destinatarioadvogados")

_INICIO_EMENTA = re.compile(r"(?m)^\s*ementa\b[\s:.\-–—]*")
_FIM_EMENTA = re.compile(r"(?m)^\s*(acordao|relatorio|voto|vistos|decisao)\b")
LIMITE_EMENTA = 4000


def _primeiro(item: dict, *chaves: str):
    for chave in chaves:
        valor = item.get(chave)
        if valor not in (None, ""):
            return valor
    return None


def _data(valor) -> date | None:
    if not valor:
        return None
    texto = str(valor).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[:10], formato).date()
        except ValueError:
            continue
    return None


def _sem_pessoas(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in CAMPOS_DESCARTADOS}


def extrair_ementa(texto: str) -> str | None:
    """O trecho entre "EMENTA" e o próximo marco do acórdão (ACÓRDÃO, RELATÓRIO, VOTO...).

    Busca no texto dobrado e recorta do original pelos mesmos índices.
    """
    dobrado = dobrar(texto)
    inicio = _INICIO_EMENTA.search(dobrado)
    if not inicio:
        return None
    fim = _FIM_EMENTA.search(dobrado, inicio.end())
    corte = fim.start() if fim else len(texto)
    ementa = texto[inicio.end() : min(corte, inicio.end() + LIMITE_EMENTA)].strip()
    return ementa or None


class Djen:
    respeita_robots = False  # API própria, sem robots.txt

    def __init__(
        self,
        id: str,
        tribunal: str,
        cliente: Cliente,
        texto: str | None = None,
        tipos_documento: tuple[str, ...] = (),
        itens_por_pagina: int = 100,
        limite_por_minuto: int = 20,
        minimo_caracteres: int = 200,
        hoje: Callable[[], date] = date.today,
    ) -> None:
        self.id = id
        self.tribunal = tribunal.upper()
        self.cliente = cliente
        self.texto = texto
        self.tipos_documento = tuple(dobrar(t) for t in tipos_documento)
        self.itens_por_pagina = itens_por_pagina
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres
        self.hoje = hoje

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Djen:
        limite = int(cfg.get("limite_por_minuto", 20))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(
            cfg["id"],
            cfg["tribunal"],
            cliente,
            cfg.get("texto"),
            tuple(cfg.get("tipos_documento", ())),
            int(cfg.get("itens_por_pagina", 100)),
            limite,
            int(cfg.get("minimo_caracteres", 200)),
        )

    def _parametros(self, dia: date, pagina: int) -> dict:
        params = {
            "siglaTribunal": self.tribunal,
            "dataDisponibilizacaoInicio": dia.isoformat(),
            "dataDisponibilizacaoFim": dia.isoformat(),
            "pagina": pagina,
            "itensPorPagina": self.itens_por_pagina,
        }
        if self.texto:
            params["texto"] = self.texto
        return params

    def _tipo_aceito(self, item: dict) -> bool:
        if not self.tipos_documento:
            return True
        tipo = dobrar(str(_primeiro(item, "tipoDocumento", "tipoComunicacao") or ""))
        return any(t in tipo for t in self.tipos_documento)

    def listar(self, desde: date) -> Iterator[Referencia]:
        """Um dia por vez, de `desde` até hoje; dentro do dia, página por página."""
        dia = desde
        while dia <= self.hoje():
            pagina = 1
            while True:
                params = self._parametros(dia, pagina)
                dados = self.cliente.requisitar(URL, params=params).json()
                itens = dados.get("items") or dados.get("itens") or []
                for item in itens:
                    if self._tipo_aceito(item):
                        yield self._referencia(item, dia)
                if len(itens) < self.itens_por_pagina:
                    break
                pagina += 1
            dia += timedelta(days=1)

    def _referencia(self, item: dict, dia: date) -> Referencia:
        ident = str(_primeiro(item, "id", "hash"))
        numero = _primeiro(item, "numeroprocessocommascara", "numero_processo", "numeroProcesso")
        tipo = _primeiro(item, "tipoDocumento", "tipoComunicacao") or "Comunicação"
        consulta = urlencode(
            {
                "siglaTribunal": self.tribunal,
                "dataDisponibilizacaoInicio": dia.isoformat(),
                "dataDisponibilizacaoFim": dia.isoformat(),
            }
        )
        return Referencia(
            fonte=self.id,
            id_na_fonte=ident,
            # Reproduzível: a consulta do dia, com o id da comunicação no fragmento.
            url=f"{URL}?{consulta}#{ident}",
            titulo=f"{tipo} {numero or ''}".strip(),
            publicado_em=_data(_primeiro(item, "data_disponibilizacao", "datadisponibilizacao"))
            or dia,
            dados=_sem_pessoas(item),
        )

    def baixar(self, ref: Referencia) -> Documento:
        """Sem rede: a listagem já trouxe o texto do ato."""
        item = dict(ref.dados or {})
        bruto = str(_primeiro(item, "texto", "conteudo") or "")
        # Normalizado antes de recortar a ementa, para que o destaque seja trecho do texto.
        texto = html_para_texto(bruto) if "<" in bruto else normalizar(bruto)
        destaques = {}
        if ementa := extrair_ementa(texto):
            destaques["ementa"] = ementa
        return montar_documento(ref, texto, destaques=destaques)

    def sentinela(self, doc: Documento) -> bool:
        return len(doc.texto) >= self.minimo_caracteres
