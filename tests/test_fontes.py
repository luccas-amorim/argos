import json
from datetime import date

import pytest

from argos import fontes
from argos.contrato import Fonte, Referencia
from argos.fontes.datajud import DataJud, converter_data
from argos.fontes.rss import Rss, ler_feed

FEED = "https://tribunal.exemplo.jus.br/rss"


def _rss(rede, **cfg):
    return fontes.construir({"tipo": "rss", "id": "rss:tribunal", "url": FEED, **cfg}, rede)


def test_adaptadores_cumprem_o_contrato():
    for classe in fontes.TIPOS.values():
        for nome in ("listar", "baixar", "sentinela", "de_config"):
            assert callable(getattr(classe, nome))
        assert isinstance(classe.respeita_robots, bool)
    assert isinstance(Rss("x", FEED, cliente=None), Fonte)


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="desconhecido"):
        fontes.construir({"tipo": "gopher", "id": "x"})


def test_rss_e_atom(fixtures):
    refs = list(ler_feed((fixtures / "rss" / "feed.xml").read_bytes(), "rss:j"))
    assert [r.id_na_fonte for r in refs] == [
        "noticia-1001",
        "noticia-1002",
        "noticia-1003",
        "noticia-0900",
    ]
    assert refs[0].publicado_em == date(2026, 10, 2)
    atom = list(ler_feed((fixtures / "rss" / "atom.xml").read_bytes(), "rss:r"))
    assert len(atom) == 1  # a entrada sem link é ignorada
    assert atom[0].url == "https://repositorio.exemplo.br/handle/123/456"
    assert atom[0].publicado_em == date(2026, 9, 30)


def test_rss_lista_desde_a_data(rede, fixtures):
    rede.responder(FEED, fixtures / "rss" / "feed.xml")
    refs = list(_rss(rede).listar(date(2026, 9, 1)))
    assert "noticia-0900" not in [r.id_na_fonte for r in refs]
    assert len(refs) == 3


def test_rss_baixa_a_pagina_e_nao_o_resumo(rede, fixtures):
    url = "https://tribunal.exemplo.jus.br/noticias/2026/10/tese-furto-qualificado"
    rede.responder(url, fixtures / "rss" / "noticia-tese.html")
    fonte = _rss(rede)
    ref = Referencia(
        "rss:tribunal",
        "noticia-1001",
        url,
        "Terceira Seção fixa tese sobre furto qualificado em recurso repetitivo",
    )
    doc = fonte.baixar(ref)
    assert "art. 155, § 4º, I, do Código Penal" in doc.texto
    assert "Resumo curto" not in doc.texto
    assert doc.destaques["manchete"] == ref.titulo
    assert doc.destaques["linha_fina"].startswith("Tema 9.999")
    assert len(doc.hash_texto) == 64
    assert fonte.sentinela(doc)


def test_rss_sentinela_reprova_pagina_de_erro_com_200(rede, fixtures):
    url = "https://tribunal.exemplo.jus.br/noticias/2026/10/sumiu"
    rede.responder(url, fixtures / "rss" / "erro-200.html")
    fonte = _rss(rede, minimo_caracteres=50)
    doc = fonte.baixar(Referencia("rss:tribunal", "noticia-1003", url))
    assert not fonte.sentinela(doc)


def test_rss_sentinela_reprova_texto_curto(rede, fixtures):
    url = "https://tribunal.exemplo.jus.br/noticias/2026/10/sumiu"
    rede.responder(url, "<p>Código Penal</p>")
    fonte = _rss(rede)
    assert not fonte.sentinela(fonte.baixar(Referencia("rss:tribunal", "x", url)))


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("20190528000000", date(2019, 5, 28)),
        ("2019-05-28T00:00:00.000Z", date(2019, 5, 28)),
        ("2019-05-28", date(2019, 5, 28)),
        ("lixo", None),
        (None, None),
    ],
)
def test_datajud_datas(valor, esperado):
    assert converter_data(valor) == esperado


def _datajud(rede, **cfg):
    base = {"tipo": "datajud", "id": "datajud:stj", "tribunal": "STJ", "tamanho_pagina": 2}
    return fontes.construir({**base, **cfg}, rede)


def test_datajud_pagina_com_search_after(rede, fixtures):
    url = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
    pagina = json.loads((fixtures / "datajud" / "pagina1.json").read_text(encoding="utf-8"))
    rede.responder(url, json.dumps(pagina))
    rede.responder(url, json.dumps({"hits": {"hits": []}}))
    consulta = {"match": {"assuntos.codigo": 3372}}
    fonte = _datajud(rede, consulta=consulta)
    refs = list(fonte.listar(date(2026, 9, 28)))
    assert [r.id_na_fonte for r in refs] == [
        "STJ_REsp_00012345620248260000@2026-09-29T10:15:00.000Z",
        "STJ_HC_00099999920268260000@2026-09-30T08:00:00.000Z",
    ]
    primeira, segunda = (json.loads(p.corpo) for p in rede.pedidos)
    assert primeira["query"]["bool"]["must"][0] == consulta
    assert primeira["query"]["bool"]["must"][1]["range"]["dataHoraUltimaAtualizacao"] == {
        "gte": "2026-09-28"
    }
    assert "search_after" not in primeira
    assert segunda["search_after"] == [1727683200000]
    assert rede.pedidos[0].cabecalhos["Authorization"].startswith("APIKey ")
    assert "robots.txt" not in " ".join(rede.urls())


def test_datajud_ficha_e_sentinela(rede, fixtures):
    url = "https://api-publica.datajud.cnj.jus.br/api_publica_stj/_search"
    rede.responder(url, fixtures / "datajud" / "pagina1.json")
    fonte = _datajud(rede, tamanho_pagina=100)
    publico, sigiloso = list(fonte.listar(date(2026, 9, 1)))
    doc = fonte.baixar(publico)
    assert "Classe: Recurso Especial (1032)" in doc.texto
    assert "Homicídio Qualificado (3372); Tribunal do Júri (10949)" in doc.destaques["assuntos"]
    assert "2026-09-28 Provimento (237) [tipo_de_documento: Acórdão]" in doc.texto
    assert fonte.sentinela(doc)
    assert not fonte.sentinela(fonte.baixar(sigiloso))
    assert isinstance(fonte, DataJud)


def test_datajud_resposta_real_do_stm(rede, fixtures):
    """Gravada em 04/10/2026: consulta do próprio adaptador, desde 14/09, página de 2."""
    url = "https://api-publica.datajud.cnj.jus.br/api_publica_stm/_search"
    rede.responder(url, fixtures / "datajud" / "stm-real-2026-10-04.json")
    rede.responder(url, json.dumps({"hits": {"hits": []}}))
    cfg = {"tipo": "datajud", "id": "datajud:stm", "tribunal": "stm", "tamanho_pagina": 2}
    fonte = fontes.construir(cfg, rede)
    refs = list(fonte.listar(date(2026, 9, 14)))
    assert [r.id_na_fonte.split("@")[0] for r in refs] == [
        "STM_G1_70001647020267120012",
        "STM_G1_70001638520267120012",
    ]
    assert refs[0].publicado_em == date(2026, 9, 14)
    assert json.loads(rede.pedidos[1].corpo)["search_after"] == [1789417709971]
    doc = fonte.baixar(refs[1])
    assert fonte.sentinela(doc)
    assert doc.destaques["assuntos"] == "Corrupção passiva (11353)"
    assert "Classe: Ação Penal Militar - Procedimento Ordinário (11037)" in doc.texto
    assert "Expedição de documento (60) [tipo_de_documento: Mandado]" in doc.texto
    assert fonte.margem_dias == 30
    assert fonte.cliente.tempo_limite == 180
