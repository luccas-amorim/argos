"""Gera, do catálogo do AtlasPen, o léxico que o Argos usa para achar jurisprudência.

**Só lê o AtlasPen.** Recebe o diretório de um clone dele (`--atlaspen`, ou a variável
`ATLASPEN_DIR`) e lê `data/crimes.json` e `data/diplomas.json`; não escreve nada lá.

O léxico não se escreve à mão: sai de `data/crimes.json` e `data/diplomas.json`, e
muda quando o catálogo muda. Mudar um termo é mudar o catálogo; não há termo em código.

**Granularidade: um termo por artigo de cada diploma** (`cp-art-121`, `cpm-art-205`).
A jurisprudência cita o artigo ("art. 121, § 2º, IV, do Código Penal") e raramente o
inciso de um jeito que se possa casar com segurança. Os ids do catálogo que cada termo
cobre saem de `ids_por_chave()`, que o `mapear.py` usa para levar o achado de volta aos
registros.

As formas de cada termo:

- **citação do artigo com o diploma**, nas grafias que os tribunais usam: "art. 121 …
  Código Penal", "art. 121 … CP", "CP, art. 121", "art. 54 … Lei … 9.605". As
  reticências (`…`) são do formato do Argos: até 60 caracteres quaisquer, o que casa
  "art. 121, § 2º, IV, do Código Penal". Nunca o artigo sozinho: "art. 121" existe em
  dezenas de diplomas.
- **o nome do tipo vai em termo à parte** (`nome-homicidio-culposo`), e só quando é curto
  o bastante para ser como a ementa o escreve (até três palavras, sem barra nem
  parêntese). Os nomes descritivos do catálogo ("Homicídio qualificado por motivo
  torpe") não aparecem assim em decisão. O termo de nome cobre todo registro que tem
  aquele nome, em qualquer diploma: "Homicídio qualificado" é nome no CPM, e a ementa do
  STJ sobre o art. 121 do CP também o escreve. Por isso nome é indício fraco: o
  `mapear.py` só liga decisão a registro com segurança pela citação; o nome sozinho vai
  para "pede juízo".

Os apelidos de cada diploma vêm dos dados: o número da norma ("Lei … 9.605", "Decreto-Lei
… 2.848", "DL … 2.848"), a sigla dos rótulos do catálogo ("CP", "CPM", "CTB") e o nome,
quando é nome de verdade ("Código Penal", "Estatuto do Desarmamento"); "Tortura" e
"Genocídio" descrevem a lei, não a nomeiam.

**Exclusão gerada, não escrita:** quando um apelido é começo de apelido de outro diploma
("Código Penal" e "Código Penal Militar"), a forma mais longa vira exclusão do termo, e a
citação do CPM não conta como CP.

Uso:
    python exemplos/atlaspen/lexico.py --atlaspen ../atlaspen --saida lexico-atlaspen.json
    argos validar-lexico lexico-atlaspen.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

_ARTIGO = re.compile(r"^Art\.\s*(\d+)\s*(º)?\s*(-[A-Z]+)?")
_NORMA = re.compile(r"^(Decreto-Lei|Lei Complementar|Lei)\s+nº\s+([\d.]+)")
_SIGLA = re.compile(r"^([A-Z]{2,4})(?:\s|\(|$)")
_NOMES_PROPRIOS = ("Código", "Lei ", "Estatuto")

CONTEXTO = [
    "acórdão", "ementa", "recurso", "habeas corpus", "ordem concedida", "ordem denegada",
    "denúncia", "condenação", "absolvição", "dosimetria", "pena-base", "regime",
    "tese", "repercussão geral", "recurso repetitivo", "súmula", "tipicidade",
]  # fmt: skip


def apelidos(diploma: dict) -> list[str]:
    """Como a jurisprudência chama o diploma. Lido dos dados, nunca escrito à mão."""
    saida: list[str] = []
    if m := _NORMA.match(diploma.get("norma", "")):
        especie, numero = m.groups()
        sem_ponto = numero.replace(".", "")
        saida.append(f"{especie} … {numero}")
        if sem_ponto != numero:
            saida.append(f"{especie} … {sem_ponto}")
        if especie == "Decreto-Lei":
            saida.append(f"DL … {numero}")
        if especie == "Lei Complementar":
            saida.append(f"LC … {numero}")
    for rotulo in diploma.get("rotulos_catalogo") or []:
        if (m := _SIGLA.match(rotulo)) and m.group(1) not in {"DL", "LC"}:
            saida.append(m.group(1))
    nome = re.split(r"\s+[—(]", diploma.get("nome", ""))[0].strip()
    if nome.startswith(_NOMES_PROPRIOS):
        saida.append(nome)
    return list(dict.fromkeys(saida))


def numero_do_artigo(artigo: str) -> str | None:
    """'Art. 121-A, §2º, I' -> '121-A'; 'Art. 1º' -> '1'."""
    m = _ARTIGO.match(artigo)
    if not m:
        return None
    return f"{m.group(1)}{m.group(3) or ''}"


def _citacoes(numero: str, apelido: str) -> list[str]:
    numeros = [numero]
    if numero.isdigit() and int(numero) < 10:
        numeros.append(f"{numero}º")  # "art. 1º": o º é letra para o regex
    formas = []
    for n in numeros:
        # A ordem inversa é sempre colada ("CP, art. 121"): com lacuna, "Código Penal.
        # Condenação pelo art. 33 (...). Art. 205" casaria o art. 205 do CP.
        formas += [f"art. {n} … {apelido}", f"artigo {n} … {apelido}", f"{apelido}, art. {n}"]
    return formas


def _nome_curto(nome: str) -> str | None:
    if any(c in nome for c in "/()") or len(nome.split()) > 3 or len(nome) < 10:
        return None
    return nome


def _rotulo_para_diploma(diplomas: list[dict]) -> dict[str, dict]:
    return {r: d for d in diplomas for r in (d.get("rotulos_catalogo") or [])}


def chave(diploma_id: str, numero: str) -> str:
    return f"{diploma_id}-art-{numero.lower()}"


def chave_de_nome(nome: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", nome.lower()) if not unicodedata.combining(c)
    )
    return "nome-" + re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-")


def ids_por_chave(crimes: list[dict], diplomas: list[dict]) -> dict[str, list[int]]:
    """Os registros do catálogo que cada termo cobre. O `mapear.py` lê isto."""
    por_rotulo = _rotulo_para_diploma(diplomas)
    saida: dict[str, list[int]] = defaultdict(list)
    for crime in crimes:
        diploma, numero = por_rotulo.get(crime["lei"]), numero_do_artigo(crime["artigo"])
        if diploma and numero:
            saida[chave(diploma["id"], numero)].append(crime["id"])
        if nome := _nome_curto(crime["crime"]):
            saida[chave_de_nome(nome)].append(crime["id"])
    return dict(saida)


def gerar(crimes: list[dict], diplomas: list[dict], versao: str | None = None) -> dict:
    por_rotulo = _rotulo_para_diploma(diplomas)
    por_id = {d["id"]: d for d in diplomas}
    todos_apelidos = {d["id"]: apelidos(d) for d in diplomas}

    termos: dict[str, dict] = {}
    for crime in crimes:
        diploma, numero = por_rotulo.get(crime["lei"]), numero_do_artigo(crime["artigo"])
        if not (diploma and numero):
            continue
        k = chave(diploma["id"], numero)
        termo = termos.setdefault(
            k,
            {"chave": k, "formas": [], "exclusoes": [], "categorias": [diploma["id"]], "nota": ""},
        )
        if not termo["formas"]:
            for apelido in todos_apelidos[diploma["id"]]:
                termo["formas"] += _citacoes(numero, apelido)
                # Apelido que é começo de apelido de outro diploma: a forma longa exclui.
                for outro, deles in todos_apelidos.items():
                    if outro == diploma["id"]:
                        continue
                    for longo in deles:
                        if longo.startswith(f"{apelido} "):
                            termo["exclusoes"] += _citacoes(numero, longo)
            termo["nota"] = f"{por_id[diploma['id']]['nome']}, art. {numero}"
        if nome := _nome_curto(crime["crime"]):
            k_nome = chave_de_nome(nome)
            por_nome = termos.setdefault(
                k_nome,
                {"chave": k_nome, "formas": [nome], "categorias": ["nome"], "peso": 0.5},
            )
            por_nome.setdefault("nota", "Nome do tipo: indício fraco, ver mapear.py.")

    lista = []
    for termo in termos.values():
        termo["formas"] = list(dict.fromkeys(termo["formas"]))
        termo["exclusoes"] = list(dict.fromkeys(termo.get("exclusoes", [])))
        if not termo["exclusoes"]:
            del termo["exclusoes"]
        lista.append(termo)
    lista.sort(key=lambda t: t["chave"])
    return {
        "id": "atlaspen-catalogo",
        "versao": versao or date.today().isoformat(),
        "descricao": "Gerado de data/crimes.json e data/diplomas.json por "
        "exemplos/atlaspen/lexico.py do Argos. Não editar à mão.",
        "termos": lista,
        "contexto": {
            "exige_qualquer": CONTEXTO,
            "nota": "Vocabulário decisório: separa decisão de texto que só menciona o artigo.",
        },
    }


def diretorio(valor: str | None) -> Path:
    """O clone do AtlasPen: o argumento, ou ATLASPEN_DIR. Sem nenhum dos dois, erro claro."""
    caminho = valor or os.environ.get("ATLASPEN_DIR")
    if not caminho:
        raise SystemExit("informe o clone do AtlasPen com --atlaspen ou ATLASPEN_DIR")
    return Path(caminho)


def carregar(atlaspen: Path) -> tuple[list[dict], list[dict]]:
    """Lê `crimes.json` e `diplomas.json` do clone do AtlasPen. Só leitura."""
    dados = Path(atlaspen) / "data"
    crimes = json.loads((dados / "crimes.json").read_text(encoding="utf-8"))
    diplomas = json.loads((dados / "diplomas.json").read_text(encoding="utf-8"))["diplomas"]
    return crimes, diplomas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--atlaspen", help="clone do AtlasPen (padrão: ATLASPEN_DIR)")
    parser.add_argument("--saida", type=Path, help="onde gravar; sem ela, só o resumo")
    args = parser.parse_args(argv)
    crimes, diplomas = carregar(diretorio(args.atlaspen))
    lexico = gerar(crimes, diplomas)
    # Coberto é registro alcançável por CITAÇÃO; nome sozinho não liga com segurança.
    cobertos = len(
        {i for k, ids in ids_por_chave(crimes, diplomas).items() if "-art-" in k for i in ids}
    )
    formas = sum(len(t["formas"]) for t in lexico["termos"])
    print(
        f"{len(lexico['termos'])} termos, {formas} formas; "
        f"{cobertos} de {len(crimes)} registros cobertos"
    )
    if args.saida:
        args.saida.write_text(json.dumps(lexico, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"gravado em {args.saida}")
    return 0 if cobertos == len(crimes) else 2


if __name__ == "__main__":
    sys.exit(main())
