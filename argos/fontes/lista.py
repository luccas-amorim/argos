"""Tabela que muda devagar: teses de repercussão geral, súmulas, listas de temas.

A página é uma tabela HTML. Cada linha é um item; o id do item é o valor da coluna-chave
(o número do tema, da súmula) mais o hash do conteúdo da linha. Assim, a linha que
**muda** (tese reescrita, súmula com nova redação) ganha id novo e volta a ser lida,
como o processo que ganhou movimento no `datajud`. Linha igual à da rodada anterior não
é relida: o estado já a conhece.

Limite conhecido: a linha que **some** (súmula cancelada e retirada da lista) não gera
item, porque o contrato só sabe listar o que existe. Por ora, quem precisa disso compara
as listas de duas rodadas; o motor pode ganhar esse aviso numa versão seguinte.

Configuração:
    {"tipo": "lista", "id": "stf:sumulas-vinculantes", "url": "https://...",
     "tabela": 0, "coluna_id": "Número", "coluna_destaque": "Enunciado",
     "limite_por_minuto": 10}

`tabela` é o índice da tabela na página (a primeira é 0). As colunas são nomeadas pelo
cabeçalho; sem cabeçalho, por posição ("1", "2", ...).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import date
from html.parser import HTMLParser

from argos.captura import montar_documento
from argos.contrato import Documento, Referencia
from argos.http import Cliente, Transporte, transporte_urllib
from argos.texto import decodificar, normalizar


class _Tabelas(HTMLParser):
    """Todas as tabelas da página, como listas de linhas de células (texto)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tabelas: list[list[list[str]]] = []
        self.cabecalhos: list[list[bool]] = []  # por tabela: a linha é só de <th>?
        self._pilha: list[list[list[str]]] = []
        self._linha: list[str] | None = None
        self._so_th = True
        self._celula: list[str] | None = None
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorando += 1
        elif tag == "table":
            self._pilha.append([])
            self.cabecalhos.append([])
            self.tabelas.append(self._pilha[-1])
        elif tag == "tr" and self._pilha:
            self._linha, self._so_th = [], True
        elif tag in ("td", "th") and self._linha is not None:
            self._celula = []
            self._so_th = self._so_th and tag == "th"
        elif tag == "br" and self._celula is not None:
            self._celula.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._ignorando:
            self._ignorando -= 1
        elif tag in ("td", "th") and self._celula is not None and self._linha is not None:
            self._linha.append(normalizar("".join(self._celula)))
            self._celula = None
        elif tag == "tr" and self._linha is not None and self._pilha:
            if any(self._linha):
                self._pilha[-1].append(self._linha)
                indice = self.tabelas.index(self._pilha[-1])
                self.cabecalhos[indice].append(self._so_th)
            self._linha = None
        elif tag == "table" and self._pilha:
            self._pilha.pop()

    def handle_data(self, dado):
        if self._celula is not None and not self._ignorando:
            self._celula.append(dado)


def ler_tabela(html: str, indice: int = 0) -> list[dict[str, str]]:
    """Linhas da tabela `indice` como dicionários coluna -> valor."""
    leitor = _Tabelas()
    leitor.feed(html)
    leitor.close()
    if indice >= len(leitor.tabelas):
        raise ValueError(
            f"a página tem {len(leitor.tabelas)} tabela(s); pedida a de índice {indice}"
        )
    linhas, so_th = leitor.tabelas[indice], leitor.cabecalhos[indice]
    if not linhas:
        raise ValueError(f"a tabela {indice} está vazia")
    if so_th[0]:
        nomes, corpo = linhas[0], linhas[1:]
    else:
        nomes, corpo = [str(i + 1) for i in range(max(map(len, linhas)))], linhas
    return [dict(zip(nomes, linha, strict=False)) for linha in corpo]


class Lista:
    respeita_robots = True

    def __init__(
        self,
        id: str,
        url: str,
        cliente: Cliente,
        tabela: int = 0,
        coluna_id: str = "1",
        coluna_destaque: str | None = None,
        limite_por_minuto: int = 10,
    ) -> None:
        self.id = id
        self.url = url
        self.cliente = cliente
        self.tabela = tabela
        self.coluna_id = coluna_id
        self.coluna_destaque = coluna_destaque
        self.limite_por_minuto = limite_por_minuto

    @classmethod
    def de_config(cls, cfg: dict, transporte: Transporte = transporte_urllib) -> Lista:
        limite = int(cfg.get("limite_por_minuto", 10))
        cliente = Cliente(limite, respeita_robots=cls.respeita_robots, transporte=transporte)
        return cls(
            cfg["id"],
            cfg["url"],
            cliente,
            int(cfg.get("tabela", 0)),
            str(cfg.get("coluna_id", "1")),
            cfg.get("coluna_destaque"),
            limite,
        )

    def listar(self, desde: date) -> Iterator[Referencia]:
        """A tabela inteira, toda rodada: `desde` não se aplica a um retrato."""
        resposta = self.cliente.requisitar(self.url)
        html, _ = decodificar(resposta.corpo, resposta.cabecalhos.get("content-type"))
        for linha in ler_tabela(html, self.tabela):
            chave = linha.get(self.coluna_id, "").strip()
            if not chave:
                continue
            conteudo = "\n".join(f"{k}: {v}" for k, v in linha.items())
            impressao = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()[:12]
            yield Referencia(
                fonte=self.id,
                id_na_fonte=f"{chave}@{impressao}",
                url=f"{self.url}#{chave}",
                titulo=f"{self.coluna_id} {chave}",
                dados=linha,
            )

    def baixar(self, ref: Referencia) -> Documento:
        """Sem rede: a linha veio inteira na listagem."""
        linha = dict(ref.dados or {})
        texto = "\n".join(f"{k}: {v}" for k, v in linha.items())
        destaques = {}
        if self.coluna_destaque and linha.get(self.coluna_destaque):
            destaques[self.coluna_destaque.lower()] = linha[self.coluna_destaque]
        return montar_documento(ref, texto, destaques=destaques)

    def sentinela(self, doc: Documento) -> bool:
        linha = doc.ref.dados or {}
        preenchidas = [v for v in linha.values() if v.strip()]
        return len(preenchidas) >= 2
