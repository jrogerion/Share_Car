# Cenário fictício para apresentação

O comando `criar_demo` cria exclusivamente dados demonstrativos. Só funciona com
`DEBUG=True` e confirmação explícita do banco local. Não cria administradores,
não altera a configuração de comissão e não modifica contas preexistentes.
Documentos e vistorias são imagens geradas com a indicação **FICTÍCIO — SEM
VALIDADE REAL**. As aprovações são preparadas somente para essas contas de teste.

## Execução

No ambiente Python do projeto:

```sh
python manage.py criar_demo --confirmar-banco-local
```

A senha é solicitada sem aparecer no terminal e será compartilhada somente
pelas contas fictícias. Para execução automatizada, `--senha-stdin` recebe uma
linha pela entrada padrão; nunca passe senhas como argumento ou salve no Git.
O comando não imprime a senha.

Se usar o container local já preparado:

```sh
podman exec -it share_car_web_1 python manage.py criar_demo --confirmar-banco-local
```

O container precisa conter a versão atual do código e `demo/imagens/veiculos/`.
As fotos são copiadas para o armazenamento persistente da aplicação.

## Contas

| E-mail para login | Nome | Papel |
| --- | --- | --- |
| proprietario1@demo.example.com | Ana (demo) | Proprietária |
| proprietario2@demo.example.com | Bruno (demo) | Proprietário |
| proprietario3@demo.example.com | Carla (demo) | Proprietária |
| locatario1@demo.example.com | Diego (demo) | Locatário |
| locatario2@demo.example.com | Elisa (demo) | Locatária |
| locatario3@demo.example.com | Felipe (demo) | Locatário |
| locatario4@demo.example.com | Gabriela (demo) | Locatária |

O domínio `example.com` é destinado a exemplos. Essas contas não possuem caixas
de e-mail reais; não dependa da recuperação de senha por e-mail na apresentação.

## Roteiro

| Veículo / cidade | Locatário | Proprietário | Etapa / demonstração |
| --- | --- | --- | --- |
| Fiat Argo / São Paulo | Diego | Ana | Solicitada: aceitar |
| Honda City / Campinas | Elisa | Ana | Solicitada: recusar |
| Jeep Renegade / São Paulo | Diego | Bruno | Aceita: simular pagamento |
| Fiat Toro / Curitiba | Felipe | Bruno | Paga: cancelar e conferir estorno, antes do check-in |
| Fiat Argo / Belo Horizonte | Gabriela | Carla | Em andamento: registrar check-out |
| Honda City / Rio de Janeiro | Elisa | Carla | Concluída: cada parte avalia |
| Fiat Argo / São Paulo | Felipe | Ana | Concluída e avaliada: mostrar notas e média pública |

Use **Reservas** para abrir cada etapa. Para mostrar avaliações cegas, entre com
Elisa e avalie a reserva concluída do Rio; depois entre com Carla. A nota da outra
parte ficará oculta até Carla também enviar sua avaliação. As operações alteram
o cenário: repetir o comando não desfaz os testes nem restaura as etapas.

Datas são relativas ao dia da primeira criação. A reserva em andamento começa
nesse dia; as concluídas usam datas passadas. Para novos testes de reserva,
escolha períodos futuros não ocupados. O cenário não é atualizado diariamente.

## Limites e cuidados

- Não execute em produção, mesmo habilitando `DEBUG` artificialmente.
- Reexecutar preserva senhas, datas e dados existentes; não existe opção de reset.
- Conflito de nomes/e-mails ou criação parcial interrompe sem sobrescrever dados.
- A criação ocorre em transação; arquivos criados são removidos em caso de erro.
- Fotos ilustrativas e licenças: [créditos](imagens/veiculos/CREDITOS.md).
- Os créditos também são incluídos nas descrições dos anúncios fictícios.
- As fotos de vistoria continuam no armazenamento público, conforme a decisão
  anterior do projeto. Use exclusivamente imagens fictícias nesta apresentação.
