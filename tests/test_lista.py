from datetime import date

import pytest

from argos import fontes
from argos.fontes.lista import ler_tabela

URL = "https://tribunal.exemplo.br/sumulas"


def _lista(rede, **cfg):
    base = {"tipo": "lista", "id": "stf:sumulas", "url": URL, "tabela": 1}
    return fontes.construir(
        {**base, "coluna_id": "Número", "coluna_destaque": "Enunciado", **cfg}, rede
    )


def test_le_a_tabela_pelo_cabecalho(fixtures):
    html = (fixtures / "lista" / "sumulas.html").read_text(encoding="utf-8")
    linhas = ler_tabela(html, 1)
    assert list(linhas[0]) == ["Número", "Enunciado", "Situação"]
    assert linhas[1]["Enunciado"].startswith("É inconstitucional")
    assert "regime\nem crime" in linhas[1]["Enunciado"]
    assert ler_tabela(html, 0)[0] == {"1": "Início", "2": "Busca"}  # sem cabeçalho: posição
    with pytest.raises(ValueError, match="2 tabela"):
        ler_tabela(html, 5)


def test_id_muda_quando_a_linha_muda(rede, fixtures):
    html = (fixtures / "lista" / "sumulas.html").read_text(encoding="utf-8")
    rede.responder(URL, html)
    rede.responder(
        URL,
        html.replace("Vigente</td></tr>\n    <tr><td>902", "Cancelada</td></tr>\n    <tr><td>902"),
    )
    fonte = _lista(rede)
    antes = {r.id_na_fonte.split("@")[0]: r.id_na_fonte for r in fonte.listar(date.today())}
    depois = {r.id_na_fonte.split("@")[0]: r.id_na_fonte for r in fonte.listar(date.today())}
    assert set(antes) == {"901", "902", "903"}  # a linha sem número fica de fora
    assert antes["901"] != depois["901"]  # situação mudou: item novo
    assert antes["902"] == depois["902"]  # igual: o estado não relê


def test_baixa_sem_rede_com_destaque_e_sentinela(rede, fixtures):
    rede.responder(URL, fixtures / "lista" / "sumulas.html")
    fonte = _lista(rede)
    s901, s902, s903 = list(fonte.listar(date.today()))
    rede.pedidos.clear()
    doc = fonte.baixar(s901)
    assert rede.pedidos == []
    assert doc.texto.startswith("Número: 901\nEnunciado: Não se tipifica")
    assert doc.destaques["enunciado"] in doc.texto
    assert s901.url == f"{URL}#901"
    assert fonte.sentinela(doc)
    assert not fonte.sentinela(fonte.baixar(s903))  # só o número, sem conteúdo
