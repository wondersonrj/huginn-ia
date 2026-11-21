# HUGINN Consultor Fiscal

> **Sugestão orientativa.** A validação e a parametrização final são de responsabilidade do contador responsável. O HUGINN nunca grava tributação no WinThor.

Para cada item da NF-e, o Consultor gera:

- **Sugestão:** carga de ICMS na saída interna, benefício, ato legal com link, tratamento do crédito de ICMS na entrada e PIS/Cofins ou CBS conforme o regime e a data.
- **Validação:** compara a sugestão com o que está no WinThor e dá um destes resultados: `confere`, `diverge` (com o valor estimado em R$), `nao_se_aplica`, `sem_regra` ou `pendente`.
- **Guia:** os passos para ajustar e conferir.
- **Dica de venda:** alíquotas para RJ, SP, MG e ES. É só orientação: ST e DIFAL ficam para o contador.

## Regras (versão `RJ-2026.11`)

| Regra | Carga | Base |
| --- | --- | --- |
| RJ-GERAL-20 | 22% (20% + 2% FECP), a partir de 20/03/2024 | Lei 2.657/1996, Lei 10.253/2023 |
| RJ-CESTA-7 | 7% por redução de base; anulação proporcional do crédito | Lei 4.892/2006, Decreto 32.161/2002 |
| RJ-RIOLOG-7 / RJ-RIOLOG-12 | 7% na cesta básica, 12% nos demais (atacadista exclusivo) | Lei 9.025/2020, Decreto 47.437/2020 |
| RJ-CONV100-ISENTO | Isenção interna, até 31/12/2027 | Conv. ICMS 100/97, Res. SEF 2.884/1997, Conv. 79/2025 |

Quando a nota se encaixa em mais de uma regra, vale esta prioridade: Conv. 100/97 (produto na lista), depois RIOLOG, depois cesta básica, depois a alíquota geral. A data de emissão da nota escolhe a regra vigente.

## Listas de produtos

O HUGINN **não inventa lista de NCM**. Cada benefício tem um JSON mantido pelo contador; o modelo está em `exemplos/lista_modelo.json`. Os prefixos de NCM aceitam de 2 a 8 dígitos, e há uma lista de exclusões. Se a lista ainda não foi aprovada (falta `aprovada_por` ou `aprovada_em`), a confiança da sugestão fica em `media`.

## Perfis

O instalador grava um JSON com os perfis; o modelo está em `exemplos/perfis_modelo.json`. Sem contador cadastrado ou com UF diferente de RJ, o perfil fica bloqueado e o Consultor não sugere nada. Também há alertas para:

- RIOLOG sem atividade de atacadista exclusivo, renúncia a outros regimes ou falta do termo de acordo;
- cliente do Simples Nacional com benefício cadastrado;
- benefício vencido ou que vence em até 30 dias.

## Uso

```
python -m app.fiscal.cli --xml nota.xml --perfis perfis.json --listas pasta_listas \
    [--winthor atual.json] [--saida pasta]
```

A saída é o arquivo `<chave>.huginn.json`, no contrato 1.1. A versão 1.1 acrescenta o status `pendente`, usado quando a tributação do WinThor ainda não foi lida.

## O que não foi verificado

- As regras foram montadas com base em legislação consultada em 21/11/2026 e ainda não foram conferidas com o contador do cliente.
- A comparação com o WinThor usa só a carga efetiva da saída interna. O mapeamento para `PCTABTRIB`/`PCTRIBUT` depende do dicionário dessas tabelas.
- O valor de `diferenca_estimada` é calculado sobre o valor da nota, sem considerar margem.
