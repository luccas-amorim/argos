"""API Pública do DataJud (CNJ): metadados e movimentos de todos os tribunais, menos o STF.

Documentação: https://datajud-wiki.cnj.jus.br/api-publica/

Técnica herdada do Dikemetria (`dikemetria/coleta/datajud.py`): Elasticsearch com
`search_after` sobre `@timestamp`, chave pública do CNJ com troca por variável de ambiente.

O DataJud **não traz o texto das decisões**. O "texto" que este adaptador entrega é a
ficha do processo escrita por extenso: classe, órgão, assuntos da TPU e movimentos. Serve
para achar processos por assunto ou classe e para saber que houve julgamento; o inteiro
teor vem de outra fonte (DJEN, dados abertos do STJ). O destaque é a lista de assuntos,
que é a classificação feita pelo próprio tribunal.

Medido em 04/10/2026, contra o índice do STM:

- **O índice não é em tempo real.** O registro mais recente tinha atualização de 23/09,
  onze dias antes da consulta. Se a carga atrasada preserva a data original da
  atualização, como parece, uma margem de 2 dias deixaria o lote atrasado antes da
  janela, perdido em silêncio. Por isso a margem padrão aqui é de 30 dias; o estado
  impede a releitura do que já foi visto.
- **É lento.** Uma consulta de um registro levou 37 s no servidor (`took`); a de página
  com filtro de data, 25 a 28 s. O tempo limite padrão aqui é de 180 s.

Configuração:
    {"tipo": "datajud", "id": "datajud:stj", "tribunal": "stj",
     "consulta": {"bool": {"should": [{"match": {"assuntos.codigo": 3372}}]}},
     "tamanho_pagina": 100, "limite_por_minuto": 30, "margem_dias": 30, "tempo_limite": 180}
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, datetime

from argos.captura import montar_documento
from argos.contrato import Documento, Referencia
from argos.http import Cliente, Transporte, transporte_urllib

URL_BASE = "https://api-publica.datajud.cnj.jus.br"
# Divulgada pelo CNJ na documentação acima e trocada de tempos em tempos. Se parar de
# funcionar, defina DATAJUD_API_KEY com a chave atual.
CHAVE_PUBLICA = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="


def converter_data(valor) -> date | None:
    """O DataJud mistura '20190528000000', '2019-05-28T00:00:00.000Z' e '2019-05-28'."""
    if not valor:
        return None
    valor = str(valor).strip()
    if valor[:8].isdigit() and (len(valor) == 8 or valor[8:].isdigit()):
        try:
            return datetime.strptime(valor[:8], "%Y%m%d").date()
        except ValueError:
            return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _assuntos(fonte: dict) -> list[dict]:
    saida = []
    for assunto in fonte.get("assuntos") or []:
        # Alguns tribunais aninham listas de assuntos.
        for item in assunto if isinstance(assunto, list) else [assunto]:
            if isinstance(item, dict):
                saida.append(item)
    return saida


def ficha(fonte: dict) -> tuple[str, str]:
    """(texto da ficha, destaque de assuntos)."""
    classe = fonte.get("classe") or {}
    orgao = fonte.get("orgaoJulgador") or {}
    assuntos = _assuntos(fonte)
    rotulos = [f"{a.get('nome', '')} ({a.get('codigo', '')})" for a in assuntos]
    linhas = [
        f"Processo {fonte.get('numeroProcesso', '')}",
        f"Tribunal: {fonte.get('tribunal', '')}  Grau: {fonte.get('grau', '')}",
        f"Classe: {classe.get('nome', '')} ({classe.get('codigo', '')})",
        f"Órgão julgador: {orgao.get('nome', '')}",
        f"Ajuizamento: {converter_data(fonte.get('dataAjuizamento')) or ''}",
        "Assuntos: " + "; ".join(rotulos),
        "",
        "Movimentos:",
    ]
    movimentos = sorted(fonte.get("movimentos") or [], key=lambda m: str(m.get("dataHora", "")))
    for mov in movimentos:
        # No DataJud, `descricao` é o nome do campo e `nome` é o valor:
        # {"descricao": "tipo_de_documento", "nome": "Mandado"} (conferido em resposta real).
        complementos = [
            f"{c.get('descricao')}: {c.get('nome')}" if c.get("descricao") else str(c.get("nome"))
            for c in mov.get("complementosTabelados") or []
            if isinstance(c, dict) and c.get("nome")
        ]
        extra = f" [{'; '.join(c for c in complementos if c)}]" if complementos else ""
        linhas.append(
            f"- {converter_data(mov.get('dataHora')) or '????-??-??'} "
            f"{mov.get('nome', '')} ({mov.get('codigo', '')}){extra}"
        )
    return "\n".join(linhas), "; ".join(rotulos)


class DataJud:
    respeita_robots = False  # API própria, com chave; robots.txt não se aplica

    def __init__(
        self,
        id: str,
        tribunal: str,
        cliente: Cliente,
        consulta: dict | None = None,
        tamanho_pagina: int = 100,
        limite_por_minuto: int = 30,
        margem_dias: int = 30,
    ) -> None:
        self.id = id
        self.tribunal = tribunal.lower()
        self.cliente = cliente
        self.consulta = consulta
        self.tamanho_pagina = tamanho_pagina
        self.limite_por_minuto = limite_por_minuto
        self.margem_dias = margem_dias

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> DataJud:
        limite = int(cfg.get("limite_por_minuto", 30))
        chave = os.environ.get("DATAJUD_API_KEY", CHAVE_PUBLICA)
        cliente = Cliente(
            limite,
            respeita_robots=cls.respeita_robots,
            transporte=transporte,
            cabecalhos={"Authorization": f"APIKey {chave}"},
            tempo_limite=float(cfg.get("tempo_limite", 180)),
        )
        return cls(
            cfg["id"],
            cfg["tribunal"],
            cliente,
            cfg.get("consulta"),
            int(cfg.get("tamanho_pagina", 100)),
            limite,
            int(cfg.get("margem_dias", 30)),
        )

    @property
    def url(self) -> str:
        return f"{URL_BASE}/api_publica_{self.tribunal}/_search"

    def montar_consulta(self, desde: date, apos: list | None = None) -> dict:
        filtros: list[dict] = [{"range": {"dataHoraUltimaAtualizacao": {"gte": desde.isoformat()}}}]
        if self.consulta:
            filtros.insert(0, self.consulta)
        consulta: dict = {
            "size": self.tamanho_pagina,
            "query": {"bool": {"must": filtros}},
            "sort": [{"@timestamp": {"order": "asc"}}],
        }
        if apos:
            consulta["search_after"] = apos
        return consulta

    def listar(self, desde: date) -> Iterator[Referencia]:
        apos: list | None = None
        while True:
            dados = self.cliente.requisitar(
                self.url, metodo="POST", json_corpo=self.montar_consulta(desde, apos)
            ).json()
            hits = dados.get("hits", {}).get("hits", [])
            for hit in hits:
                fonte = hit.get("_source", {})
                atualizado = fonte.get("dataHoraUltimaAtualizacao", "")
                # A atualização entra no id: processo que ganhou movimento volta a ser lido.
                yield Referencia(
                    fonte=self.id,
                    id_na_fonte=f"{hit.get('_id')}@{atualizado}",
                    url=f"{self.url}#{hit.get('_id')}",
                    titulo=f"{(fonte.get('classe') or {}).get('nome', '')} "
                    f"{fonte.get('numeroProcesso', '')}".strip(),
                    publicado_em=converter_data(atualizado),
                    dados=fonte,
                )
            apos = hits[-1].get("sort") if hits else None
            if len(hits) < self.tamanho_pagina or not apos:
                return

    def baixar(self, ref: Referencia) -> Documento:
        """Sem rede: a listagem já trouxe o registro inteiro, e não há mais o que buscar."""
        texto, assuntos = ficha(dict(ref.dados or {}))
        return montar_documento(ref, texto, destaques={"assuntos": assuntos})

    def sentinela(self, doc: Documento) -> bool:
        fonte = doc.ref.dados or {}
        # Segredo de justiça não entra no corpus, nem como metadado.
        if int(fonte.get("nivelSigilo") or 0):
            return False
        return bool(fonte.get("numeroProcesso")) and bool(fonte.get("classe"))
