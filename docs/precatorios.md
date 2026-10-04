# Precatórios: cenários para decidir a expansão

Esboço para direcionar, não plano. **Decidido em 04/10/2026:** o Argos ganha estudos de
precatórios e processamento de grandes volumes de dados em planilha, como funcionalidade
adicional à vigilância dos tribunais para o AtlasPen. A pergunta que fica: **por qual
cenário começar?**

## Por que é outro bicho

Tudo o que o Argos faz hoje é texto: baixa, confronta com um léxico, tria. Precatório é
**tabela**. O valor não está em achar a palavra, e sim em quatro coisas que o Argos ainda
não faz:

| Precisa | O Argos tem? |
|---|---|
| ler tabela de PDF, XLSX e HTML de dezenas de tribunais, cada um com seu layout | só HTML (`lista`); PDF e XLSX, não |
| normalizar para um esquema único: número do precatório, ente devedor, natureza, data de apresentação, valor, posição | não; hoje o "esquema" é o léxico |
| comparar retratos no tempo: quem subiu na fila, quem foi pago, quem entrou | em parte: o `lista` dá id novo à linha que muda, mas não diz o que mudou |
| validar e relatar a qualidade do dado: número CNJ com dígito verificador, valor em reais, data | não; o Dikemetria tem (`referencias.py`, `valores.py`) |

O que **já serve** sem mudança: o cliente HTTP educado (`robots.txt`, limite, bloqueio por
país), a captura com sentinela, o estado com pendentes, a proveniência (URL, data e hash
de cada retrato) e a disciplina de nunca afirmar o que não leu.

## O que é público

- **Listas de ordem cronológica por ente devedor.** A Resolução CNJ 303/2019 (arts. 7º, 12
  e 15) manda cada tribunal organizar e publicar a fila por entidade devedora, **sem
  identificar o beneficiário** (art. 12, § 3º). Exemplos: o TJSP publica, por ente,
  ordem cronológica, ordem crescente de valor (acordos e leilões) e prioridades, com
  atualização mensal por volta do dia 5
  ([TJSP](https://www.tjsp.jus.br/Precatorios/Precatorios/Faq)); o TJPI publica um PDF
  por ente ([exemplo](https://www.tjpi.jus.br/sapre/static/listas/ordem_cronologica_ente_2209005.pdf)).
- **Mapa anual** da dívida de cada ente, publicado pelos tribunais até 31 de março do ano
  seguinte.
- **Regime especial** (EC 109/2021): estados e municípios em mora pagam até 2029, com
  depósito mensal de percentual da receita corrente líquida e plano anual de pagamento
  homologado pelo tribunal; os planos e termos de homologação saem publicados.
- **Federais**: os TRFs mandam ao CJF as bases de precatórios para cada orçamento
  (Portaria CJF 199/2023); o que vai ao ar, e em que formato, varia por TRF.

Nada disso foi sondado ainda. Antes de qualquer código, a primeira tarefa é a mesma do
STF: abrir, de IP brasileiro, as fontes do cenário escolhido e gravar uma resposta real
de cada uma.

## Cenários concretos

Cada um com quem usa, a pergunta, a fonte, a saída e o que exigiria construir. Estão em
ordem de tamanho, do menor para o maior.

### A. A fila do cliente

**Quem:** advogado ou escritório com precatórios de clientes contra um ou poucos entes.
**Pergunta:** "meu precatório andou na fila este mês? foi pago? o ente está depositando?"
**Fonte:** a lista cronológica do ente no tribunal, mensal.
**Saída:** relatório mensal por número de precatório: posição anterior, posição atual,
pago ou não, e o total liberado pelo ente no mês.
**Exige:** leitor de tabela do tribunal escolhido (um, para começar), retrato mensal
guardado, diferença entre retratos por número de precatório.
**Por que primeiro:** é pequeno de ponta a ponta e exercita as duas peças difíceis
(tabela de PDF ou XLSX, e diferença no tempo) com uma fonte só. Identifica por número de
precatório, que é o que a lista publica; nome de credor nunca entra.

### B. O ente que não paga

**Quem:** pesquisa, jornalismo de dados, Defensoria, OAB.
**Pergunta:** "quanto o município X deve, a que ritmo paga, e fecha a conta até 2029?"
**Fonte:** listas mensais, mapa anual e planos de pagamento do regime especial.
**Saída:** série histórica por ente: estoque, pagamentos, fila média em anos, distância
entre o ritmo atual e o necessário para quitar no prazo.
**Exige:** tudo de A, para muitos entes, mais o mapa anual (outro layout) e um esquema
de série histórica. É jurimetria: conversa com o Dikemetria.

### C. As planilhas gigantes

**Quem:** quem já tem os dados, mas em arquivos inconsistentes: dezenas de XLSX de
tribunais diferentes, colunas com nomes diferentes, valores como texto, datas em três
formatos, números de processo com e sem máscara.
**Pergunta:** "quero uma tabela só, limpa, e saber o que estava sujo."
**Fonte:** os arquivos que a pessoa já tem.
**Saída:** tabela canônica (CSV e Parquet) com proveniência por linha (arquivo, aba,
linha de origem) e relatório de qualidade: linhas descartadas com o motivo, valores
corrigidos com o antes e o depois, duplicatas, números CNJ inválidos. É a mesma
disciplina da triagem do Argos (descarte nomeado), aplicada a célula em vez de texto.
**Exige:** mapeamento de colunas declarado em arquivo (como o léxico: dado, não código),
validadores (dígito do CNJ, moeda, data), deduplicação.
**Observação:** este cenário não precisa de rede nem de vigilância. É o mais útil sozinho
e o que menos se parece com o Argos.

### D. A fila como mercado

**Quem:** investidor em cessão de crédito de precatório.
**Pergunta:** "quais precatórios estão perto de ser pagos e por quanto se negociam?"
**Fica fora, por política.** Achar o credor exige cruzar a lista (que não identifica
beneficiário, por determinação do CNJ) com processos e outras fontes. É exatamente o
cruzamento para montar perfil de pessoa que o README do Argos veda. Os cenários A, B e C
não precisam disso.

## Onde isso mora

**No Argos** (decisão de 04/10/2026), em duas camadas:

- **Peças gerais**: leitura de tabela (PDF e XLSX), retrato tabular guardado, diferença
  entre retratos, validadores (número CNJ, moeda, data). Servem também à vigilância dos
  tribunais: as listas do STF são tabela, e o `lista` já dá o primeiro passo.
- **O domínio dos precatórios**: o esquema, o leitor de cada tribunal, as regras de
  natureza alimentar e prioridade, o regime especial, os relatórios. Mora num
  subpacote próprio, para não se misturar com a vigilância de jurisprudência.

O cenário C (planilhas) não vigia nada: entra arquivo, sai tabela limpa com relatório.
Por isso ganha comando próprio, ao lado de `rodar`, e não uma fonte.

## O que decidir

1. **Qual cenário é real para você**, e quem é a primeira pessoa que vai usar o resultado.
2. **Qual tribunal primeiro.** O TJSP tem o maior volume e lista mensal por ente; um
   tribunal menor seria um teste mais barato.
3. **Se já existem planilhas** (cenário C): ver uma ou duas, mesmo que parciais, define o
   esquema melhor do que qualquer especulação.
