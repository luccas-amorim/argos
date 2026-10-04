import pytest

from argos.http import USER_AGENT, BloqueadoPorPais, BloqueadoPorRobots, Cliente, ErroColeta


class Relogio:
    def __init__(self):
        self.agora = 0.0
        self.pausas = []

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.pausas.append(segundos)
        self.agora += segundos


def _cliente(rede, relogio=None, **kw):
    relogio = relogio or Relogio()
    return Cliente(
        kw.pop("limite", 60), transporte=rede, dormir=relogio.dormir, relogio=relogio, **kw
    )


def test_identifica_o_projeto_e_le_robots_uma_vez_por_origem(rede):
    rede.responder("https://a.br/x", "ok")
    rede.responder("https://a.br/y", "ok")
    cliente = _cliente(rede)
    cliente.requisitar("https://a.br/x")
    cliente.requisitar("https://a.br/y")
    assert rede.urls() == ["https://a.br/robots.txt", "https://a.br/x", "https://a.br/y"]
    assert all(p.cabecalhos["User-Agent"] == USER_AGENT for p in rede.pedidos)


def test_obedece_o_limite_por_minuto(rede):
    rede.responder("https://a.br/x", "ok")
    relogio = Relogio()
    cliente = _cliente(rede, relogio, limite=30, respeita_robots=False)
    for _ in range(3):
        cliente.requisitar("https://a.br/x")
    assert relogio.pausas == [2.0, 2.0]


def test_robots_que_proibe_bloqueia_sem_requisitar(rede):
    rede.responder("https://a.br/robots.txt", "User-agent: *\nDisallow: /privado/\n")
    cliente = _cliente(rede)
    with pytest.raises(BloqueadoPorRobots):
        cliente.requisitar("https://a.br/privado/doc")
    assert "https://a.br/privado/doc" not in rede.urls()


def test_robots_403_proibe_tudo(rede):
    rede.responder("https://a.br/robots.txt", "", status=403)
    with pytest.raises(BloqueadoPorRobots):
        _cliente(rede).requisitar("https://a.br/x")


def test_tenta_de_novo_em_503_e_desiste_em_404(rede):
    rede.responder("https://a.br/x", "fora", status=503)
    rede.responder("https://a.br/x", "ok")
    relogio = Relogio()
    resposta = _cliente(rede, relogio, respeita_robots=False).requisitar("https://a.br/x")
    assert resposta.corpo == b"ok"
    assert 2.0 in relogio.pausas
    with pytest.raises(ErroColeta, match="HTTP 404"):
        _cliente(rede, respeita_robots=False).requisitar("https://a.br/nada")


def test_esgota_tentativas(rede):
    rede.responder("https://a.br/x", "fora", status=502)
    with pytest.raises(ErroColeta, match="após 2 tentativas"):
        _cliente(rede, respeita_robots=False, tentativas=2).requisitar("https://a.br/x")


def test_corpo_json_e_parametros(rede):
    rede.responder("https://api.br/busca", '{"ok": true}')
    cliente = _cliente(rede, respeita_robots=False)
    resposta = cliente.requisitar(
        "https://api.br/busca", metodo="POST", params={"q": "ação"}, json_corpo={"a": 1}
    )
    assert resposta.json() == {"ok": True}
    pedido = rede.pedidos[-1]
    assert pedido.url == "https://api.br/busca?q=a%C3%A7%C3%A3o"
    assert pedido.corpo == b'{"a": 1}'
    assert pedido.cabecalhos["Content-Type"] == "application/json"


def test_bloqueio_por_pais_tem_erro_proprio(rede):
    # Corpo real (resumido) do CloudFront do DJEN, medido em 04/10/2026 de fora do Brasil.
    corpo = (
        "<TITLE>ERROR: The request could not be satisfied</TITLE> The Amazon CloudFront "
        "distribution is configured to block access from your country."
    )
    rede.responder("https://api.br/x", corpo, status=403)
    with pytest.raises(BloqueadoPorPais, match="IP brasileiro"):
        _cliente(rede, respeita_robots=False).requisitar("https://api.br/x")
