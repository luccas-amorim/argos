import json
from datetime import date

import pytest

from argos import cli, estimativa
from argos.estimativa import Par, normalizar_url


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://www.Jornal.br/a/b/", "jornal.br/a/b"),
        ("http://jornal.br/a/b?utm_source=x&id=3", "jornal.br/a/b?id=3"),
        ("https://web.archive.org/web/20021002080000id_/http://www.jornal.br/a/b", "jornal.br/a/b"),
        ("https://web.archive.org/web/2002/https://jornal.br/a/b", "jornal.br/a/b"),
        ("jornal.br", "jornal.br/"),
    ],
)
def test_normalizar_url(url, esperado):
    assert normalizar_url(url) == esperado


def test_chapman_com_numeros_conhecidos():
    # n1 = 100, n2 = 80, em comum 40: Lincoln-Petersen daria 200; Chapman, 199,4.
    par = Par("a", "b", 100, 80, 40)
    assert par.chapman == pytest.approx(101 * 81 / 41 - 1)
    baixo, alto = par.intervalo
    assert 140 <= baixo < par.chapman < alto


def _rodada(saidas, nome, itens):
    pasta = saidas / f"{nome}-rodar"
    pasta.mkdir(parents=True)
    linhas = [
        json.dumps({"fonte": f, "url": u, "situacao": "triado", "nivel": n}) for f, u, n in itens
    ]
    (pasta / "itens.jsonl").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def test_calcular_canais_chao_e_curva(tmp_path):
    saidas = tmp_path / "saidas"
    _rodada(saidas, "20261001T000000Z", [
        ("wayback:j", "https://web.archive.org/web/1999id_/http://j.br/1", 3),
        ("wayback:k", "https://web.archive.org/web/1999id_/http://k.br/2", 2),
        ("wayback:j", "https://web.archive.org/web/1999id_/http://j.br/ruido", 1),
    ])  # fmt: skip
    _rodada(saidas, "20261008T000000Z", [
        ("gdelt:c", "https://www.j.br/1", 3),
        ("gdelt:c", "https://k.br/9", 2),
        ("rss:jornal", "https://k.br/9", 3),
        ("openalex:c", "https://doi.org/10.1/x", 3),
    ])  # fmt: skip
    (saidas / "20261009T000000Z-retriar").mkdir()  # retriagem não é rodada de descoberta

    estrato = {"openalex:c": "academico"}
    por_estrato = estimativa.calcular(saidas, estrato_de=lambda f: estrato.get(f, "imprensa"))
    imprensa, academico = por_estrato["imprensa"], por_estrato["academico"]

    # Dois domínios do Wayback são um canal só; o nível 1 fica de fora.
    assert imprensa.por_canal["wayback"] == {"j.br/1", "k.br/2"}
    assert set(imprensa.por_canal) == {"wayback", "gdelt", "rss"}
    assert len(imprensa.observadas) == 3
    assert imprensa.frequencias == {2: 2, 1: 1}
    assert imprensa.chao == 3 + 1 * 1 / (2 * 2)
    assert imprensa.curva == [("20261001T000000Z", 2, 2), ("20261008T000000Z", 1, 3)]
    assert academico.chao is None  # um canal só no estrato: sem estimativa

    texto = estimativa.relatorio(por_estrato)
    assert "## Estrato `imprensa`" in texto and "## Estrato `academico`" in texto
    assert "`gdelt` × `wayback` | 2 | 2 | 1 |" in texto


def test_desde_alinha_no_tempo(tmp_path):
    saidas = tmp_path / "saidas"
    pasta = saidas / "20261001T000000Z-rodar"
    pasta.mkdir(parents=True)
    itens = [
        {"fonte": "wayback:j", "url": "https://j.br/velha", "situacao": "triado", "nivel": 3,
         "publicado_em": "2002-10-02"},
        {"fonte": "wayback:j", "url": "https://j.br/nova", "situacao": "triado", "nivel": 3,
         "publicado_em": "2026-09-30"},
    ]  # fmt: skip
    (pasta / "itens.jsonl").write_text("\n".join(json.dumps(i) for i in itens))
    (est,) = estimativa.calcular(saidas, desde=date(2026, 7, 1)).values()
    assert est.observadas == {"j.br/nova"}


def test_um_canal_so_nao_estima(tmp_path):
    _rodada(tmp_path / "saidas", "20261001T000000Z", [("a", "https://x.br/1", 3)])
    por_estrato = estimativa.calcular(tmp_path / "saidas")
    assert por_estrato["geral"].chao is None
    assert "ao menos dois" in estimativa.relatorio(por_estrato)


def test_cli_estimar(cfg, capsys):
    assert cli.main(["estimar", "--config", str(cfg)]) == 0
    assert "relatório em" in capsys.readouterr().out
    assert (cfg.parent / "dados" / "estimativa.md").exists()
