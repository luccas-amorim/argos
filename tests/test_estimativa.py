import json

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
        ("wayback:j", "https://web.archive.org/web/1999id_/http://j.br/2", 2),
        ("wayback:j", "https://web.archive.org/web/1999id_/http://j.br/ruido", 1),
    ])  # fmt: skip
    _rodada(saidas, "20261008T000000Z", [
        ("gdelt:c", "https://www.j.br/1", 3),
        ("gdelt:c", "https://k.br/9", 2),
        ("openalex:c", "https://doi.org/10.1/x", 3),
        ("openalex:c", "https://k.br/9", 3),
    ])  # fmt: skip
    (saidas / "20261009T000000Z-retriar").mkdir()  # retriagem não é rodada de descoberta

    est = estimativa.calcular(saidas)
    assert est.por_canal["wayback:j"] == {"j.br/1", "j.br/2"}  # o nível 1 fica de fora
    assert len(est.observadas) == 4
    assert est.frequencias == {1: 2, 2: 2}
    assert est.chao == 4 + 2 * 2 / (2 * 2)
    assert est.curva == [("20261001T000000Z", 2, 2), ("20261008T000000Z", 2, 4)]
    texto = estimativa.relatorio(est)
    assert "URLs distintas observadas: **4**" in texto
    assert "`gdelt:c` × `wayback:j` | 2 | 2 | 1 |" in texto


def test_um_canal_so_nao_estima(tmp_path):
    _rodada(tmp_path / "saidas", "20261001T000000Z", [("a", "https://x.br/1", 3)])
    est = estimativa.calcular(tmp_path / "saidas")
    assert est.chao is None
    assert "ao menos dois" in estimativa.relatorio(est)


def test_cli_estimar(cfg, capsys):
    assert cli.main(["estimar", "--config", str(cfg)]) == 0
    assert "0 URLs observadas" in capsys.readouterr().out
    assert (cfg.parent / "dados" / "estimativa.md").exists()
