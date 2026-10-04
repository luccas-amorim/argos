"""Exemplo de consumidor: o léxico gerado do catálogo do AtlasPen e o mapa de volta.

Roda contra um recorte de `data/crimes.json` e `data/diplomas.json` do AtlasPen, copiado
sem alteração para `tests/fixtures/atlaspen/`. Com `ATLASPEN_DIR` apontando para um clone,
roda também contra o catálogo inteiro. Nada aqui escreve no AtlasPen.
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from argos import lexico as argos_lexico
from argos.texto import dobrar

sys.path.insert(0, str(Path(__file__).parents[1] / "exemplos" / "atlaspen"))

import lexico  # noqa: E402
import mapear  # noqa: E402

RECORTE = Path(__file__).parent / "fixtures" / "atlaspen"


@pytest.fixture(scope="module")
def dados():
    return lexico.carregar(RECORTE)


@pytest.fixture(scope="module")
def gerado(dados):
    return lexico.gerar(*dados, versao="2026-10-04")


def _termo(gerado, chave):
    return next(t for t in gerado["termos"] if t["chave"] == chave)


def _casar(gerado, texto):
    casador = argos_lexico.Casador(argos_lexico.de_dados(gerado))
    validas, _ = casador.ocorrencias(dobrar(texto))
    return {o.chave for o in validas}


def test_valido_para_o_argos_e_todo_registro_alcancavel(dados, gerado):
    assert argos_lexico.validar(gerado) == []
    crimes, diplomas = dados
    por_chave = lexico.ids_por_chave(crimes, diplomas)
    citados = {i for k, ids in por_chave.items() if "-art-" in k for i in ids}
    assert citados == {c["id"] for c in crimes}


def test_citacao_nunca_e_o_artigo_sozinho(gerado):
    sozinho = re.compile(r"^(art\.|artigo)\s+\S+$")
    for termo in gerado["termos"]:
        if "-art-" in termo["chave"]:
            assert not any(sozinho.match(f) for f in termo["formas"]), termo["chave"]


def test_apelidos_vem_dos_dados(dados):
    _, diplomas = dados
    cp = next(d for d in diplomas if d["id"] == "cp")
    assert lexico.apelidos(cp) == [
        "Decreto-Lei … 2.848", "Decreto-Lei … 2848", "DL … 2.848", "CP", "Código Penal",
    ]  # fmt: skip
    tortura = next(d for d in diplomas if d["id"] == "lei9455")
    assert "Tortura" not in lexico.apelidos(tortura)  # descreve a lei, não a nomeia


def test_cpm_vira_exclusao_do_cp(gerado):
    cp121 = _termo(gerado, "cp-art-121")
    assert "art. 121 … Código Penal" in cp121["formas"]
    assert "art. 121 … Código Penal Militar" in cp121["exclusoes"]
    assert "exclusoes" not in _termo(gerado, "cpm-art-205")


def test_nome_e_termo_a_parte_e_fraco(gerado):
    termo = _termo(gerado, "nome-homicidio-culposo")
    assert termo["formas"] == ["Homicídio culposo"] and termo["peso"] == 0.5
    assert all("Homicídio" not in f for f in _termo(gerado, "cp-art-121")["formas"])


def test_ordinal_de_um_a_nove(gerado):
    formas = _termo(gerado, "lei9455-art-1")["formas"]
    assert "art. 1º … Lei … 9.455" in formas and "art. 1 … Lei … 9.455" in formas


def test_casa_como_a_jurisprudencia_cita(gerado):
    texto = (
        "PENAL. RECURSO ESPECIAL. HOMICÍDIO QUALIFICADO. ART. 121, § 2º, IV, DO CÓDIGO PENAL. "
        "Condenação pelo art. 33, caput, da Lei n. 11.343/2006. Art. 205 do Código Penal Militar."
    )
    # O art. 205 do CPM não vira art. 205 do CP: nem pela exclusão, nem pela ordem inversa
    # atravessando frases ("Código Penal. Condenação pelo art. 33 (...). Art. 205").
    assert _casar(gerado, texto) == {
        "cp-art-121", "lei11343-art-33", "cpm-art-205", "nome-homicidio-qualificado",
    }  # fmt: skip


def test_ordem_inversa_colada(gerado):
    assert _casar(gerado, "nos termos do CP, art. 155, § 4º, I") == {"cp-art-155"}


def test_mapear_separa_citacao_nome_e_ficha(dados, tmp_path):
    crimes, diplomas = dados
    itens = [
        {"fonte": "djen:stj", "url": "https://x/1", "titulo": "Acórdão 1", "nivel": 3,
         "chaves": ["cp-art-121", "nome-homicidio-qualificado"], "trecho": "ART. 121"},
        {"fonte": "djen:stj", "url": "https://x/2", "titulo": "Decisão 2", "nivel": 2,
         "chaves": ["nome-homicidio-qualificado"]},
        {"fonte": "datajud:stm", "url": "https://x/3", "titulo": "Ficha 3", "nivel": 3,
         "chaves": ["cpm-art-205"]},
    ]  # fmt: skip
    (tmp_path / "aceitos.jsonl").write_text("\n".join(json.dumps(i) for i in itens))
    m = mapear.mapear(mapear.ler_itens(tmp_path), crimes, diplomas)

    ids_121 = set(lexico.ids_por_chave(crimes, diplomas)["cp-art-121"])
    assert set(m["por_citacao"]) == ids_121  # a citação liga; o nome no mesmo item não soma
    assert [i["url"] for i, _ in m["so_nome"]] == ["https://x/2"]
    assert [i["url"] for i in m["fichas"]] == ["https://x/3"]
    texto = mapear.relatorio(m)
    assert "## Só pelo nome (pede juízo)" in texto
    assert "Nada aqui foi escrito no catálogo" in texto


def test_cli_exige_o_clone_e_so_le(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ATLASPEN_DIR", raising=False)
    with pytest.raises(SystemExit, match="--atlaspen"):
        lexico.main([])
    saida = tmp_path / "lexico.json"
    assert lexico.main(["--atlaspen", str(RECORTE), "--saida", str(saida)]) == 0
    assert json.loads(saida.read_text())["id"] == "atlaspen-catalogo"
    assert mapear.main([str(tmp_path), "--atlaspen", str(RECORTE)]) == 0  # rodada vazia


@pytest.mark.skipif(not os.environ.get("ATLASPEN_DIR"), reason="ATLASPEN_DIR não definido")
def test_catalogo_inteiro_alcancavel_por_citacao():
    crimes, diplomas = lexico.carregar(Path(os.environ["ATLASPEN_DIR"]))
    gerado = lexico.gerar(crimes, diplomas)
    assert argos_lexico.validar(gerado) == []
    por_chave = lexico.ids_por_chave(crimes, diplomas)
    citados = {i for k, ids in por_chave.items() if "-art-" in k for i in ids}
    assert citados == {c["id"] for c in crimes}
