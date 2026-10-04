"""Cliente HTTP educado: identifica o projeto, obedece o limite da fonte e o robots.txt.

O limite é o que o adaptador declara (`limite_por_minuto`), não um número que o motor
negocia. O transporte é injetável: os testes trocam a rede por fixtures gravadas.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable
from dataclasses import dataclass, field

from argos import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"Argos/{__version__} (+https://github.com/luccas-amorim/argos)"
RETENTAVEIS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Requisicao:
    metodo: str
    url: str
    corpo: bytes | None = None
    cabecalhos: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Resposta:
    status: int
    url: str
    corpo: bytes
    cabecalhos: dict[str, str] = field(default_factory=dict)

    def json(self):
        return json.loads(self.corpo.decode("utf-8"))


Transporte = Callable[[Requisicao, float], Resposta]


class ErroColeta(RuntimeError):
    """Falha de rede ou de HTTP depois de esgotadas as tentativas."""


class BloqueadoPorRobots(ErroColeta):
    """O robots.txt da origem não autoriza o caminho. Não é falha: é política."""


def transporte_urllib(req: Requisicao, tempo_limite: float) -> Resposta:
    pedido = urllib.request.Request(
        req.url, data=req.corpo, headers=req.cabecalhos, method=req.metodo
    )
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as r:
            return Resposta(
                r.status, r.geturl(), r.read(), {k.lower(): v for k, v in r.headers.items()}
            )
    except urllib.error.HTTPError as erro:
        cabecalhos = {k.lower(): v for k, v in (erro.headers or {}).items()}
        return Resposta(erro.code, req.url, erro.read() or b"", cabecalhos)


class Cliente:
    def __init__(
        self,
        limite_por_minuto: int,
        *,
        respeita_robots: bool = True,
        transporte: Transporte = transporte_urllib,
        cabecalhos: dict[str, str] | None = None,
        tentativas: int = 4,
        tempo_limite: float = 60.0,
        dormir: Callable[[float], None] | None = None,
        relogio: Callable[[], float] | None = None,
    ) -> None:
        if limite_por_minuto <= 0:
            raise ValueError("limite_por_minuto precisa ser positivo")
        self.intervalo = 60.0 / limite_por_minuto
        self.respeita_robots = respeita_robots
        self.transporte = transporte
        self.cabecalhos = {"User-Agent": USER_AGENT, **(cabecalhos or {})}
        self.tentativas = tentativas
        self.tempo_limite = tempo_limite
        # Resolvidos na chamada, e não na definição, para que os testes troquem o relógio.
        self._dormir = dormir or (lambda segundos: time.sleep(segundos))
        self._relogio = relogio or (lambda: time.monotonic())
        self._ultima: float | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _aguardar(self) -> None:
        if self._ultima is not None:
            espera = self.intervalo - (self._relogio() - self._ultima)
            if espera > 0:
                self._dormir(espera)
        self._ultima = self._relogio()

    def _permitido(self, url: str) -> bool:
        partes = urllib.parse.urlsplit(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        if origem not in self._robots:
            # Falha de rede aqui sobe como ErroColeta e não fica em cache: a próxima
            # requisição à mesma origem tenta ler o robots.txt de novo.
            self._robots[origem] = self._ler_robots(origem)
        regras = self._robots[origem]
        return regras is None or regras.can_fetch(self.cabecalhos["User-Agent"], url)

    def _ler_robots(self, origem: str) -> urllib.robotparser.RobotFileParser | None:
        """None quando não há robots.txt (404 e afins): a convenção é tudo permitido."""
        resposta = self._enviar(
            Requisicao("GET", f"{origem}/robots.txt", cabecalhos=dict(self.cabecalhos))
        )
        regras = urllib.robotparser.RobotFileParser()
        if resposta.status in (401, 403):
            # Convenção do robotparser: origem que nega o robots.txt nega tudo.
            regras.disallow_all = True
            return regras
        if resposta.status >= 400:
            return None
        regras.parse(resposta.corpo.decode("utf-8", errors="replace").splitlines())
        return regras

    def _enviar(self, req: Requisicao) -> Resposta:
        ultimo: str = ""
        for tentativa in range(self.tentativas):
            self._aguardar()
            try:
                resposta = self.transporte(req, self.tempo_limite)
            except (OSError, urllib.error.URLError) as erro:
                ultimo = str(erro)
            else:
                if resposta.status not in RETENTAVEIS:
                    return resposta
                ultimo = f"HTTP {resposta.status}"
            pausa = min(60.0, 2.0 ** (tentativa + 1))
            log.warning(
                "%s %s falhou (%s); nova tentativa em %ss", req.metodo, req.url, ultimo, pausa
            )
            self._dormir(pausa)
        raise ErroColeta(
            f"{req.metodo} {req.url} falhou após {self.tentativas} tentativas: {ultimo}"
        )

    def requisitar(
        self,
        url: str,
        *,
        metodo: str = "GET",
        params: dict | None = None,
        json_corpo: dict | None = None,
        cabecalhos: dict[str, str] | None = None,
    ) -> Resposta:
        """Faz a requisição e devolve a resposta 2xx. Qualquer outro status é ErroColeta."""
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        if self.respeita_robots and not self._permitido(url):
            raise BloqueadoPorRobots(f"robots.txt não autoriza {url}")
        todos = {**self.cabecalhos, **(cabecalhos or {})}
        corpo = None
        if json_corpo is not None:
            corpo = json.dumps(json_corpo, ensure_ascii=False).encode("utf-8")
            todos.setdefault("Content-Type", "application/json")
        resposta = self._enviar(Requisicao(metodo, url, corpo, todos))
        if not 200 <= resposta.status < 300:
            trecho = resposta.corpo[:300].decode("utf-8", errors="replace")
            raise ErroColeta(f"{metodo} {url} -> HTTP {resposta.status}: {trecho}")
        return resposta
