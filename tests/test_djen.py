import json
from datetime import date

import pytest

from argos import fontes, lexico, rodada
from argos.fontes.djen import URL, extrair_ementa
from argos.triagem import triar

DIA = date(2026, 10, 1)


@pytest.fixture
def pagina(fixtures):
    return (fixtures / "djen" / "stj-2026-10-01.json").read_text(encoding="utf-8")


def _djen(rede, hoje=date(2026, 10, 2), **cfg):
    base = {"tipo": "djen", "id": "djen:stj", "tribunal": "stj"}
    fonte = fontes.construir({**base, **cfg}, rede)
    fonte.hoje = lambda: hoje
    return fonte


def test_lista_dia_a_dia_filtra_tipo_e_descarta_pessoas(rede, pagina):
    rede.responder(URL, pagina)
    rede.responder(URL, json.dumps({"items": []}))
    fonte = _djen(rede, tipos_documento=["Acordao", "Decisão"])
    refs = list(fonte.listar(DIA))

    assert [r.id_na_fonte for r in refs] == ["9001", "9003"]  # o despacho fica de fora
    assert refs[0].publicado_em == DIA
    assert refs[0].titulo == "Acórdão 0001234-56.2025.3.00.0000"
    assert refs[0].url.startswith(f"{URL}?siglaTribunal=STJ&dataDisponibilizacaoInicio=2026-10-01")
    assert refs[0].url.endswith("#9001")
    for ref in refs:
        assert "destinatarios" not in ref.dados and "destinatarioadvogados" not in ref.dados
        assert "FULANO" not in json.dumps(ref.dados, ensure_ascii=False)

    dias = [p.url.split("dataDisponibilizacaoInicio=")[1][:10] for p in rede.pedidos]
    assert dias == ["2026-10-01", "2026-10-02"]
    assert "siglaTribunal=STJ" in rede.pedidos[0].url
    assert "robots.txt" not in " ".join(rede.urls())


def test_pagina_cheia_pede_a_seguinte(rede, pagina):
    rede.responder(URL, pagina)
    rede.responder(URL, json.dumps({"items": []}))
    list(_djen(rede, hoje=DIA, itens_por_pagina=3, texto="Código Penal").listar(DIA))
    assert ["pagina=1" in rede.pedidos[0].url, "pagina=2" in rede.pedidos[1].url] == [True, True]
    assert "texto=C%C3%B3digo+Penal" in rede.pedidos[0].url


def test_baixa_sem_rede_com_a_ementa_em_destaque(rede, pagina):
    rede.responder(URL, pagina)
    fonte = _djen(rede, hoje=DIA)
    acordao, despacho, decisao = list(fonte.listar(DIA))
    rede.pedidos.clear()

    doc = fonte.baixar(acordao)
    assert rede.pedidos == []
    assert "<p>" not in doc.texto
    assert doc.destaques["ementa"].startswith("PENAL E PROCESSUAL PENAL. RECURSO ESPECIAL.")
    assert "Vistos, relatados" not in doc.destaques["ementa"]
    assert doc.destaques["ementa"] in doc.texto
    assert fonte.sentinela(doc)

    assert "ementa" not in fonte.baixar(decisao).destaques
    assert not fonte.sentinela(fonte.baixar(despacho))  # curto demais para ser decisão


def test_triagem_do_acordao_pela_ementa(rede, pagina, fixtures):
    rede.responder(URL, pagina)
    fonte = _djen(rede, hoje=DIA)
    acordao = next(iter(fonte.listar(DIA)))
    raiz = fixtures.parents[1]
    casador = lexico.Casador(lexico.carregar(raiz / "exemplos" / "lexico.exemplo.json"))
    resultado = triar(fonte.baixar(acordao), casador)
    assert (resultado.nivel, resultado.onde, resultado.chaves) == (3, "ementa", ["cp-art-121"])


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Ementa: PENAL. Furto.\nVoto\nO relator...", "PENAL. Furto."),
        ("EMENTA – HABEAS CORPUS.\nACÓRDÃO\n", "HABEAS CORPUS."),
        ("Sem a palavra que abre o resumo.", None),
    ],
)
def test_extrair_ementa(texto, esperado):
    assert extrair_ementa(texto) == esperado


def test_bloqueio_por_pais_aparece_como_falha_da_fonte(rede, tmp_path):
    corpo = "The Amazon CloudFront distribution is configured to block access from your country."
    rede.responder(URL, corpo, status=403)
    fonte = _djen(rede, hoje=DIA)
    lex = lexico.de_dados({"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["a"]}]})
    from argos.config import Config

    cfg = Config(lexico=tmp_path / "l.json", diretorio=tmp_path, fontes=())
    r = rodada.rodar(cfg, [fonte], lexico.Casador(lex), desde=DIA, hoje=DIA)
    assert r.codigo_saida == rodada.ERRO
    assert r.falhas_de_fonte["djen:stj"].startswith("listagem: BloqueadoPorPais")
