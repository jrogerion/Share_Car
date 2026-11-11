# Auditoria do fluxo de pagamento simulado — ShareCar

## 1. Escopo e método

Auditoria realizada **sem alterar nenhum arquivo, sem criar migrations e sem executar operações destrutivas**.

Arquivos e camadas analisados:

- **Backend/controllers:** `apps/pagamentos/views.py`, `apps/pagamentos/services.py`, `apps/pagamentos/forms.py`, `apps/pagamentos/models.py`, `apps/reservas/views.py`, `apps/reservas/services.py`, `apps/locacoes/services.py`, `apps/administracao/views.py`.
- **Rotas:** `config/urls.py`, `apps/pagamentos/urls.py`, `apps/reservas/urls.py`, `apps/core/urls.py`.
- **Frontend/templates:** `apps/pagamentos/templates/pagamentos/pagar.html`, `apps/reservas/templates/reservas/detalhe.html`, `apps/reservas/templates/reservas/minhas.html`, `apps/core/templates/core/pagamento.html`, `page.html`.
- **Banco/migrations:** `apps/pagamentos/migrations/0001_initial.py`, `apps/reservas/models.py`, schema real da tabela `pagamentos_pagamento` no PostgreSQL.
- **Middlewares/configuração:** `config/settings.py`, `LoginRequiredMixin`, `CsrfViewMiddleware`, `AuthenticationMiddleware`.
- **Testes:** `apps/pagamentos/tests.py`, `apps/reservas/tests.py`, `apps/locacoes/tests.py`, `apps/administracao/tests.py`.

Verificações executadas:

- `python manage.py check` → **nenhum problema encontrado**.
- **77 testes** dos apps `pagamentos`, `reservas`, `locacoes` e `administracao` → **todos passaram**.
- Inspeção direta do schema PostgreSQL da tabela de pagamentos.

**Conclusão preliminar:** o fluxo principal está bem protegido no nível HTTP e no banco. Não encontrei falha que permita, pelo fluxo atual, pagar reserva de outro usuário, alterar o valor por POST ou criar dois pagamentos aprovados para a mesma reserva. As principais lacunas são de **defesa em profundidade, auditoria/histórico, validação no service e clareza operacional da simulação**.

---

## 2. Resumo por requisito

| # | Requisito | Situação |
|---|---|---|
| 1 | Simular Pix e cartão sem coletar dados financeiros reais | **Atendido** |
| 2 | Somente o locatário responsável pode simular o pagamento | **Atendido no HTTP; parcial no service** |
| 3 | Verificar no servidor se a reserva foi aceita | **Atendido** |
| 4 | Validar no servidor participante, status e valor contratado | **Atendido com ressalvas** |
| 5 | Valor obtido do banco, nunca do formulário/frontend | **Atendido** |
| 6 | Comissão e repasse calculados corretamente | **Atendido no cenário atual; ressalva para taxas > 0** |
| 7 | Impedir mais de um pagamento aprovado por reserva | **Atendido** |
| 8 | Tratamento de recusados e novas tentativas | **Parcial** |
| 9 | Estorno simulado ao cancelar reserva paga | **Atendido no fluxo principal; parcial em auditoria/abrangência** |
| 10 | Identificação clara de simulação, sem integração real | **Atendido na interface; parcial no backend/operacional** |

---

## 3. Análise detalhada por requisito

### Requisito 1 — Simulação via Pix e cartão, sem dados bancários ou financeiros reais

**Situação: Atendido.**

Evidências:

- `apps/pagamentos/models.py:6-8` define os meios `PIX = "pix"` e `CARTAO = "cartao"`.
- `apps/pagamentos/forms.py:6-22` contém apenas dois campos: `meio` e `resultado`. Não existe campo de número de cartão, CVV, validade, titular, agência, conta ou chave Pix.
- `apps/pagamentos/templates/pagamentos/pagar.html:7` informa: “Nenhum valor real será cobrado”.
- `pagar.html:8-13` exibe aviso: “Pagamento fictício. Não informe dados de cartão, senhas ou códigos reais.”
- Não há integração com gateway, API financeira, QR code Pix real ou processamento externo.
- Busca por termos como `cvv`, `titular`, `número do cartão`, `agência`, `conta corrente` não encontrou campos financeiros no fluxo real.

Observação importante: o resultado “aprovado” ou “recusado” é escolhido pelo próprio usuário no formulário (`forms.py:14-21`). Isso é aceitável **porque o módulo é declaradamente uma simulação**. Se esse código for reutilizado para pagamento real, essa escolha pelo cliente seria uma falha crítica.

Recomendação:

- Criar uma configuração explícita, por exemplo `PAGAMENTO_SIMULADO`, e impedir que o fluxo seja usado como pagamento real sem substituição do service.
- Manter o módulo separado de qualquer futura integração de gateway.

---

### Requisito 2 — Somente o locatário responsável pela reserva pode simular o pagamento

**Situação: Atendido na camada HTTP; parcial em defesa em profundidade.**

Evidências:

- `apps/pagamentos/views.py:59-66`: a busca da reserva é feita com `Reserva.objects.filter(locatario=request.user, pk=pk)`. Portanto, outro usuário recebe **404**, não 403, o que também evita enumeração de reservas.
- `apps/pagamentos/views.py:108-112`: o botão “Simular pagamento” só aparece quando `eh_locatario` é verdadeiro.
- Teste existente: `test_outro_usuario_nao_paga_reserva_alheia` em `apps/pagamentos/tests.py` cobre GET de outro usuário.
- O proprietário do veículo também não consegue pagar pela rota, pois não é o `locatario` da reserva.

Lacuna:

- `apps/pagamentos/services.py:13-20` recebe apenas `reserva`, `meio` e `resultado`; **não recebe o usuário autenticado e não valida se ele é o locatário**. A autorização existe somente na view.
- Hoje isso não é explorável pela rota HTTP, mas qualquer nova chamada ao service — API, comando administrativo, outra view — pode pular a verificação.

Recomendação:

- Passar o usuário autenticado ao service e validar `atual.locatario_id == usuario.pk` dentro de `simular_pagamento`, ou criar uma camada de permissão reutilizável.
- Adicionar teste de POST por outro usuário, não apenas GET.

---

### Requisito 3 — Verificar no servidor se a reserva foi aceita antes de permitir o pagamento

**Situação: Atendido.**

Evidências:

- `apps/pagamentos/views.py:18-32`: tanto GET quanto POST chamam `_bloqueio(reserva)` antes de renderizar ou processar.
- `apps/pagamentos/views.py:68-77`: bloqueia se `reserva.status != Reserva.Status.ACEITA`.
- `apps/pagamentos/services.py:20-25`: o service refaz a consulta com `select_for_update()` e valida novamente o status `ACEITA`, protegendo contra alteração entre a abertura do formulário e o POST.
- Testes: `test_reserva_solicitada_nao_aceita_pagamento` e `test_reserva_ja_paga_nao_abre_novo_pagamento`.

Recomendação:

- Manter a validação duplicada por segurança, mas centralizar as regras em um único método de domínio para evitar divergência futura entre view e service.

---

### Requisito 4 — Validar no servidor o participante, o status e o valor contratado

**Situação: Atendido com ressalvas.**

Evidências:

- **Participante:** validado na view por `filter(locatario=request.user)` (`views.py:59-66`).
- **Status:** validado na view (`views.py:68-77`) e novamente no service (`services.py:20-25`).
- **Valor contratado:** o service usa exclusivamente `atual.total`, `atual.comissao` e `atual.repasse_proprietario`, todos lidos do banco (`services.py:43-45`).

Ressalvas:

- O service **não valida `meio`** contra `Pagamento.Meio`; se for chamado diretamente com um valor inválido, pode gravar um meio não previsto.
- O service **não valida `resultado`**. Em `services.py:33-37`, qualquer valor diferente de `"aprovado"` vira `RECUSADO`, em vez de gerar erro. Pela view isso não ocorre porque o `ChoiceField` do formulário barra valores inválidos, mas o service não é autossuficiente.
- O service não valida o participante, como explicado no requisito 2.

Recomendação:

- Validar explicitamente:
  - `meio in Pagamento.Meio.values`;
  - `resultado in {"aprovado", "recusado"}`;
  - usuário autenticado é o locatário;
  - estado atual do pagamento permite nova tentativa.
- Considerar `full_clean()` ou validação equivalente no service, além do formulário.

---

### Requisito 5 — Valor do pagamento obtido diretamente do banco de dados

**Situação: Atendido.**

Evidências:

- `apps/pagamentos/services.py:20`: a reserva é relida do banco com lock.
- `services.py:43-45`:
  - `valor_bruto = atual.total`;
  - `comissao = atual.comissao`;
  - `repasse_proprietario = atual.repasse_proprietario`.
- O formulário não possui campos de valor (`forms.py:6-22`). Campos extras enviados por POST, como `valor_bruto=1`, são ignorados pelo `Form` e não chegam ao service.
- O template exibe `reserva.total` do banco (`pagar.html:43-47`).
- Restrições de banco reforçam a consistência:
  - `reserva_total_consistente`: `total = valor_diarias + taxas`;
  - `pagamento_soma_consistente`: `valor_bruto = comissao + repasse_proprietario`.
- Teste `test_pagamento_aprovado_grava_valores_da_reserva` confirma que o pagamento recebe os valores da reserva.

Recomendação:

- Adicionar teste de regressão enviando campos adulterados (`valor_bruto`, `total`, `comissao`) no POST e comprovando que o banco ignora esses valores.
- Opcionalmente, armazenar também `percentual_comissao` no pagamento para facilitar auditoria futura.

---

### Requisito 6 — Comissão da plataforma e repasse ao proprietário calculados corretamente

**Situação: Atendido no cenário atual; há uma inconsistência latente se `taxas > 0`.**

Evidências:

- `apps/reservas/models.py:37-42`: comissão = `total * percentual_comissao / 100`, com `ROUND_HALF_UP`.
- `apps/reservas/models.py:44-47`: repasse = `total - comissao`.
- `apps/pagamentos/services.py:43-45`: grava esses valores no pagamento.
- `apps/reservas/services.py:20-27`: usa `ConfiguracaoComissao` ou o padrão de 15%.
- `apps/reservas/services.py:30-51`: calcula a estimativa da reserva.
- `apps/reservas/models.py:49-56`: valida `percentual_comissao` entre 0 e 100, total consistente e comissão não negativa.
- `apps/pagamentos/models.py:27-30`: valida que os valores são não negativos e que a soma fecha.
- Teste `test_pagamento_aprovado_grava_valores_da_reserva` confirma: total 450,00 → comissão 67,50 → repasse 382,50.

Ressalva importante:

- Em `apps/reservas/services.py:38-41`, a comissão da **estimativa** é calculada sobre `valor_diarias`.
- Em `apps/reservas/models.py:39-40`, a comissão da **reserva/pagamento** é calculada sobre `total`.
- Hoje `taxas` é sempre `0.00` em `criar_reserva` (`apps/reservas/services.py:90`), então os valores coincidem.
- Se taxas passarem a ser diferentes de zero, a estimativa e o valor efetivamente registrado no pagamento podem divergir.

Recomendação:

- Definir formalmente a base de cálculo da comissão: `valor_diarias` ou `total`.
- Unificar `estimar_reserva` e `Reserva.comissao` para usar a mesma base.
- Adicionar testes com `taxas > 0` e com arredondamentos de centavos.
- No painel administrativo, exibir também comissão e repasse, não apenas o valor bruto.

---

### Requisito 7 — Impedir mais de um pagamento aprovado para a mesma reserva

**Situação: Atendido.**

Evidências:

- `apps/pagamentos/models.py:16-17`: `reserva = OneToOneField(...)`. O banco cria uma restrição `UNIQUE` em `reserva_id`, então só pode existir **um registro de pagamento por reserva**.
- `apps/pagamentos/services.py:20`: lock pessimista na reserva com `select_for_update()`.
- `services.py:27-31`: se já existe pagamento aprovado, lança `PagamentoInvalido`.
- A transação é atômica (`@transaction.atomic`), e o lock serializa tentativas concorrentes para a mesma reserva.
- O schema real confirma:
  - `pagamentos_pagamento_reserva_id_key` — UNIQUE em `reserva_id`;
  - `pagamento_soma_consistente`;
  - `pagamento_valores_validos`.
- Teste `test_pagamento_aprovado_nao_pode_ser_repetido`.

Observação de modelagem:

- O `OneToOneField` impede **qualquer** segundo pagamento, não apenas um segundo aprovado. Isso atende ao requisito, mas elimina o histórico de tentativas.
- Se no futuro for necessário manter várias tentativas com apenas uma aprovada, será preciso trocar por `ForeignKey` + constraint parcial única para `status = 'aprovado'` e manter a lógica de lock.

Recomendação:

- Manter o lock e a validação.
- Se auditoria de tentativas for necessária, criar modelo de histórico separado, sem enfraquecer a garantia de um único aprovado.
- Adicionar teste de concorrência com `TransactionTestCase` para comprovar o comportamento sob duas requisições simultâneas.

---

### Requisito 8 — Tratamento de pagamentos recusados e novas tentativas

**Situação: Parcial.**

O que funciona:

- `apps/pagamentos/services.py:33-38`: resultado diferente de `"aprovado"` grava `RECUSADO`.
- `services.py:38-47`: usa `update_or_create`, permitindo que uma nova tentativa substitua uma recusa anterior.
- `apps/pagamentos/views.py:52-56`: exibe mensagem de recusa e informa que o usuário pode tentar novamente.
- `pagar.html:35`: documenta que novas tentativas substituem o resultado anterior até a aprovação.
- Teste `test_pagamento_recusado_pode_ser_repetido` cobre recusa seguida de aprovação e confirma que existe apenas um registro.

Lacunas:

- O histórico da recusa é **sobrescrito**. Não há registro de quantas tentativas ocorreram, quando ocorreram ou qual foi o resultado de cada uma.
- O modelo `Pagamento` não possui `criado_em` nem `atualizado_em`.
- Não há limite de tentativas nem throttling; um locatário pode simular indefinidamente.
- Não há máquina de estados explícita. Um pagamento `ESTORNADO` poderia, em tese, ser sobrescrito por uma nova aprovação se a reserva estivesse novamente `ACEITA`. O fluxo normal impede isso porque o estorno só ocorre no cancelamento, mas a regra não está centralizada.
- O status `PENDENTE` existe no modelo (`models.py:11`) mas não é usado pelo fluxo.

Recomendação:

- Definir transições permitidas:
  - sem pagamento → `APROVADO` ou `RECUSADO`;
  - `RECUSADO` → nova tentativa;
  - `APROVADO` → bloqueado;
  - `ESTORNADO` → bloqueado, salvo regra de negócio explícita.
- Registrar histórico de tentativas com data/hora, meio, resultado, valor e usuário.
- Avaliar limite de tentativas por reserva ou intervalo mínimo entre tentativas.
- Adicionar teste de recusa e nova tentativa pela view, não apenas pelo service.

---

### Requisito 9 — Estorno simulado quando uma reserva paga é cancelada

**Situação: Atendido no fluxo principal; parcial em auditoria e abrangência.**

Evidências:

- `apps/reservas/services.py:126-141`: `cancelar_reserva`:
  - bloqueia a reserva com `select_for_update()`;
  - permite cancelamento apenas nos status `SOLICITADA` ou `ACEITA`;
  - altera para `CANCELADA`;
  - atualiza pagamentos aprovados para `ESTORNADO`.
- `apps/reservas/views.py:238-251`: a view de cancelamento é restrita ao locatário.
- `apps/reservas/templates/reservas/detalhe.html:100-102`: informa que o valor foi estornado na simulação.
- `detalhe.html:152-154`: avisa, antes do cancelamento, que o pagamento aprovado será estornado.
- Teste `test_cancelamento_estorna_pagamento_aprovado` em `apps/pagamentos/tests.py`.

Lacunas:

- O estorno é apenas uma mudança de status (`update(status=ESTORNADO)`), sem registro de data, motivo, valor estornado ou usuário responsável.
- Não existe um service de estorno reutilizável; a lógica está embutida em `cancelar_reserva`.
- Só existe o caminho de cancelamento pelo locatário. Se no futuro houver cancelamento pelo proprietário, administrador ou rotina automática, esses caminhos precisarão chamar a mesma lógica.
- Alterações diretas de status no banco ou em futura tela administrativa podem cancelar a reserva sem estornar o pagamento.
- Não há teste de idempotência do estorno nem de cancelamento pela view.

Recomendação:

- Extrair um `estornar_pagamento(reserva, motivo, usuario)` para ser usado por todos os caminhos de cancelamento.
- Registrar `estornado_em`, motivo e valor.
- Garantir que toda transição para `CANCELADA` passe pelo service.
- Adicionar testes de cancelamento com pagamento aprovado, pagamento recusado e tentativa de estorno duplicado.

---

### Requisito 10 — Identificação clara de simulação, sem integração financeira real

**Situação: Atendido na interface do fluxo real; parcial no backend/operacional.**

Evidências:

- `apps/pagamentos/templates/pagamentos/pagar.html:2`: título “Pagamento simulado”.
- `pagar.html:5`: “ShareCar · Pagamento simulado”.
- `pagar.html:7`: “Nenhum valor real será cobrado”.
- `pagar.html:8-13`: aviso explícito para não informar dados reais.
- `apps/reservas/templates/reservas/detalhe.html:95-110`: seção de pagamento com botão “Simular pagamento”.
- `detalhe.html:100-102`: mensagem de estorno “na simulação”.
- `apps/administracao/templates/administracao/painel.html:200`: “Nenhum pagamento simulado” quando não há registros.
- `apps/core/templates/core/pagamento.html` é uma página estática de demonstração, com “Pix de demonstração”, “Total ilustrativo” e “QR code fictício”.
- Não existe integração com gateway, banco ou processador de cartão.

Lacunas:

- O modelo `Pagamento` não possui campo como `simulado=True`, `provider="simulado"` ou equivalente. Quem acessa o banco diretamente não vê uma marcação explícita de simulação.
- O painel administrativo usa o título “Pagamentos recentes”, não “Pagamentos simulados”.
- A rota pública `/reserva/pagamento/` (`apps/core/urls.py:31`) permanece disponível fora do fluxo real e sem exigir login. Ela não grava dados e é claramente ilustrativa, mas pode gerar confusão.
- A documentação em `docs/relatorio-projeto.md:309` ainda afirma que o fluxo de pagamento existe “apenas como protótipo visual”, o que não corresponde mais ao código atual.

Recomendação:

- Adicionar configuração/feature flag de simulação e impedir ativação acidental em produção.
- Marcar explicitamente o pagamento como simulado no modelo ou em um campo de origem.
- Renomear o painel para “Pagamentos simulados recentes”.
- Restringir a página estática de demonstração ao ambiente de desenvolvimento ou removê-la do `urls.py` de produção.
- Atualizar a documentação interna.

---

## 4. Falhas e riscos de segurança identificados

| Risco | Severidade | Situação atual | Recomendação |
|---|---|---|---|
| Resultado do pagamento é escolhido pelo cliente (`resultado=aprovado`) | **Alta se confundido com pagamento real**; aceitável na simulação | Por design, o usuário “aprova” a própria simulação | Manter apenas em ambiente claramente simulado; nunca reutilizar para pagamento real |
| Autorização não centralizada no service | **Média (latente)** | A view protege; o service não verifica o usuário | Validar o locatário dentro de `simular_pagamento` |
| Service não valida `meio` e `resultado` | **Baixa** | O formulário valida, mas chamadas diretas ao service não | Validar no service com choices explícitas |
| Falta de histórico e timestamps do pagamento | **Média para auditoria** | Apenas o último estado é mantido | Adicionar histórico de tentativas e datas |
| Estados `ESTORNADO`/`PENDENTE` sem máquina de estados explícita | **Baixa** | O fluxo normal não explora, mas não há guarda central | Definir transições permitidas |
| Ausência de limite de tentativas | **Baixa** | Usuário pode simular repetidamente | Rate limit ou limite por reserva |
| Página de demonstração pública em `/reserva/pagamento/` | **Baixa** | Não grava dados, mas fica no URLconf de produção | Restringir a `DEBUG` ou remover em produção |
| Ausência de marcação de simulação no backend/admin | **Baixa/Média operacional** | A UI do fluxo real é clara; banco e admin são menos explícitos | Campo de origem e rótulos administrativos |
| Possível divergência de comissão se `taxas > 0` | **Baixa (correção de negócio)** | Hoje `taxas = 0` sempre | Unificar a base de cálculo |
| CSRF, IDOR, SQL injection ou coleta de cartão | **Não foram encontrados problemas** | CSRF ativo, ORM parametrizado, filtro por locatário, sem campos de cartão | Manter e cobrir com testes |

---

## 5. Lacunas de testes

Os testes existentes cobrem bem o caminho feliz e algumas recusas, mas faltam cenários relevantes:

- POST de pagamento por usuário que não é o locatário — hoje só há teste de GET.
- POST para reserva `SOLICITADA`, `RECUSADA`, `CANCELADA`, `EM_ANDAMENTO` ou `CONCLUIDA`.
- POST com campos adulterados (`valor_bruto`, `comissao`, `total`) comprovando que o banco prevalece.
- POST com `meio` ou `resultado` inválidos.
- Recusa seguida de nova tentativa pela view, incluindo mensagem e redirecionamento.
- Cancelamento pela view com pagamento aprovado e verificação do estorno.
- Tentativa de segundo cancelamento ou segundo estorno.
- Comissão e repasse com `taxas > 0`, percentual 0%, 100% e arredondamentos.
- Concorrência real com duas requisições simultâneas para a mesma reserva.
- Check-in após estorno e após recusa.
- Garantia de que o pagamento não expõe dados financeiros ou pessoais no HTML.

---

## 6. Prioridades recomendadas

### P0 — Antes de qualquer uso fora da simulação

1. Criar uma flag/configuração explícita de “pagamento simulado” e impedir que o fluxo seja usado como pagamento real.
2. Centralizar a autorização do locatário no service.
3. Validar `meio`, `resultado` e transições de estado no service.
4. Criar trilha de auditoria mínima: data/hora da tentativa, resultado, valor, comissão, repasse e usuário.

### P1 — Robustez e rastreabilidade

1. Extrair um service único de estorno e usá-lo em todos os caminhos de cancelamento.
2. Adicionar histórico de tentativas ou, no mínimo, timestamps e motivo de estorno.
3. Unificar a base de cálculo da comissão entre estimativa e reserva/pagamento.
4. Completar os testes listados na seção 5.

### P2 — Operação e clareza

1. Rótulos “simulado” no admin e no banco.
2. Restringir a página estática de demonstração ao ambiente de desenvolvimento.
3. Atualizar a documentação interna.
4. Avaliar rate limit para tentativas de pagamento.

---

## 7. Arquivos envolvidos

**Pagamentos**

- `apps/pagamentos/models.py`
- `apps/pagamentos/services.py`
- `apps/pagamentos/views.py`
- `apps/pagamentos/forms.py`
- `apps/pagamentos/urls.py`
- `apps/pagamentos/templates/pagamentos/pagar.html`
- `apps/pagamentos/tests.py`
- `apps/pagamentos/migrations/0001_initial.py`

**Reservas e locações**

- `apps/reservas/models.py`
- `apps/reservas/services.py`
- `apps/reservas/views.py`
- `apps/reservas/urls.py`
- `apps/reservas/templates/reservas/detalhe.html`
- `apps/reservas/templates/reservas/minhas.html`
- `apps/reservas/tests.py`
- `apps/locacoes/services.py`
- `apps/locacoes/tests.py`

**Administração e configuração**

- `apps/administracao/views.py`
- `apps/administracao/templates/administracao/painel.html`
- `config/urls.py`
- `config/settings.py`

**Demonstração estática**

- `apps/core/urls.py`
- `apps/core/templates/core/pagamento.html`
- `apps/core/templates/core/resumo.html`
- `apps/core/templates/core/page.html`
- `docs/prototipo/06-pagamento.html`

---

## 8. Verificações executadas e limitações

Executado:

- `python manage.py check` no container da aplicação → **0 issues**.
- Testes de `apps.pagamentos`, `apps.reservas`, `apps.locacoes` e `apps.administracao` → **77 testes, todos OK**.
- Inspeção do schema real de `pagamentos_pagamento` no PostgreSQL, confirmando:
  - `UNIQUE` em `reserva_id`;
  - `CHECK` de valores não negativos;
  - `CHECK` de soma `valor_bruto = comissao + repasse_proprietario`;
  - chave estrangeira para `reservas_reserva`.

Limitações:

- Esta foi uma auditoria estática e de testes, não um teste de penetração.
- Não foram executadas duas requisições reais concorrentes; a proteção foi avaliada por código e pelo uso de `select_for_update()`.
- O ambiente analisado é o de desenvolvimento; não foram avaliadas configurações específicas de produção.
- Não há gateway real para testar, o que é compatível com o escopo de simulação.

---

## 9. Parecer final

O fluxo atende bem aos requisitos centrais de **simulação**: não coleta dados financeiros, restringe o acesso ao locatário, verifica o status da reserva no servidor, usa valores do banco, calcula comissão e repasse de forma consistente no cenário atual, impede duplicidade de pagamento aprovado e implementa estorno no cancelamento.

O que impede classificá-lo como “pronto para pagamento real” não é uma falha explorável no fluxo HTTP atual, mas a **natureza deliberadamente simulada** — o resultado é escolhido pelo cliente — somada à ausência de auditoria/histórico e à autorização não centralizada no service. Para o objetivo de MVP acadêmico/simulado, o fluxo está consistente; para qualquer evolução futura, as correções P0 e P1 acima são necessárias.
