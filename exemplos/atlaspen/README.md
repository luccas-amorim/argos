# Exemplo de consumidor: jurisprudência para o AtlasPen

O Argos procurando decisões sobre os tipos penais do
[AtlasPen](https://github.com/luccas-amorim/atlaspen). **O AtlasPen é só lido:** estes
scripts recebem o diretório de um clone dele, leem `data/crimes.json` e
`data/diplomas.json`, e entregam arquivos aqui. Levar o resultado ao AtlasPen é decisão
de quem o mantém.

| Arquivo | O que faz |
|---|---|
| `lexico.py` | gera o léxico do Argos a partir do catálogo: um termo por artigo de cada diploma, com a citação na forma dos tribunais, e o nome curto do tipo em termo à parte |
| `mapear.py` | leva a rodada do Argos de volta aos registros, como relatório: por citação, só pelo nome (pede juízo) e fichas do DataJud |
| `config.json` | as fontes: DJEN do STJ (acórdãos) e DataJud do STM (pequeno, quase todo penal). O DataJud do STJ fica de fora até haver um filtro conferido em resposta real: sem filtro, o volume é o do tribunal inteiro |

## Rodar

```bash
git clone --depth 1 https://github.com/luccas-amorim/atlaspen ../atlaspen
python exemplos/atlaspen/lexico.py --atlaspen ../atlaspen --saida exemplos/atlaspen/lexico.json
argos validar-lexico exemplos/atlaspen/lexico.json
argos rodar --config exemplos/atlaspen/config.json --desde 2026-09-01
python exemplos/atlaspen/mapear.py dados-atlaspen/saidas/<rodada> --atlaspen ../atlaspen --md relatorio.md
```

O DJEN só responde a IP brasileiro: de fora do país, a fonte `djen:stj` falha com
`BloqueadoPorPais` e as fichas do DataJud seguem sozinhas.

O plano completo, com o recorte, as lições do gerador e o que não fazer, está em
[`docs/jurisprudencia.md`](../../docs/jurisprudencia.md); o do STF, em
[`docs/stf.md`](../../docs/stf.md).

## Dados

`lexico.json` é gerado e não vai para o git. Os dados de que ele sai são do AtlasPen, sob
Creative Commons Atribuição 4.0 (CC BY 4.0), de Luccas de Amorim; o recorte usado nos
testes, em `tests/fixtures/atlaspen/`, é cópia sem alteração de parte deles.
