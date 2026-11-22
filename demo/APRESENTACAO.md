# Preparação da apresentação local

## Antes de apresentar

1. Inicie o ambiente com antecedência e abra <http://127.0.0.1:8000/>. Use esse
   mesmo endereço nos perfis de navegador para evitar confusão com sessões.
2. Siga o roteiro manual abaixo. Cadastre as contas e os anúncios pela interface;
   não é necessário carregar o gerador de cenário.
3. Separe administrador, proprietário e locatário em três perfis de navegador
   ou navegadores diferentes. Duas janelas anônimas do mesmo navegador podem
   compartilhar a sessão e não garantem isolamento entre contas.
4. Confira as senhas sem registrá-las neste documento, os nomes dos perfis,
   aprovações, fotos fictícias e datas disponíveis. Não use documentos pessoais.
5. Com internet disponível, abra as páginas antes de começar e confira estilos,
   fontes e ícones carregados por CDN. Teste login, busca e fotos com antecedência.
6. Mantenha os containers ligados e o computador sem suspensão automática.

O Compose mantém PostgreSQL, fotos e documentos em volumes distintos. Recriar o
container web não deve apagar esses volumes. **Nunca use `down -v` ou remova
volumes**, pois isso pode apagar o banco e os arquivos.

O entrypoint padrão executa migrations ao iniciar. Antes de reconstruir/subir o
ambiente, revise migrations pendentes e autorize sua aplicação separadamente.
Não trate uma atualização do container como operação que nunca altera o banco.

## Roteiro manual de apresentação (10 a 15 minutos)

### Preparação das contas e do material

- Crie uma conta administrativa com `createsuperuser` e duas contas pessoais
  pelo formulário de cadastro: proprietário e locatário, com e-mails distintos.
  A conta administrativa é exclusiva de administração, não anuncia nem aluga.
- Use nomes preenchidos e dados fictícios de documento/CNH. A validade da CNH
  deve cobrir as datas escolhidas para o aluguel. Prepare imagens JPEG/PNG
  válidas, preferencialmente identificadas como fictícias, antes de apresentar.
- Deixe cada papel autenticado em seu próprio perfil de navegador. O site usa
  e-mail no login; o Django Admin usa o nome de usuário. Evite repetir tentativas
  incorretas: os limites de login permanecem ativos durante a apresentação.
- Escolha datas futuras sem conflito com outras reservas ou bloqueios da agenda.
  Se houver períodos disponíveis cadastrados, confira se cobrem todo o aluguel.
- Decida se preencherá o cadastro completo ao vivo ou apenas mostrará os campos.
  Para caber no tempo, preparar as contas manualmente antes é suficiente; não
  utilize o gerador automático para cumprir esse roteiro.

### Sequência principal

| Etapa | Papel | Ação e resultado esperado |
| --- | --- | --- |
| 1. Objetivo e catálogo | Visitante | Apresentar a proposta acadêmica, navegar no carrossel e usar busca/filtros. Mostrar média e quantidade de avaliações quando já houver notas públicas. |
| 2. Perfis | Proprietário/locatário | Mostrar cadastro manual, completar o perfil do locatário com CNH fictícia e validade e explicar os papéis. Cada usuário acompanha somente seus fluxos pessoais. |
| 3. Documentação | Proprietário e administrador | Proprietário envia documento fictício. Superusuário aprova o documento no painel, liberando o cadastro de anúncio. |
| 4. Anúncio | Proprietário | Cadastrar características, cidade, diária e fotos; conferir a agenda. O anúncio aguarda aprovação. |
| 5. Análises | Administrador | Aprovar anúncio e CNH fictícia do locatário. O anúncio aprovado, ativo e não bloqueado passa a aparecer na busca. |
| 6. Solicitação | Locatário | Escolher datas disponíveis, conferir a estimativa e solicitar. A reserva fica solicitada e ainda não permite pagamento. |
| 7. Aceite | Proprietário | Aceitar a reserva. O locatário passa a poder pagar. O administrador não aceita no lugar do proprietário. |
| 8. Pagamento | Locatário | Simular aprovação, destacando que não existe cobrança real. Conferir as condições da opção escolhida. |
| 9. Vistoria | Locatário | Fazer check-in com pagamento aprovado e depois check-out, com fotos fictícias, combustível e quilometragem de devolução não inferior à inicial. A reserva é concluída. |
| 10. Avaliações | Locatário e proprietário | Enviar a primeira nota e mostrar o sigilo. Enviar a nota recíproca e conferir a liberação das avaliações. A nota do locatário ao proprietário compõe a média pública do veículo. |
| 11. Encerramento | Administrador | Mostrar consulta da reserva e acompanhamento financeiro em modo administrativo. Reforçar separação de papéis, arquivos privados e caráter simulado dos pagamentos. |

Referência de tempo: 2 minutos de introdução/perfis, 3 de anúncio/aprovações,
4 de reserva/pagamento, 3 de vistorias/avaliações e 1 de encerramento. As etapas
representam uma simulação funcional, não uma viagem ou transação real.

### Alternativas e cuidados durante a demonstração

- Se faltar tempo, use reservas previamente preparadas **manualmente**, em etapas
  diferentes, para mostrar pagamento, vistoria e avaliação. Combine antes quais
  contas e reservas serão usadas; não altere registros de outras demonstrações.
- Cancelamento e estorno são opcionais: use outra reserva paga, antes do check-in,
  e não a que será usada para concluir o fluxo principal.
- Depois de um ensaio, confira o estado das reservas. As ações não são desfeitas
  automaticamente; repetir a apresentação exige novas reservas em datas livres
  ou escolher outras previamente preparadas. Não exclua dados nem recrie o banco.
- Não mostre conteúdo de documentos, links de redefinição de senha, `.env`,
  senhas ou configurações privadas durante o compartilhamento de tela.
- Fotos de vistoria só podem ser abertas pelos participantes e pela administração;
  documentos ficam restritos ao próprio usuário e ao superusuário. Não demonstre
  privacidade expondo documentos reais.
- A instalação como PWA é opcional. Só a inclua ao vivo depois de conferir a
  instalação no navegador da apresentação; não substitui o fluxo principal.

### Conferência do roteiro em 22/11/2026

- Suíte completa com **544 testes aprovados**, `manage.py check` sem problemas
  e nenhuma mudança de model pendente. Banco PostgreSQL descartável e arquivos
  isolados; nenhuma migration foi aplicada ao banco local.
- A jornada integrada exercitou cadastro manual pelos formulários, aprovações,
  busca, reserva, aceite, pagamento, check-in/check-out e avaliações recíprocas,
  com CSRF ativo. Trata-se de ensaio funcional automatizado, não de uma
  apresentação manual completa no navegador com as contas locais.
- Conferência do banco local em conexão somente leitura: 1 superusuário ativo,
  4 proprietários com documento aprovado, 6 locatários com CNH aprovada e válida
  na data da consulta e 7 anúncios públicos. A validade precisa ser conferida
  novamente para o período escolhido da apresentação.
- Reservas locais na consulta: 1 solicitada, 3 aceitas, 1 em andamento,
  4 concluídas e 4 canceladas. Esses totais não substituem a escolha das contas,
  datas e reservas adequadas a cada etapa; são apenas a fotografia da conferência.
- Todos os 25 arquivos referenciados foram encontrados no armazenamento.
  Nenhum conteúdo de documento privado foi exibido na revisão.
- Homepage e busca responderam HTTP 200 e foram observadas no Firefox desktop;
  a busca também foi observada em viewport mobile. Fotos, cards, filtros e
  avaliações públicas apareceram nas páginas capturadas.
- Não foram solicitadas ou testadas senhas das contas locais nem realizadas
  operações de cadastro, aprovação, reserva, pagamento ou avaliação nesse banco.
  Instalação PWA no Chrome/Edge e ensaio manual autenticado permanecem pendentes.
- O ensaio manual no banco local depende de combinar previamente quais contas
  e reservas podem ser alteradas. Não há reset automático entre ensaios.

## Instalação como aplicativo

- Acesse o site uma vez com o servidor ligado, usando Chrome ou Edge compatível.
- Use a opção de instalar aplicativo no menu ou na barra de endereços, quando
  disponibilizada pelo navegador. O site não força um aviso de instalação.
- No iOS, a opção fica em Compartilhar → Adicionar à Tela de Início; o suporte
  depende da versão do navegador/sistema. Firefox desktop não oferece a mesma
  instalação nativa de Chrome/Edge.
- Service workers exigem contexto seguro: HTTPS ou a exceção de desenvolvimento
  para `localhost`/loopback. Um endereço HTTP da rede local acessado pelo celular
  não tem essa exceção automaticamente. Não desative a segurança do navegador.

## O que funciona sem conexão

O cache da PWA armazena **somente a tela offline genérica**, sem dados pessoais.
Não armazena páginas autenticadas, anúncios, fotos, documentos, APIs ou operações.
Reservas, pagamentos e vistorias não são enfileirados nem reenviados.

Se o servidor ficar inacessível após a primeira visita, uma navegação GET mostra
o aviso offline. Um envio de formulário pode falhar normalmente; confira a
reserva antes de repetir uma operação cujo resultado seja incerto.

A aplicação **não é totalmente offline**: exige o servidor e o PostgreSQL. Mesmo
rodando localmente, Bootstrap, ícones e fontes ainda usam CDNs; a apresentação
completa precisa de internet ou de uma preparação futura dos recursos locais.
A tela offline, por sua vez, não depende de CDN.

Para verificar o cache, use as ferramentas de desenvolvedor do navegador:
Application/Aplicativo → Service Workers e Cache Storage. O cache
`sharecar-pwa-v1` deve conter apenas `/offline/`. A limpeza de versões antigas
remove somente caches com prefixo `sharecar-pwa-`, nunca os de outros aplicativos.

## Backup local

Faça backup do banco **e** dos arquivos. Suspenda temporariamente o serviço web
para evitar que uploads e dados mudem durante a cópia; mantenha o PostgreSQL
ligado. Evite também alterações no banco por outros terminais durante a cópia.
Exemplo para os nomes atuais dos containers Podman, em um terminal Linux:

```sh
(
set -eu
umask 077
mkdir -p "$HOME/.local/share/sharecar-backups"
BACKUP="$(mktemp -d "$HOME/.local/share/sharecar-backups/$(date +%Y%m%d-%H%M%S)-XXXXXX")"
IMAGEM="$(podman inspect share_car_web_1 --format '{{.Image}}')"
podman pause share_car_web_1
trap 'podman unpause share_car_web_1 >/dev/null' EXIT
podman exec share_car_db_1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP/banco.dump"
podman run --rm --pull=never --network none --user 0 \
  --volumes-from share_car_web_1:ro --entrypoint tar "$IMAGEM" \
  -C /app -cf - media private_media > "$BACKUP/midias.tar"
test -s "$BACKUP/banco.dump"
test -s "$BACKUP/midias.tar"
cd "$BACKUP"
sha256sum banco.dump midias.tar > SHA256SUMS
printf 'Cópia capturada em: %s\n' "$BACKUP"
)
```

O subshell retoma o processo web ao terminar, inclusive em caso de erro, sem
reiniciar seu entrypoint ou executar migrations. Se o terminal for interrompido
de forma que o trap não execute, confira o estado e use `podman unpause
share_car_web_1`. Não use o procedimento se o container já estiver pausado.

Na validação de 22/11/2026, `podman cp` retornou sucesso, mas não trouxe os
arquivos dos volumes. Por isso, o exemplo usa os volumes explicitamente em modo
somente leitura. Um dump/tar não vazio ou um comando com código zero **não
comprova um backup completo**: confira inventário, hashes e restauração.

Guarde configurações e acessos privados separadamente, com acesso restrito,
fora do Git e de pastas compartilhadas. O exemplo não copia `.env` nem credenciais
e não criptografa o backup. As permissões restritas não substituem criptografia
ou uma segunda cópia em outro dispositivo.

Para validar uma restauração, use **outro banco e outros diretórios/volumes**:
crie um banco vazio com nome novo e restaure com `pg_restore --exit-on-error
--single-transaction --no-owner --no-privileges`. Esses dois últimos argumentos
usam o proprietário isolado; não reproduzem permissões e papéis do servidor
original. Não use `--clean` nem a conexão do banco original.

Extraia `midias.tar` somente em diretório vazio isolado, rejeitando links,
arquivos especiais e caminhos fora de `media/` e `private_media/`. Configure a
instância de teste para esse banco e essas mídias; não envie e-mails reais.
Confira sessões autenticadas, reservas, fotos e documentos. Não sobrescreva o
banco nem os volumes atuais. A criação e a restauração desse ambiente exigem
autorização específica.

### Restauração validada em 22/11/2026

- Backup local realizado e restaurado com autorização, usando PostgreSQL 18.6
  descartável em memória, sem rede externa ou portas publicadas.
- Conteúdo de 20 tabelas e valores/estado de 17 sequências iguais à captura;
  estrutura de colunas, índices e restrições conferida pelo catálogo. Posições
  físicas de colunas removidas e casts equivalentes não foram tratados como
  divergências lógicas de esquema.
- SHA-256 dos 25 arquivos conferido entre origem, backup e restauração:
  7 públicos e 18 privados. Todas as 25 referências do banco foram abertas.
- Homepage, busca, sessões autenticadas e consulta de reservas funcionaram.
  Downloads privados autorizados funcionaram, com `no-store`; acesso anônimo
  e acesso de terceiros às fotos de vistoria foram bloqueados.
- A restrição de sobreposição rejeitou duplicatas nos quatro status que ocupam
  agenda; uma reserva cancelada não ocupou a agenda. Esses testes modificaram
  somente o banco descartável, não o original.
- `manage.py check` sem problemas e nenhuma migration pendente na restauração.
  Sessões foram criadas na cópia; nenhuma senha real foi solicitada ou testada.
- O backup aceito tem `manifesto.json` e `validacao.json` com resultado
  `VALIDADO`, em pasta restrita fora do repositório. As tentativas intermediárias
  sem esse resultado não devem ser consideradas backups validados.

A validação não cobre perda do computador, recuperação de segredos, restauração
de papéis PostgreSQL ou um backup criado depois dessa data. Nenhum segredo foi
copiado e o ambiente descartável foi encerrado após os testes.

## Manutenção dos contadores de acesso

O comando `limpar_limites_acesso` confere contadores de login/recuperação que
expiraram há pelo menos 24 horas. Por padrão, **não exclui nada**. A retenção
não é um prazo de bloqueio de conta: os limites de acesso continuam expirando
nas suas janelas normais de 5 ou 15 minutos.

O comando foi disponibilizado no container web local em 22/11/2026. A atualização
substituiu somente o web, preservando explicitamente pod, rede, aliases, porta
local, ambiente e volumes. O PostgreSQL não foi recriado ou reiniciado.

Não havia migrations pendentes. Para não executar migrations na atualização,
a instância atual inicia diretamente com `python manage.py runserver`, sem o
entrypoint padrão. O Dockerfile original continua com migrations automáticas;
futuras recriações pelo Compose exigem revisão dessa configuração e do plano de
migrations, além da preservação dos volumes. Compartilhar o pod, isoladamente,
não garante a mesma rede ou os aliases necessários para resolver o nome `db`.

A conferência local em modo de conexão somente leitura encontrou 1 contador
elegível, com retenção padrão de 24 horas e limite de 1000. O histórico de
migrations e os contadores foram conferidos sem alterações. Nenhuma exclusão
foi executada nem limpeza agendada. Essa quantidade é a observada na conferência,
não um total permanente.

Conferência, sem alteração de registros:

```sh
podman exec share_car_web_1 python manage.py limpar_limites_acesso
```

Para conferir uma retenção maior e limitar a quantidade:

```sh
podman exec share_car_web_1 python manage.py limpar_limites_acesso --retencao-horas 48 --limite 500
```

Somente após autorização específica para excluir contadores no banco alvo,
adicione `--executar` ao comando escolhido. Não é necessário parar o web:
linhas em uso são ignoradas para preservar a renovação de contadores.

- Retenção padrão: 24 horas após a expiração, configurável com mínimo de 1 hora.
- Limite padrão: 1000 registros, configurável de 1 a 10000. O total da conferência
  é limitado a esse valor e não representa necessariamente todo o acervo elegível.
- Exclusão em lotes de até 100, cada um com sua própria transação. Em caso de
  falha posterior, lotes já concluídos permanecem removidos; o comando pode ser
  repetido após conferir a causa.
- Pode haver registros elegíveis remanescentes por causa do limite ou de locks.
  Uma nova conferência permite decidir sobre outra execução autorizada.
- Nenhum usuário, reserva, pagamento, arquivo ou contador ativo deve ser removido.
  A saída não lista chaves, IPs ou e-mails. Não se trata de limpeza de logs gerais.
- O comando não é executado automaticamente no startup, em requisições ou por cron.

## Fotos de vistoria privadas

Novas vistorias usam `private_media/locacoes/`, no volume privado já existente.
Somente participantes da reserva e contas administrativas acessam as fotos pela
rota autenticada. Não publique `private_media` por servidor HTTP/CDN.

Para os arquivos antigos, o comando `python manage.py proteger_fotos_vistoria`
faz apenas uma conferência, sem alterar arquivos ou registros. Com uploads
parados e backup conferido, `--executar` copia os arquivos referenciados e verifica
SHA-256, sem sobrescrever conflitos. `--executar --remover-originais` também
remove os originais públicos após conferir todas as cópias. Essa remoção e a
aplicação da migration `locacoes/0002_fotos_privadas` exigem autorização específica.
O comando pode ser repetido e não altera IDs nem nomes registrados no banco.
Arquivos órfãos não são removidos automaticamente.

O servidor Django de desenvolvimento publica apenas `media/veiculos/`. Em uma
hospedagem futura, configure o servidor de arquivos para essa mesma restrição,
inclusive bloqueando antigos caminhos `media/locacoes/`. Cópias antigas em CDNs
ou backups precisam de revisão separada. Use somente dados fictícios na demo.
