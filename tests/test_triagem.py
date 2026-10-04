from datetime import UTC, datetime

import pytest

from argos import lexico
from argos.captura import montar_documento
from argos.contrato import Referencia
from argos.triagem import recortar, triar

REF = Referencia(fonte="teste", id_na_fonte="1", url="https://exemplo.br/1")


@pytest.fixture
def casador(fixtures):
    return lexico.Casador(lexico.carregar(fixtures / "lexico-penal.json"))


def _doc(texto, **destaques):
    return montar_documento(
        REF, texto, destaques=destaques, agora=datetime(2026, 10, 4, tzinfo=UTC)
    )


def test_nivel_0_sem_termo(casador):
    r = triar(_doc("O tribunal promove semana de conciliação."), casador)
    assert (r.nivel, r.motivo, r.trecho) == (0, "sem_termo", None)


def test_nivel_0_so_exclusao_sai_com_trecho(casador):
    r = triar(_doc("Denúncia por homicídio culposo na direção de veículo automotor."), casador)
    assert (r.nivel, r.motivo) == (0, "so_exclusao")
    assert "na direção" in r.trecho


def test_nivel_0_cpm_nao_vira_cp(casador):
    r = triar(_doc("Acórdão: recurso sobre o art. 155, § 1º, do Código Penal Militar."), casador)
    assert (r.nivel, r.motivo) == (0, "so_exclusao")


def test_nivel_1_termo_sem_contexto(casador):
    r = triar(_doc("O art. 155 do Código Penal foi assunto de palestra no auditório."), casador)
    assert (r.nivel, r.motivo, r.chaves) == (1, "sem_contexto", ["cp-art-155"])
    assert "art. 155" in r.trecho


def test_nivel_2_termo_e_contexto_fora_do_destaque(casador):
    doc = _doc(
        "Seminário discute o sistema de justiça. "
        "Entre os casos, um recurso sobre furto qualificado.",
        manchete="Seminário discute o sistema de justiça",
    )
    r = triar(doc, casador)
    assert (r.nivel, r.motivo, r.onde) == (2, "pede_juizo", "texto")


def test_nivel_3_termo_no_destaque(casador):
    doc = _doc(
        "A Terceira Seção fixou tese em recurso repetitivo sobre o art. 155, § 4º, I, do "
        "Código Penal. O caso envolvia também homicídio.",
        ementa="FURTO QUALIFICADO. ROMPIMENTO DE OBSTÁCULO. PROVA.",
    )
    r = triar(doc, casador)
    assert (r.nivel, r.motivo, r.onde) == (3, "aceito", "ementa")
    assert r.chaves == ["cp-art-155", "cp-art-121"]
    assert r.categorias == ["cp"]
    assert r.pontuacao == 2.0
    assert r.trecho == "FURTO QUALIFICADO. ROMPIMENTO DE OBSTÁCULO. PROVA."


def test_recorte_marca_o_que_cortou():
    texto = "a" * 500 + "ALVO" + "b" * 500
    trecho = recortar(texto, 500, 504, raio=10)
    assert trecho == "…" + "a" * 10 + "ALVO" + "b" * 10 + "…"


def test_triagem_e_deterministica(casador):
    doc = _doc("Recurso: art. 155 do CP, pena de reclusão.", ementa="Furto qualificado")
    assert triar(doc, casador) == triar(doc, casador)
