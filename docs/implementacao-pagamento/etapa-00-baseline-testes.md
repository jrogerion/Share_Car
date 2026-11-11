# Etapa 0 — Baseline de testes de caracterização

## 1. Objetivo

Criar e complementar testes automatizados para congelar o comportamento atual do fluxo de pagamento simulado antes das alterações previstas nas etapas seguintes.

Esta etapa teve como referência:

- a auditoria do fluxo de pagamento simulado;
- o plano de implementação das correções;
- a arquitetura e os testes já existentes no projeto.

**Não houve alteração de lógica de negócio, models, services ou views.** As únicas alterações de código foram em arquivos de teste.

---

## 2. Testes que já existiam

### `apps/pagamentos/tests.py`

Já existiam testes cobrindo parcialmente:

- gravação dos valores da reserva no pagamento;
- recusa seguida de nova tentativa, no nível do service;
- reserva `SOLICITADA` sem permissão de pagamento, no nível do service;
- pagamento aprovado que não pode ser repetido, no nível do service;
- estorno no cancelamento, no nível do service;
- abertura do formulário pelo locatário;
- aprovação de pagamento pelo locatário;
- acesso GET de outro usuário à reserva alheia;
- bloqueio de novo pagamento já aprovado, no nível da view via GET.

### `apps/locacoes/tests.py`

Já existiam testes cobrindo:

- check-in sem pagamento aprovado;
- check-in com pagamento aprovado;
- check-in pela view com pagamento aprovado;
- bloqueio de vistoria por outro usuário.

### `apps/reservas/tests.py`

Já existiam testes cobrindo:

- comissão configurada em 10% para uma nova reserva;
- cancelamento de reserva pelo locatário;
- bloqueio de cancelamento por outro usuário;
- cálculo de valores da reserva.

### `apps/administracao/tests.py`

Já existia teste de atualização do percentual de comissão.

---

## 3. Lacunas identificadas

Antes desta etapa, não havia cobertura adequada para:

- POST de pagamento por outro usuário;
- GET e POST de pagamento pelo proprietário do veículo;
- todos os status de reserva que não são `ACEITA` na camada da view;
- envio de campos adulterados de valor pelo frontend;
- nova tentativa de pagamento recusado pela view;
- estorno de pagamento aprovado por meio da view de cancelamento;
- aprovação de pagamento com cartão pela view;
- check-in com pagamento especificamente `RECUSADO`;
- verificação explícita de que o pagamento replica `reserva.comissao` e `reserva.repasse_proprietario`, além da soma dos valores.

---

## 4. Testes novos criados

### `apps/pagamentos/tests.py`

1. `test_pagamento_respeita_percentual_de_comissao_da_reserva`
   - Cria reserva com percentual de 10% e confirma comissão de R$ 45,00, repasse de R$ 405,00 e soma igual ao valor bruto.

2. `test_pagamento_aprovado_com_cartao_pela_view`
   - Confirma que o meio `cartao` é aceito e persistido pela view.

3. `test_outro_usuario_nao_paga_reserva_alheia_por_post`
   - Confirma 404 e ausência de pagamento quando outro usuário tenta POST.

4. `test_proprietario_nao_paga_reserva_do_proprio_veiculo`
   - Confirma 404 para GET e POST do proprietário do veículo, que não é o locatário.

5. `test_reservas_nao_aceitas_nao_permitem_pagamento_pela_view`
   - Testa GET e POST para reservas `SOLICITADA`, `RECUSADA`, `CANCELADA`, `EM_ANDAMENTO` e `CONCLUIDA`.
   - Usa `subTest` para separar os cinco status.
   - Confirma redirecionamento e ausência de pagamento em todos os casos.

6. `test_campos_adulterados_de_valor_sao_ignorados`
   - Envia `valor_bruto`, `comissao`, `repasse_proprietario`, `total` e `percentual_comissao` falsos no POST.
   - Confirma que o pagamento usa os valores da reserva no banco.

7. `test_pagamento_recusado_permite_nova_tentativa_pela_view`
   - Confirma pagamento `RECUSADO` e, em seguida, nova tentativa aprovada pela view.
   - Confirma que continua existindo apenas um registro de pagamento.

8. `test_cancelamento_pela_view_estorna_pagamento_aprovado`
   - Cria pagamento aprovado, cancela a reserva pela view e confirma `CANCELADA` + `ESTORNADO`.

9. `test_reserva_ja_paga_nao_permite_novo_post`
   - Confirma que um POST após aprovação não cria novo pagamento nem altera o existente.

### `apps/locacoes/tests.py`

10. `test_check_in_com_pagamento_recusado_e_bloqueado`
    - Cria pagamento `RECUSADO` e confirma que o check-in continua bloqueado.

### Testes existentes fortalecidos

- `test_pagamento_aprovado_grava_valores_da_reserva` passou a comparar explicitamente:
  - `pagamento.comissao` com `reserva.comissao`;
  - `pagamento.repasse_proprietario` com `reserva.repasse_proprietario`;
  - a soma `comissao + repasse` com `valor_bruto`.
- `test_locatario_aprova_pagamento` passou a validar os mesmos valores após o POST.
- O helper `criar_reserva` foi ampliado apenas para os testes, aceitando `inicio_dias` e `percentual_comissao`, sem alterar código de produção.

---

## 5. Arquivos de testes modificados

- `apps/pagamentos/tests.py`
- `apps/locacoes/tests.py`

Nenhum model, service, view, formulário, template, migration ou configuração foi alterado.

---

## 6. Cenários validados

| Cenário solicitado | Cobertura |
|---|---|
| Outro usuário não acessa nem paga reserva alheia via GET | Teste existente mantido e executado. |
| Outro usuário não paga reserva alheia via POST | Novo teste adicionado e aprovado. |
| Proprietário não paga reserva do próprio veículo | Novo teste GET + POST adicionado e aprovado. |
| Reservas não aceitas não permitem pagamento | Teste existente no service + novo teste de view para cinco status. |
| Reserva com pagamento aprovado não permite nova aprovação | Testes existentes no service e GET + novo teste de POST pela view. |
| Campos adulterados de valores são ignorados | Novo teste adicionado e aprovado. |
| Pagamento recusado permite nova tentativa | Teste existente no service + novo teste pela view. |
| Cancelamento de reserva paga gera estorno | Teste existente no service + novo teste pela view. |
| Check-in exige pagamento aprovado | Teste existente sem pagamento + novo teste com pagamento recusado. |
| Comissão e repasse permanecem corretos | Testes existentes fortalecidos + novo teste com percentual de 10%. |

---

## 7. Comandos executados

### Verificação do projeto

```bash
docker compose run --rm --entrypoint python --volume "$PWD:/app" web manage.py check
```

Resultado:

```text
System check identified no issues (0 silenced).
```

### Testes dos apps relacionados

```bash
docker compose run --rm --entrypoint python --volume "$PWD:/app" web \
  manage.py test apps.pagamentos apps.reservas apps.locacoes apps.administracao \
  --verbosity 2
```

Resultado:

```text
Ran 87 tests in 9.709s

OK
Destroying test database for alias 'default' ('test_aluguel_carro')...
```

### Observação sobre o ambiente

O serviço `web` do Docker Compose usa uma imagem construída no momento do build e não monta o código-fonte do host. Por isso, a execução inicial no container padrão não considerou os testes recém-adicionados. A execução válida foi feita em um container avulso com o diretório do projeto montado em `/app` e com o entrypoint substituído por `python`, evitando a execução do `migrate` do entrypoint.

O banco de desenvolvimento não foi alterado. O Django criou e destruiu o banco de teste isolado `test_aluguel_carro`.

---

## 8. Resultado dos testes

| Indicador | Resultado |
|---|---|
| Apps executados | `pagamentos`, `reservas`, `locacoes`, `administracao` |
| Total de métodos de teste executados | 87 |
| Testes aprovados | 87 |
| Testes reprovados | 0 |
| Erros | 0 |
| Falhas | 0 |
| `manage.py check` | Sem problemas |

O teste `test_reservas_nao_aceitas_nao_permitem_pagamento_pela_view` contém cinco subcasos de status, todos executados com sucesso dentro do mesmo método.

---

## 9. Problemas identificados

Nenhum problema de implementação foi revelado pelos testes nesta etapa.

As lacunas encontradas eram de **cobertura de testes**, não de comportamento observado:

- faltavam testes de POST para reservas alheias;
- faltavam testes de todos os status não aceitos na view;
- faltava teste explícito de adulteração de valores;
- faltavam testes de retentativa e estorno pela view;
- faltava teste de check-in com pagamento recusado;
- faltava teste de comissão com percentual diferente de 15% no pagamento.

Todos esses cenários foram cobertos e passaram sem necessidade de alteração de produção.

---

## 10. Pendências para as próximas etapas

Esta etapa não corrige as lacunas apontadas na auditoria. Permanecem para as etapas seguintes:

- **Etapa 1:** autorização e validação de entrada dentro do service.
- **Etapa 2:** máquina de estados explícita para pagamentos.
- **Etapa 3:** configuração explícita de simulação.
- **Etapa 4:** timestamps e metadados de auditoria.
- **Etapa 5:** histórico completo de tentativas.
- **Etapa 6:** estorno centralizado e idempotente.
- **Etapa 7:** unificação da base de cálculo da comissão.
- **Etapa 8:** limite de tentativas.
- **Etapa 9:** rótulos e observabilidade no painel administrativo.
- **Etapa 10:** restrição das páginas estáticas de demonstração.
- **Etapa 11:** constraints de banco para `meio` e `status`.
- **Etapa 12:** atualização da documentação interna.

Testes ainda pendentes para etapas futuras:

- chamada direta ao service com `meio` ou `resultado` inválidos;
- tentativa de reativar pagamento `ESTORNADO`;
- concorrência real com `TransactionTestCase`;
- idempotência do estorno;
- limite de tentativas;
- verificação das constraints de `meio` e `status`;
- testes do painel administrativo com os novos rótulos e valores.

---

## 11. Parecer final

A Etapa 0 foi concluída com sucesso.

- Foram adicionados 10 novos métodos de teste e fortalecidos testes existentes.
- A suíte dos quatro apps relacionados executou 87 testes, com 87 aprovações e nenhuma falha.
- O `manage.py check` não encontrou problemas.
- Nenhuma lógica de negócio foi alterada.
- Nenhuma migration foi criada.
- Nenhum dado do banco de desenvolvimento foi modificado.

O baseline está adequado para servir de rede de segurança para a Etapa 1, que deverá ocorrer somente após autorização.
