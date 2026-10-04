"""Leva o que o Argos achou de volta aos registros do catálogo do AtlasPen, como relatório.

Só lê o AtlasPen (`--atlaspen` ou `ATLASPEN_DIR`): o relatório sai aqui, e levá-lo ao
AtlasPen é decisão de quem o mantém.

Lê a pasta de uma rodada do Argos (`aceitos.jsonl` e `pede-juizo.jsonl`), usa as chaves
do léxico gerado por `lexico.py` para achar os registros, e escreve um relatório em
Markdown. **Não escreve no catálogo** e não cria `data/jurisprudencia.json`: o formato
desse arquivo é decisão do projeto, e até lá o achado é pergunta, não dado, como nos
derivadores de violência e de ação penal.

Três listas:

- **por citação**: a decisão cita o artigo com o diploma ("art. 121 … Código Penal"). É
  a ligação segura, registro por registro.
- **só pelo nome**: a decisão escreve o nome do tipo e não cita o artigo. O nome pode ser
  de mais de um diploma ("Homicídio qualificado" é nome no CPM e aparece em ementa do
  CP), então vai como pede juízo, com os candidatos.
- **sem metadado de texto**: item do DataJud (ficha do processo, sem decisão). Diz que o
  processo existe e sobre o que é, não o que se decidiu; fica à parte.

Uso:
    python exemplos/atlaspen/mapear.py <pasta-da-rodada-do-argos> --atlaspen ../atlaspen
    python exemplos/atlaspen/mapear.py <pasta> --atlaspen ../atlaspen --md relatorio.md

Saídas: 0 = nada achado; 3 = há o que ler.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lexico import carregar, diretorio, ids_por_chave  # noqa: E402


def ler_itens(pasta: Path) -> list[dict]:
    itens = []
    for nome in ("aceitos.jsonl", "pede-juizo.jsonl"):
        arquivo = pasta / nome
        if arquivo.exists():
            itens += [json.loads(x) for x in arquivo.read_text(encoding="utf-8").splitlines()]
    return itens


def mapear(itens: list[dict], crimes: list[dict], diplomas: list[dict]) -> dict:
    por_chave = ids_por_chave(crimes, diplomas)
    nomes = {c["id"]: f"{c['lei']} {c['artigo']}: {c['crime']}" for c in crimes}
    por_citacao: dict[int, list[dict]] = defaultdict(list)
    so_nome: list[tuple[dict, list[int]]] = []
    fichas: list[dict] = []
    for item in itens:
        if item["fonte"].startswith("datajud"):
            fichas.append(item)
            continue
        citadas = [k for k in item.get("chaves", []) if "-art-" in k]
        if citadas:
            for k in citadas:
                for i in por_chave.get(k, []):
                    por_citacao[i].append(item)
        else:
            candidatos = sorted({i for k in item.get("chaves", []) for i in por_chave.get(k, [])})
            so_nome.append((item, candidatos))
    return {"por_citacao": dict(por_citacao), "so_nome": so_nome, "fichas": fichas, "nomes": nomes}


def _linha(item: dict) -> str:
    titulo = (item.get("titulo") or item["url"]).replace("|", "\\|")
    return f"[{titulo}]({item['url']}) ({item['fonte']}, nível {item.get('nivel')})"


def relatorio(m: dict) -> str:
    saida = ["# Jurisprudência achada pelo Argos", ""]
    saida += [
        f"Por citação: {len(m['por_citacao'])} registros. Só pelo nome: {len(m['so_nome'])} "
        f"decisões. Fichas do DataJud: {len(m['fichas'])}.",
        "",
        "Nada aqui foi escrito no catálogo. Cada ligação é pergunta para quem assina.",
    ]
    if m["por_citacao"]:
        saida += ["", "## Por citação", ""]
        for i in sorted(m["por_citacao"]):
            saida.append(f"- **{i}** {m['nomes'][i]}")
            vistos = set()
            for item in m["por_citacao"][i]:
                if item["url"] in vistos:
                    continue
                vistos.add(item["url"])
                saida.append(f"  - {_linha(item)}")
                if item.get("trecho"):
                    saida.append(f"    > {item['trecho']}")
    if m["so_nome"]:
        saida += ["", "## Só pelo nome (pede juízo)", ""]
        for item, candidatos in m["so_nome"]:
            ids = ", ".join(str(i) for i in candidatos[:12])
            mais = f" e mais {len(candidatos) - 12}" if len(candidatos) > 12 else ""
            saida.append(f"- {_linha(item)}; candidatos: {ids}{mais}")
    if m["fichas"]:
        saida += ["", "## Fichas do DataJud (sem texto de decisão)", ""]
        saida += [f"- {_linha(item)}: {', '.join(item.get('chaves', []))}" for item in m["fichas"]]
    return "\n".join(saida) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pasta", type=Path, help="pasta de uma rodada do Argos")
    parser.add_argument("--atlaspen", help="clone do AtlasPen (padrão: ATLASPEN_DIR)")
    parser.add_argument("--md", type=Path, help="grava o relatório aqui")
    args = parser.parse_args(argv)
    crimes, diplomas = carregar(diretorio(args.atlaspen))
    m = mapear(ler_itens(args.pasta), crimes, diplomas)
    texto = relatorio(m)
    if args.md:
        args.md.write_text(texto, encoding="utf-8")
    else:
        print(texto)
    return 3 if (m["por_citacao"] or m["so_nome"] or m["fichas"]) else 0


if __name__ == "__main__":
    sys.exit(main())
