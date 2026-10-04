"""Wayback Machine (Internet Archive): o que um domínio publicou e o arquivo guardou.

Não há busca por texto no Wayback, só por endereço. Este adaptador pergunta ao servidor
CDX, domínio a domínio, por toda URL arquivada cujo endereço case uma expressão (por
exemplo, `carandiru` no caminho da matéria), e baixa a cópia arquivada. É o canal que
recupera o que já saiu do ar, e cada texto vem com a data da captura.

API: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

- `filter=original:<regex>` filtra pelo endereço; `(?i)` torna a busca insensível a caixa.
- `collapse=urlkey` devolve uma captura por URL (a primeira na janela).
- `showResumeKey=true` pagina: a última linha da resposta é a chave da próxima página.
- O texto vem do modo `id_` (`/web/<timestamp>id_/<url>`), que serve o conteúdo
  arquivado sem a barra de navegação do Wayback.

`publicado_em` é a **data da captura**, não da publicação: o Wayback não sabe quando a
página foi publicada, só quando a viu. `desde` filtra capturas, e uma varredura do passivo
usa `--desde 1996-01-01`.

O CDX e o modo `id_` são a interface pública e documentada do arquivo para uso
programático; o adaptador declara API própria (não lê `robots.txt`) e se limita a 15
requisições por minuto, abaixo do que o Internet Archive tolera.

Configuração:
    {"tipo": "wayback", "id": "wayback:folha", "dominio": "folha.uol.com.br",
     "filtro": "(?i).*carandiru.*", "limite_por_minuto": 15, "minimo_caracteres": 400,
     "por_pagina": 1000}
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from urllib.parse import urlencode

from argos.contrato import Documento, Referencia
from argos.fontes.rss import MARCAS_DE_ERRO, documento_html, pagina_integra
from argos.http import Cliente, Transporte, transporte_urllib

CDX = "https://web.archive.org/cdx/search/cdx"
ARQUIVO = "https://web.archive.org/web"
CAMPOS = "timestamp,original,statuscode,mimetype,digest"

MARCAS_DO_WAYBACK = (
    *MARCAS_DE_ERRO,
    "wayback machine doesn't have that page archived",
    "hrm. the wayback machine has not archived",
    "this url has been excluded from the wayback machine",
)


def _data(timestamp: str) -> date | None:
    try:
        return datetime.strptime(timestamp[:8], "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


class Wayback:
    respeita_robots = False  # API documentada do arquivo; ver docstring

    def __init__(
        self,
        id: str,
        dominio: str,
        cliente: Cliente,
        filtro: str = "(?i).*carandiru.*",
        limite_por_minuto: int = 15,
        minimo_caracteres: int = 400,
        por_pagina: int = 1000,
    ) -> None:
        self.id = id
        self.dominio = dominio
        self.cliente = cliente
        self.filtro = filtro
        self.limite_por_minuto = limite_por_minuto
        self.minimo_caracteres = minimo_caracteres
        self.por_pagina = por_pagina

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Wayback:
        limite = int(cfg.get("limite_por_minuto", 15))
        cliente = Cliente(
            limite,
            respeita_robots=cls.respeita_robots,
            transporte=transporte,
            tempo_limite=float(cfg.get("tempo_limite", 120)),
        )
        return cls(
            cfg["id"],
            cfg["dominio"],
            cliente,
            cfg.get("filtro", "(?i).*carandiru.*"),
            limite,
            int(cfg.get("minimo_caracteres", 400)),
            int(cfg.get("por_pagina", 1000)),
        )

    def _parametros(self, desde: date, retomar: str | None) -> list[tuple[str, str]]:
        # Lista de pares: `filter` se repete, e um dicionário perderia as repetições.
        params = [
            ("url", self.dominio),
            ("matchType", "domain"),
            ("filter", f"original:{self.filtro}"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("collapse", "urlkey"),
            ("output", "json"),
            ("fl", CAMPOS),
            ("from", desde.strftime("%Y%m%d")),
            ("limit", str(self.por_pagina)),
            ("showResumeKey", "true"),
        ]
        if retomar:
            params.append(("resumeKey", retomar))
        return params

    def listar(self, desde: date) -> Iterator[Referencia]:
        retomar: str | None = None
        while True:
            url = f"{CDX}?{urlencode(self._parametros(desde, retomar))}"
            linhas = self.cliente.requisitar(url).json() or []
            if not linhas:
                return
            cabecalho, corpo = linhas[0], linhas[1:]
            retomar = None
            # Com showResumeKey, o fim é: [..., [], ["<chave>"]].
            if len(corpo) >= 2 and corpo[-2] == [] and len(corpo[-1]) == 1:
                retomar = corpo[-1][0]
                corpo = corpo[:-2]
            for valores in corpo:
                if not valores:
                    continue
                registro = dict(zip(cabecalho, valores, strict=False))
                original, momento = registro.get("original"), registro.get("timestamp", "")
                if not original:
                    continue
                yield Referencia(
                    fonte=self.id,
                    id_na_fonte=original,
                    url=f"{ARQUIVO}/{momento}id_/{original}",
                    titulo=original,
                    publicado_em=_data(momento),
                    dados={"original": original, "timestamp": momento},
                )
            if not retomar:
                return

    def baixar(self, ref: Referencia) -> Documento:
        # A manchete vem da página: o "título" da referência é só a URL.
        return documento_html(ref, self.cliente.requisitar(ref.url))

    def sentinela(self, doc: Documento) -> bool:
        return pagina_integra(doc, self.minimo_caracteres, MARCAS_DO_WAYBACK)
