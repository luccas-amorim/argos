"""Linha de comando.

    python -m argos rodar --config exemplos/config.exemplo.json
    python -m argos rodar --config ... --desde 2026-09-01 --sem-estado
    python -m argos retriar --config ...
    python -m argos validar-lexico exemplos/lexico.exemplo.json

Saídas: 0 nada a ler; 2 erro de execução ou fonte fora do ar; 3 há itens que pedem juízo.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from argos import __version__, config, fontes, lexico, rodada, saidas
from argos.saidas import catalogo


def _rodar(args: argparse.Namespace) -> int:
    cfg = config.carregar(args.config)
    casador = lexico.Casador(lexico.carregar(cfg.lexico))
    selecionadas = [f for f in cfg.fontes if not args.fonte or f["id"] in args.fonte]
    if args.fonte and len(selecionadas) != len(set(args.fonte)):
        print(f"fonte desconhecida entre {args.fonte}", file=sys.stderr)
        return rodada.ERRO
    instancias = [fontes.construir(f) for f in selecionadas]
    desde = date.fromisoformat(args.desde) if args.desde else None
    resultado = rodada.rodar(cfg, instancias, casador, desde=desde, usar_estado=not args.sem_estado)
    pasta = saidas.escrever(resultado, cfg.saidas)
    print(f"{len(resultado.linhas)} itens; saídas em {pasta}")
    _catalogar(cfg, resultado)
    return resultado.codigo_saida


def _catalogar(cfg: config.Config, resultado: rodada.Rodada) -> None:
    if cfg.catalogo_csv is None:
        return
    nivel = int(cfg.catalogo.get("nivel_minimo", 2))
    novas = catalogo.atualizar(resultado, cfg.catalogo_csv, nivel)
    print(f"catálogo: {novas} URLs novas em {cfg.catalogo_csv}")


def _retriar(args: argparse.Namespace) -> int:
    cfg = config.carregar(args.config)
    casador = lexico.Casador(lexico.carregar(cfg.lexico))
    resultado = rodada.retriar(cfg, casador, args.fonte)
    pasta = saidas.escrever(resultado, cfg.saidas)
    print(f"{len(resultado.linhas)} itens retriados; saídas em {pasta}")
    _catalogar(cfg, resultado)
    return resultado.codigo_saida


def _validar_lexico(args: argparse.Namespace) -> int:
    try:
        lex = lexico.carregar(args.arquivo)
    except lexico.ErroLexico as erro:
        print(erro, file=sys.stderr)
        return rodada.ERRO
    formas = sum(len(t.formas) for t in lex.termos)
    print(f"{lex.id} {lex.versao}: válido, {len(lex.termos)} termos, {formas} formas")
    return rodada.SEM_NADA


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="argos", description=__doc__.split("\n")[0])
    parser.add_argument("--version", action="version", version=f"argos {__version__}")
    parser.add_argument("-v", "--verboso", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("rodar", help="uma rodada: listar, baixar, triar, gravar")
    p.add_argument("--config", required=True)
    p.add_argument("--desde", help="AAAA-MM-DD; ignora a data guardada no estado")
    p.add_argument("--sem-estado", action="store_true", help="relê tudo e não grava estado")
    p.add_argument("--fonte", action="append", help="só esta fonte (repetível)")
    p.set_defaults(func=_rodar)

    p = sub.add_parser("retriar", help="aplica o léxico atual ao corpus guardado, sem rede")
    p.add_argument("--config", required=True)
    p.add_argument("--fonte")
    p.set_defaults(func=_retriar)

    p = sub.add_parser("validar-lexico", help="confere o formato de um léxico")
    p.add_argument("arquivo")
    p.set_defaults(func=_validar_lexico)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (OSError, ValueError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return rodada.ERRO
