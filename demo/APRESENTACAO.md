# Preparação da apresentação local

## Antes de apresentar

1. Inicie o ambiente com antecedência e abra <http://localhost:8000/>.
2. Confira os acessos privados e o [roteiro do cenário](CENARIO.md).
3. Verifique as datas das reservas: repetir `criar_demo` não atualiza datas nem
   restaura etapas já usadas. Não recrie o banco para contornar isso.
4. Teste login, busca, fotos e uma reserva fictícia antes da apresentação.
5. Mantenha os containers ligados e o computador sem suspensão automática.

O Compose mantém PostgreSQL, fotos e documentos em volumes distintos. Recriar o
container web não deve apagar esses volumes. **Nunca use `down -v` ou remova
volumes**, pois isso pode apagar o banco e os arquivos.

O entrypoint padrão executa migrations ao iniciar. Antes de reconstruir/subir o
ambiente, revise migrations pendentes e autorize sua aplicação separadamente.
Não trate uma atualização do container como operação que nunca altera o banco.

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

Antes de usar no container, confira se sua imagem inclui esse comando. A entrega
de 22/11/2026 não atualizou a imagem web em execução nem agendou limpeza. Atualizar
o container continua exigindo revisão de migrations e preservação dos volumes.

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
