import json
from pathlib import Path

import pytest

from argos import lexico
from argos.texto import dobrar

RAIZ = Path(__file__).parents[1]


def _casar(lex, texto):
    validas, anuladas = lexico.Casador(lex).ocorrencias(dobrar(texto))
    return [o.chave for o in validas], [o.chave for o in anuladas]


def test_exemplo_do_repositorio_e_valido():
    lex = lexico.carregar(RAIZ / "exemplos" / "lexico.exemplo.json")
    assert lex.termos[0].chave == "cp-art-121"
    assert "recurso" in lex.contexto


def test_schema_e_validador_concordam():
    """Os campos aceitos pelo validador são exatamente os do schema publicado."""
    schema = json.loads((RAIZ / "exemplos" / "lexico.schema.json").read_text(encoding="utf-8"))
    termo = schema["properties"]["termos"]["items"]
    contexto = schema["properties"]["contexto"]
    assert set(schema["properties"]) == lexico._CHAVES_RAIZ
    assert set(termo["properties"]) == lexico._CHAVES_TERMO
    assert set(contexto["properties"]) == lexico._CHAVES_CONTEXTO
    assert set(schema["required"]) == {"id", "versao", "termos"}
    assert set(termo["required"]) == {"chave", "formas"}


@pytest.mark.parametrize(
    ("dados", "trecho"),
    [
        ({"versao": "1", "termos": [{"chave": "a", "formas": ["a"]}]}, "id"),
        ({"id": "x", "versao": "1", "termos": []}, "termos"),
        ({"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": []}]}, "formas"),
        (
            {"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["a"], "peso": 0}]},
            "peso",
        ),
        (
            {
                "id": "x",
                "versao": "1",
                "termos": [{"chave": "a", "formas": ["a"]}, {"chave": "a", "formas": ["b"]}],
            },
            "repetida",
        ),
        (
            {"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["a"], "regex": "."}]},
            "desconhecido",
        ),
        (
            {"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["a"]}], "contexto": {}},
            "exige_qualquer",
        ),
    ],
)
def test_invalidos_sao_recusados_com_motivo(dados, trecho):
    problemas = lexico.validar(dados)
    assert problemas
    assert any(trecho in p for p in problemas)
    with pytest.raises(lexico.ErroLexico):
        lexico.de_dados(dados)


def test_casa_sem_acento_sem_caixa_e_por_palavra_inteira():
    lex = lexico.de_dados(
        {"id": "x", "versao": "1", "termos": [{"chave": "h", "formas": ["homicídio"]}]}
    )
    assert _casar(lex, "HOMICIDIO qualificado")[0] == ["h"]
    assert _casar(lex, "Homicídio")[0] == ["h"]
    assert _casar(lex, "pré-homicídiorama")[0] == []


def test_espaco_da_forma_tolera_quebra_de_linha():
    lex = lexico.de_dados(
        {"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["art. 121 do CP"]}]}
    )
    assert _casar(lex, "nos termos do art.\n121  do CP")[0] == ["a"]


def test_exclusao_anula_so_a_ocorrencia_que_contem():
    lex = lexico.carregar(RAIZ / "exemplos" / "lexico.exemplo.json")
    validas, anuladas = _casar(lex, "Trata-se de homicídio culposo na direção de veículo.")
    assert validas == [] and anuladas == ["cp-art-121"]
    validas, anuladas = _casar(
        lex, "Homicídio culposo na direção; depois, homicídio doloso, art. 121 do Código Penal."
    )
    assert validas == ["cp-art-121", "cp-art-121"] and anuladas == ["cp-art-121"]


def test_forma_mais_longa_vence_na_mesma_posicao():
    lex = lexico.carregar(RAIZ / "exemplos" / "lexico.exemplo.json")
    casador = lexico.Casador(lex)
    texto = dobrar("conforme o art. 121 do Código Penal")
    (oc,), _ = casador.ocorrencias(texto)
    assert texto[oc.inicio : oc.fim] == "art. 121 do codigo penal"


def test_contexto_ausente_no_lexico_nao_exige_nada():
    lex = lexico.de_dados({"id": "x", "versao": "1", "termos": [{"chave": "a", "formas": ["a"]}]})
    assert lexico.Casador(lex).contexto("qualquer coisa") is True
