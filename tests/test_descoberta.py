"""Canais de descoberta do observatório: wayback, openalex, gdelt."""

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

from argos import fontes
from argos.fontes import gdelt, openalex, wayback


def _query(url):
    return parse_qs(urlsplit(url).query)


# --- wayback -----------------------------------------------------------------------


def _wayback(rede):
    cfg = {"tipo": "wayback", "id": "wayback:jornal", "dominio": "jornal.exemplo.br"}
    return fontes.construir(cfg, rede)


def test_wayback_pagina_pelo_resume_key(rede, fixtures):
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p1.json")
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    refs = list(_wayback(rede).listar(date(1996, 1, 1)))

    assert len(refs) == 3
    primeira = refs[0]
    assert (
        primeira.id_na_fonte
        == "http://www1.jornal.exemplo.br/fsp/cotidian/carandiru-ff02109912.htm"
    )
    assert primeira.url == f"{wayback.ARQUIVO}/19990301120000id_/{primeira.id_na_fonte}"
    assert primeira.publicado_em == date(1999, 3, 1)  # data da captura

    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["filter"] == ["original:(?i).*carandiru.*", "statuscode:200", "mimetype:text/html"]
    assert q1["matchType"] == ["domain"] and q1["collapse"] == ["urlkey"]
    assert q1["from"] == ["19960101"]
    assert "resumeKey" not in q1
    assert q2["resumeKey"] == ["br,exemplo,jornal)/carandiru-10-anos.shtml 20021002080000"]
    assert "robots.txt" not in " ".join(rede.urls())


def test_wayback_baixa_a_copia_e_reprova_nao_arquivada(rede, fixtures):
    fonte = _wayback(rede)
    rede.responder(wayback.CDX, fixtures / "wayback" / "cdx-p2.json")
    (ref,) = list(fonte.listar(date(1996, 1, 1)))
    rede.responder(ref.url, fixtures / "wayback" / "captura.html")
    doc = fonte.baixar(ref)
    assert doc.destaques["manchete"] == "Carandiru, dez anos depois"
    assert "Pavilhão 9" in doc.texto
    assert fonte.sentinela(doc)

    rede.rotas[ref.url] = []
    rede.responder(ref.url, fixtures / "wayback" / "nao-arquivada.html")
    fonte.minimo_caracteres = 10
    assert not fonte.sentinela(fonte.baixar(ref))


# --- openalex ----------------------------------------------------------------------


def test_openalex_cursor_resumo_e_chave(rede, fixtures, monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", "chave-de-teste")
    rede.responder(openalex.URL, fixtures / "openalex" / "p1.json")
    rede.responder(openalex.URL, fixtures / "openalex" / "p2.json")
    cfg = {"tipo": "openalex", "id": "openalex:carandiru", "busca": "carandiru"}
    fonte = fontes.construir(cfg, rede)
    artigo, dissertacao = list(fonte.listar(date(2026, 1, 1)))

    q1, q2 = (_query(p.url) for p in rede.pedidos)
    assert q1["cursor"] == ["*"] and q2["cursor"] == ["Ij1hYmMi"]
    assert q1["filter"] == ["from_publication_date:2026-01-01"]
    assert q1["api_key"] == ["chave-de-teste"]
    assert not any("mailto" in p.url for p in rede.pedidos)

    assert artigo.url == "https://doi.org/10.0000/exemplo.1"
    assert dissertacao.url == "https://repositorio.exemplo.br/handle/1"  # sem DOI
    doc = fonte.baixar(artigo)
    assert "Este artigo analisa a memória do massacre de 1992." in doc.texto
    assert doc.destaques["titulo"].startswith("Memória e violência de Estado")
    assert fonte.sentinela(doc)


def test_resumo_invertido_vazio():
    assert openalex.resumo(None) == ""
    assert openalex.resumo({"b": [1], "a": [0, 2]}) == "a b a"


# --- gdelt -------------------------------------------------------------------------


def test_gdelt_um_dia_por_vez_dentro_da_janela(rede, fixtures):
    rede.responder(gdelt.URL, fixtures / "gdelt" / "dia.json")
    cfg = {"tipo": "gdelt", "id": "gdelt:carandiru", "busca": "carandiru"}
    fonte = fontes.construir(cfg, rede)
    fonte.hoje = lambda: date(2026, 10, 4)
    refs = list(fonte.listar(date(2020, 1, 1)))  # anterior à janela: cortado

    consultas = [_query(p.url) for p in rede.pedidos if p.url.startswith(gdelt.URL)]
    assert len(consultas) == 91  # 90 dias de janela, mais hoje
    assert consultas[0]["startdatetime"] == ["20260706000000"]
    assert consultas[0]["enddatetime"] == ["20260707000000"]
    assert {r.id_na_fonte for r in refs} == {
        "https://noticias.exemplo.com/2026/10/02/carandiru-34-anos",
        "https://news.example.org/brazil-prison-massacre",
    }
    assert refs[0].publicado_em == date(2026, 10, 2)


def test_gdelt_dia_cheio_e_repartido_em_seis_horas(rede):
    cheio = {
        "articles": [
            {"url": f"https://x.br/{i}", "seendate": "20261002T000000Z"} for i in range(250)
        ]
    }
    rede.responder(gdelt.URL, json.dumps(cheio))
    rede.responder(gdelt.URL, json.dumps({"articles": []}))
    cfg = {"tipo": "gdelt", "id": "gdelt:x", "busca": "x"}
    fonte = fontes.construir(cfg, rede)
    fonte.hoje = lambda: date(2026, 10, 2)
    list(fonte.listar(date(2026, 10, 2)))
    api = [p for p in rede.pedidos if p.url.startswith(gdelt.URL)]
    faixas = [_query(p.url)["startdatetime"][0] for p in api][1:]
    assert faixas == ["20261002000000", "20261002060000", "20261002120000", "20261002180000"]
