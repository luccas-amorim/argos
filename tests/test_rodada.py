"""Rodada de ponta a ponta, sem rede: feed, páginas, sentinela, triagem, estado e saídas."""

import json
import shutil
from datetime import date

import pytest

from argos import cli, config, estado, fontes, lexico, rodada, saidas

FEED = "https://jornal.exemplo.br/feed"
BASE = "https://jornal.exemplo.br/2026/10"


@pytest.fixture
def cfg(tmp_path, fixtures):
    shutil.copy(fixtures / "lexico-carandiru.json", tmp_path / "lexico.json")
    dados = {
        "lexico": "lexico.json",
        "diretorio": "dados",
        "desde": "2026-09-01",
        "fontes": [{"tipo": "rss", "id": "rss:jornal", "url": FEED, "minimo_caracteres": 200}],
    }
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


@pytest.fixture
def rede_jornal(rede, fixtures):
    rede.responder(FEED, fixtures / "rss" / "feed.xml")
    rede.responder(f"{BASE}/carandiru-34-anos", fixtures / "rss" / "materia-carandiru.html")
    rede.responder(f"{BASE}/drenagem", fixtures / "rss" / "materia-outra.html")
    rede.responder(f"{BASE}/sumiu", fixtures / "rss" / "erro-200.html")
    return rede


def _rodar(caminho, rede, **kw):
    c = config.carregar(caminho)
    casador = lexico.Casador(lexico.carregar(c.lexico))
    instancias = [fontes.construir(f, rede) for f in c.fontes]
    return c, rodada.rodar(c, instancias, casador, hoje=date(2026, 10, 4), **kw)


def test_rodada_completa(cfg, rede_jornal):
    c, r = _rodar(cfg, rede_jornal)
    por_id = {linha.ref.id_na_fonte: linha for linha in r.linhas}

    assert set(por_id) == {"jornal-1001", "jornal-1002", "jornal-1003"}  # 0900 é anterior
    assert por_id["jornal-1001"].nivel == 3
    assert por_id["jornal-1001"].resultado.onde == "manchete"
    assert por_id["jornal-1002"].resultado.motivo == "sem_termo"
    assert por_id["jornal-1003"].situacao == rodada.SENTINELA
    assert r.codigo_saida == rodada.PEDE_LEITURA
    assert r.desde == {"rss:jornal": "2026-09-01"}

    # Corpus: só o íntegro tem nome canônico; o reprovado fica como .part.
    pasta = c.corpus / "rss_jornal"
    assert len(list(pasta.glob("*.json"))) == 2
    assert len(list(pasta.glob("*.json.part"))) == 1

    # Estado: o reprovado não é marcado como visto, para ser tentado de novo.
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.ultima_rodada == date(2026, 10, 4)
    assert set(memoria.vistos) == {"jornal-1001", "jornal-1002"}


def test_saidas(cfg, rede_jornal):
    c, r = _rodar(cfg, rede_jornal)
    pasta = saidas.escrever(r, c.saidas)
    aceitos = [json.loads(x) for x in (pasta / "aceitos.jsonl").read_text().splitlines()]
    assert len(aceitos) == 1
    item = aceitos[0]
    assert item["url"] == f"{BASE}/carandiru-34-anos"
    assert item["lexico"] == {"id": "carandiru-amostra", "versao": "2026-10-04"}
    assert item["chaves"][0] == "massacre-do-carandiru"
    assert "evento" in item["categorias"]
    assert item["hash_texto"] and item["capturado_em"]
    assert item["corpus"] == f"corpus/rss_jornal/{item['hash_texto']}.json"
    assert (c.diretorio / item["corpus"]).exists()
    assert (pasta / "pede-juizo.jsonl").read_text() == ""
    assert len((pasta / "itens.jsonl").read_text().splitlines()) == 3

    completo = (pasta / "relatorio-completo.md").read_text()
    resumo = (pasta / "relatorio-resumo.md").read_text()
    assert "Descartados no nível 0" in completo and "drenagem" in completo
    assert "drenagem" not in resumo
    assert "Falhas de captura ou de integridade (1)" in resumo
    meta = json.loads((pasta / "rodada.json").read_text())
    assert meta["contagens"]["situacao"] == {"reprovado_sentinela": 1, "triado": 2}
    assert meta["codigo_saida"] == 3


def test_segunda_rodada_nao_rebaixa_o_que_ja_viu(cfg, rede_jornal):
    _rodar(cfg, rede_jornal)
    rede_jornal.pedidos.clear()
    _, r = _rodar(cfg, rede_jornal)
    baixadas = [u for u in rede_jornal.urls() if u.startswith(BASE)]
    # A janela agora começa em 02/10 e o item reprovado é de 01/10: só volta por ser pendente.
    assert r.desde == {"rss:jornal": "2026-10-02"}  # última rodada menos a margem
    assert baixadas == [f"{BASE}/sumiu"]


def test_pendente_e_resolvido_quando_a_pagina_volta(cfg, rede_jornal, fixtures):
    c, _ = _rodar(cfg, rede_jornal)
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.pendentes["jornal-1003"]["motivo"] == rodada.SENTINELA
    assert memoria.pendentes["jornal-1003"]["tentativas"] == 1

    rede_jornal.rotas[f"{BASE}/sumiu"] = []
    rede_jornal.responder(f"{BASE}/sumiu", fixtures / "rss" / "materia-carandiru.html")
    _, r = _rodar(cfg, rede_jornal)
    assert [linha.nivel for linha in r.linhas] == [3]
    memoria = estado.ler(c.estado, "rss:jornal")
    assert memoria.pendentes == {}
    assert "jornal-1003" in memoria.vistos


def test_sem_estado_rele_tudo_e_nao_grava(cfg, rede_jornal):
    c, _ = _rodar(cfg, rede_jornal, usar_estado=False)
    assert not estado.caminho(c.estado, "rss:jornal").exists()


def test_fonte_fora_do_ar_da_codigo_2_e_nao_avanca_o_estado(cfg, rede):
    c, r = _rodar(cfg, rede)  # sem rota para o feed: 404
    assert r.codigo_saida == rodada.ERRO
    assert "rss:jornal" in r.falhas_de_fonte
    assert not estado.caminho(c.estado, "rss:jornal").exists()


def test_retriar_aplica_lexico_novo_sem_rede(cfg, rede_jornal, tmp_path):
    c, _ = _rodar(cfg, rede_jornal)
    novo = json.loads((tmp_path / "lexico.json").read_text())
    novo["versao"] = "2026-10-05"
    novo["termos"].append({"chave": "drenagem", "formas": ["drenagem"]})
    novo["contexto"]["exige_qualquer"].append("prefeitura")
    (tmp_path / "lexico.json").write_text(json.dumps(novo))

    r = rodada.retriar(c, lexico.Casador(lexico.carregar(c.lexico)))
    assert r.lexico_versao == "2026-10-05"
    niveis = sorted(linha.nivel for linha in r.linhas)
    assert niveis == [3, 3]


def test_cli_validar_e_rodar_sem_fonte(cfg, capsys, fixtures):
    assert cli.main(["validar-lexico", str(fixtures / "lexico-carandiru.json")]) == 0
    assert "válido" in capsys.readouterr().out
    assert cli.main(["rodar", "--config", str(cfg), "--fonte", "rss:outra"]) == rodada.ERRO


def test_configuracao_de_exemplo_carrega_e_constroi():
    from pathlib import Path

    raiz = Path(__file__).parents[1]
    c = config.carregar(raiz / "exemplos" / "config.exemplo.json")
    assert c.lexico == (raiz / "exemplos" / "lexico.exemplo.json").resolve()
    assert c.diretorio == (raiz / "dados").resolve()
    assert [fontes.construir(f).id for f in c.fontes] == ["datajud:stm"]


def test_feed_malformado_derruba_so_a_fonte(cfg, rede):
    rede.responder(FEED, "<rss><channel><item>sem fechar")
    _, r = _rodar(cfg, rede)
    assert r.codigo_saida == rodada.ERRO
    assert r.falhas_de_fonte["rss:jornal"].startswith("listagem: ParseError")
