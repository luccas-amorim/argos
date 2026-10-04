"""Quanto falta: estimativa do total a partir da sobreposição entre canais.

É a técnica de captura e recaptura, a mesma de contar peixes num lago. Se o canal A acha
`n1` páginas, o B acha `n2` e `m` estão nos dois, o total estimado é ~ `n1 · n2 / m`. Aqui
se usa a forma de Chapman, que não explode quando `m` é pequeno, e, para três canais ou
mais, o estimador de Chao, que usa quantas páginas foram vistas por um canal só (`f1`) e
por exatamente dois (`f2`) e é um **piso** robusto à heterogeneidade (página popular é
mais fácil de achar que página obscura).

Duas regras de uso que o código impõe:

- **Canal é o prefixo do id da fonte** (`wayback:folha` e `wayback:estadao` são o mesmo
  canal, `wayback`). Domínios do Wayback não se sobrepõem; tratados como canais
  separados, quase toda URL seria "vista por um canal só" e a estimativa explodiria.
- **Só se comparam canais do mesmo estrato.** Captura e recaptura supõe que os canais
  olham para a mesma população. Imprensa se compara com imprensa, produção acadêmica com
  produção acadêmica. Cada fonte declara `"estrato"` na configuração (padrão: `geral`), e
  o relatório sai por estrato. Para alinhar no tempo (o GDELT só cobre três meses),
  `--desde` restringe a comparação a itens publicados ou capturados a partir da data.

As ressalvas vão no relatório porque são parte do número:

- **Os canais não são independentes.** Todos favorecem o que é popular e bem ligado.
  Dependência positiva faz a estimativa ficar **abaixo** do real: leia como piso.
- **A unidade é a URL normalizada** (sem esquema, sem `www.`, sem barra final, sem
  parâmetros de rastreio, e sem o prefixo do Wayback). A mesma matéria em duas URLs
  conta duas vezes.
- **A curva de acumulação** (quantas URLs novas cada rodada trouxe) diz se a busca está
  saturando, coisa que nenhum estimador diz sozinho.

Entrada: os `itens.jsonl` das rodadas em `<diretorio>/saidas/`, com nível mínimo
configurável (padrão 2: aceitos e pede juízo).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

_WAYBACK = re.compile(r"^https?://web\.archive\.org/web/\d+[a-z_]*/(.+)$")
_RASTREIO = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|amp$)")


def normalizar_url(url: str) -> str:
    url = url.strip()
    if m := _WAYBACK.match(url):
        url = m.group(1)
    if "://" not in url:
        url = f"http://{url}"
    partes = urlsplit(url)
    host = partes.netloc.lower().removeprefix("www.").split(":")[0]
    caminho = partes.path.rstrip("/") or "/"
    consulta = urlencode(
        sorted((k, v) for k, v in parse_qsl(partes.query) if not _RASTREIO.match(k.lower()))
    )
    return f"{host}{caminho}" + (f"?{consulta}" if consulta else "")


@dataclass
class Par:
    a: str
    b: str
    n1: int
    n2: int
    m: int

    @property
    def chapman(self) -> float:
        return (self.n1 + 1) * (self.n2 + 1) / (self.m + 1) - 1

    @property
    def intervalo(self) -> tuple[float, float]:
        n1, n2, m = self.n1, self.n2, self.m
        var = (n1 + 1) * (n2 + 1) * (n1 - m) * (n2 - m) / ((m + 1) ** 2 * (m + 2))
        dp = math.sqrt(var)
        return max(self.n1 + self.n2 - self.m, self.chapman - 1.96 * dp), self.chapman + 1.96 * dp


@dataclass
class Estimativa:
    por_canal: dict[str, set[str]]
    curva: list[tuple[str, int, int]] = field(default_factory=list)  # rodada, novas, total

    @property
    def observadas(self) -> set[str]:
        return set().union(*self.por_canal.values()) if self.por_canal else set()

    @property
    def frequencias(self) -> Counter:
        """Quantas URLs foram vistas por exatamente k canais."""
        contagem = Counter(u for urls in self.por_canal.values() for u in urls)
        return Counter(contagem.values())

    @property
    def chao(self) -> float | None:
        if len(self.por_canal) < 2:
            return None
        s = len(self.observadas)
        f1, f2 = self.frequencias.get(1, 0), self.frequencias.get(2, 0)
        return s + (f1 * f1 / (2 * f2) if f2 else f1 * (f1 - 1) / 2)

    @property
    def pares(self) -> list[Par]:
        return [
            Par(a, b, len(self.por_canal[a]), len(self.por_canal[b]),
                len(self.por_canal[a] & self.por_canal[b]))
            for a, b in combinations(sorted(self.por_canal), 2)
        ]  # fmt: skip


def canal(fonte: str) -> str:
    return fonte.split(":", 1)[0]


def calcular(
    saidas: Path,
    nivel_minimo: int = 2,
    estrato_de: Callable[[str], str] = lambda fonte: "geral",
    desde: date | None = None,
) -> dict[str, Estimativa]:
    """Uma estimativa por estrato. `estrato_de` recebe o id da fonte."""
    por_estrato: dict[str, Estimativa] = {}
    vistas: dict[str, set[str]] = {}
    for pasta in sorted(Path(saidas).glob("*-rodar")):
        arquivo = pasta / "itens.jsonl"
        if not arquivo.exists():
            continue
        antes = {e: len(v) for e, v in vistas.items()}
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            item = json.loads(linha)
            if item.get("situacao") != "triado" or (item.get("nivel") or 0) < nivel_minimo:
                continue
            publicado = item.get("publicado_em")
            if desde and (not publicado or date.fromisoformat(publicado) < desde):
                continue
            estrato = estrato_de(item["fonte"])
            est = por_estrato.setdefault(estrato, Estimativa({}))
            url = normalizar_url(item["url"])
            est.por_canal.setdefault(canal(item["fonte"]), set()).add(url)
            vistas.setdefault(estrato, set()).add(url)
        rodada = pasta.name.removesuffix("-rodar")
        for estrato, urls in vistas.items():
            novas = len(urls) - antes.get(estrato, 0)
            por_estrato[estrato].curva.append((rodada, novas, len(urls)))
    return por_estrato


def relatorio(estratos: dict[str, Estimativa], desde: date | None = None) -> str:
    linhas = ["# Estimativa de cobertura", ""]
    if desde:
        linhas += [f"Só itens publicados ou capturados a partir de {desde.isoformat()}.", ""]
    if not estratos:
        return "\n".join([*linhas, "Nenhuma rodada com itens triados ainda."]) + "\n"
    for nome, est in sorted(estratos.items()):
        linhas += _estrato(nome, est)
    linhas += [
        "",
        "## Como ler",
        "",
        "Os canais não são independentes, e a dependência puxa a estimativa para baixo: os "
        "números acima são piso. Saturação de verdade é a curva achatar com canais novos "
        "entrando, não só com os mesmos canais repetindo.",
    ]
    return "\n".join(linhas) + "\n"


def _estrato(nome: str, est: Estimativa) -> list[str]:
    total = len(est.observadas)
    linhas = [f"## Estrato `{nome}`", "", f"URLs distintas observadas: **{total}**.", ""]

    linhas += ["| Canal | URLs | Só neste canal |", "|---|---|---|"]
    contagem = Counter(u for urls in est.por_canal.values() for u in urls)
    for canal, urls in sorted(est.por_canal.items()):
        exclusivas = sum(1 for u in urls if contagem[u] == 1)
        linhas.append(f"| `{canal}` | {len(urls)} | {exclusivas} |")

    if est.chao is not None:
        f = est.frequencias
        linhas += [
            "",
            "**Total estimado**",
            "",
            f"- **Chao (piso, {len(est.por_canal)} canais):** {est.chao:,.0f} "
            f"(vistas por um canal só: {f.get(1, 0)}; por exatamente dois: {f.get(2, 0)}).",
            f"- **Cobertura:** no máximo {total / est.chao:.0%} (observadas ÷ piso)."
            if est.chao
            else "",
            "",
            "| Par | n1 | n2 | em comum | Chapman | IC 95% |",
            "|---|---|---|---|---|---|",
        ]
        for p in est.pares:
            baixo, alto = p.intervalo
            linhas.append(
                f"| `{p.a}` × `{p.b}` | {p.n1} | {p.n2} | {p.m} | {p.chapman:,.0f} | "
                f"{baixo:,.0f} a {alto:,.0f} |"
            )
        linhas += [
            "",
            "Par sem nada em comum dá estimativa enorme e instável: não diz que o total é "
            "enorme, diz que os dois canais olham para lugares diferentes.",
        ]
    else:
        linhas += ["", "Com um canal só não há estimativa: é preciso ao menos dois."]

    linhas += ["", "**Curva de acumulação**", "", "| Rodada | Novas | Total |", "|---|---|---|"]
    linhas += [f"| {r} | {novas} | {acum} |" for r, novas, acum in est.curva]
    return [*linhas, ""]
