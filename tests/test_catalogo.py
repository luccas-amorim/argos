"""Catálogo CSV: id, url e os identificadores que decidiram buscar o item."""

import csv
import json

from argos import cli, config, fontes
from argos.saidas import catalogo
from tests.apoio import _rodar


def _linhas(caminho):
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def test_catalogo_tem_tres_colunas_e_so_o_que_passou(cfg, rede_jornal, tmp_path):
    c, r = _rodar(cfg, rede_jornal)
    caminho = tmp_path / "catalogo.csv"
    assert catalogo.atualizar(r, caminho) == 1
    (linha,) = _linhas(caminho)
    assert list(linha) == ["id", "url", "identificadores"]
    assert linha["url"] == "https://jornal.exemplo.br/2026/10/carandiru-34-anos"
    assert linha["id"] == catalogo.id_da_url(linha["url"])
    assert linha["identificadores"].split(";")[0] == "massacre-do-carandiru"


def test_catalogo_e_cumulativo_e_guarda_os_identificadores_iniciais(cfg, rede_jornal, tmp_path):
    _, r = _rodar(cfg, rede_jornal)
    caminho = tmp_path / "catalogo.csv"
    catalogo.atualizar(r, caminho)
    antes = caminho.read_text(encoding="utf-8")
    r.linhas[0].resultado.chaves = ["outra-chave"]
    assert catalogo.atualizar(r, caminho) == 0
    assert caminho.read_text(encoding="utf-8") == antes


def test_nivel_minimo(cfg, rede_jornal, tmp_path):
    _, r = _rodar(cfg, rede_jornal)
    assert catalogo.atualizar(r, tmp_path / "a.csv", nivel_minimo=0) == 2
    assert catalogo.atualizar(r, tmp_path / "b.csv", nivel_minimo=3) == 1


def test_sem_guardar_texto_nada_vai_para_o_corpus(cfg, rede_jornal):
    dados = json.loads(cfg.read_text())
    dados["guardar_texto"] = False
    cfg.write_text(json.dumps(dados))
    c, r = _rodar(cfg, rede_jornal)
    assert not c.corpus.exists()
    assert [linha.nivel for linha in r.linhas if linha.nivel is not None] == [3, 0]
    assert all(linha.corpus is None for linha in r.linhas)


def test_cli_atualiza_o_catalogo(cfg, monkeypatch, rede_jornal, capsys):
    dados = json.loads(cfg.read_text())
    dados["catalogo"] = {"arquivo": "catalogo.csv"}
    cfg.write_text(json.dumps(dados))
    construir = fontes.construir
    monkeypatch.setattr(fontes, "construir", lambda f: construir(f, rede_jornal))
    assert cli.main(["rodar", "--config", str(cfg)]) == 3
    assert len(_linhas(config.carregar(cfg).catalogo_csv)) == 1
    assert "catálogo: 1 URLs novas" in capsys.readouterr().out
