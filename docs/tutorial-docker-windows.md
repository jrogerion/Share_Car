# Tutorial — Docker e Docker Compose no Windows

Este tutorial é para colaboradores que usam **Windows 10/11** e vão executar o
projeto com **Docker Desktop + Docker Compose**. O mesmo `docker-compose.yml`
funciona no Linux com Podman; para esse caso, consulte o
[README principal](../README.md).

Ao final, você terá:

- WSL 2 e Docker Desktop instalados e verificados;
- os containers `web` (Django) e `db` (PostgreSQL) em execução;
- acesso ao admin do Django em `http://localhost:8000/admin/`;
- acesso ao PostgreSQL pelo pgAdmin ou pelo `psql`;
- dados preservados ao parar e recriar os containers.

> **Importante:** os comandos abaixo são para **desenvolvimento local**. A
> configuração usa o servidor de desenvolvimento do Django e publica o banco
> apenas em `127.0.0.1`. Não exponha esse banco diretamente à internet.

## 1. Requisitos

- Windows 10 versão 21H2 ou superior, ou Windows 11, 64 bits.
- Virtualização habilitada na BIOS/UEFI.
- Pelo menos 8 GB de RAM (16 GB é confortável).
- Cerca de 20 GB livres em disco.
- Permissão de administrador para instalar o WSL 2 e o Docker Desktop.
- Git para Windows (recomendado) ou o projeto baixado em ZIP.

### Conferir a virtualização

Abra o **Gerenciador de Tarefas** (`Ctrl + Shift + Esc`) → **Desempenho** →
**CPU** e procure **Virtualização**. Deve estar **Habilitada**.

Se estiver desabilitada, reinicie o computador e habilite **Intel VT-x**,
**Intel Virtualization Technology**, **AMD-V** ou **SVM Mode** na BIOS/UEFI.
O nome varia conforme o fabricante.

## 2. Instalar e configurar o WSL 2

O Docker Desktop usa o WSL 2 como backend no Windows. Abra o **PowerShell como
Administrador** e execute:

```powershell
wsl --install
```

Esse comando instala o WSL 2 e, por padrão, uma distribuição Ubuntu. Reinicie o
computador quando solicitado. Depois da reinicialização, o Ubuntu pode pedir a
criação de um usuário e uma senha — isso é local e não tem relação com o banco
do projeto.

Atualize e confirme a versão:

```powershell
wsl --update
wsl --set-default-version 2
wsl --status
wsl --list --verbose
```

A distribuição usada deve aparecer com `VERSION 2`. Se ela estiver na versão 1
(substitua `Ubuntu` pelo nome exibido em `wsl --list --verbose`):

```powershell
wsl --set-version Ubuntu 2
```

Se o comando `wsl --install` não existir ou falhar, habilite os recursos
manualmente no PowerShell como Administrador e reinicie:

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

Depois, repita `wsl --update` e `wsl --set-default-version 2`.

## 3. Instalar o Docker Desktop

1. Baixe o instalador oficial em
   <https://docs.docker.com/desktop/install/windows-install/>.
2. Execute o instalador e mantenha a opção **Use WSL 2 instead of Hyper-V**
   marcada.
3. Reinicie o Windows ao final, se solicitado.
4. Abra o **Docker Desktop**, aceite os termos e pule o login (não é necessário
   para este projeto).
5. Em **Settings → General**, confirme **Use the WSL 2 based engine**.
6. Em **Settings → Resources → WSL Integration**, habilite a distribuição
   Ubuntu (ou a distribuição que você instalou).
7. Clique em **Apply & restart**.

O **Docker Compose** já vem incluído no Docker Desktop; não é preciso instalar
o `docker-compose` separadamente. Use sempre o comando moderno
`docker compose` (com espaço), não o antigo `docker-compose` (com hífen).

Confirme que o Docker Desktop está usando **containers Linux**. Clique no ícone
do Docker na bandeja do sistema; se aparecer a opção **Switch to Linux
containers**, selecione-a.

### Verificar a instalação

Abra um **novo** PowerShell (para carregar o `PATH`) e execute:

```powershell
docker --version
docker compose version
docker info
docker run --rm hello-world
```

O `docker info` deve mostrar um servidor Linux. O `hello-world` deve terminar
com uma mensagem de sucesso. Se o comando `docker` não for reconhecido, feche e
abra o PowerShell novamente; se persistir, reinstale o Docker Desktop.

## 4. Preparar o projeto

### 4.1. Obter o código

Com Git:

```powershell
git clone <URL-DO-REPOSITORIO> C:\dev\ShareCar
Set-Location C:\dev\ShareCar
```

Sem Git: baixe o ZIP, extraia em `C:\dev\ShareCar` e abra o PowerShell nessa
pasta.

Prefira uma pasta local como `C:\dev\ShareCar`, **fora do OneDrive** e sem
acentos ou espaços no caminho. Isso evita bloqueios de arquivo e lentidão.

Confirme que os arquivos principais estão presentes:

```powershell
Get-ChildItem
```

Você deve ver, entre outros, `manage.py`, `Dockerfile` e `docker-compose.yml`.

### 4.2. Criar o `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Preencha obrigatoriamente:

```dotenv
DJANGO_SECRET_KEY=<chave-aleatoria-1>
POSTGRES_PASSWORD=<chave-aleatoria-2>
```

As demais variáveis podem ficar com os valores padrão. Para gerar duas chaves
aleatórias sem instalar Python no Windows:

```powershell
docker run --rm docker.io/library/python:3.14-slim python -c 'import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(32))'
```

Copie a primeira linha para `DJANGO_SECRET_KEY` e a segunda para
`POSTGRES_PASSWORD`. Use os valores **sem espaços, sem aspas e sem `#`**; o
formato hexadecimal gerado acima é o mais seguro para evitar problemas de
interpretação no `.env`.

O `.env` contém segredos e já está no `.gitignore`. **Nunca o envie ao Git.**

### 4.3. Conferir a configuração

Opcionalmente, valide a interpolação do Compose:

```powershell
docker compose config
```

Esse comando imprime as variáveis resolvidas, incluindo senhas. Evite colar a
saída em chats ou issues.

## 5. Subir os containers

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

Na primeira execução, o Docker baixa as imagens do Python e do PostgreSQL e
constrói a imagem da aplicação. Pode levar alguns minutos.

O log do serviço `web` deve mostrar algo como:

```text
Aguardando PostgreSQL...
PostgreSQL pronto.
Applying ... OK
Starting development server at http://0.0.0.0:8000/
```

O entrypoint aguarda uma conexão autenticada com o banco antes de aplicar as
migrações. O serviço `db` também tem healthcheck com `pg_isready`. Se o banco
não ficar pronto em 60 segundos, o Django não inicia; veja os logs:

```powershell
docker compose logs db
docker compose logs web
```

Quando estiver tudo certo, `docker compose ps` deve mostrar os dois serviços
em execução (o `db` como `healthy`).

### 5.1. Criar o usuário administrador

```powershell
docker compose exec web python manage.py createsuperuser
```

Informe usuário, e-mail e senha quando solicitado. Depois acesse:

**<http://localhost:8000/admin/>**

A página inicial `/` deve abrir a Home do projeto; o admin deve abrir
normalmente em `/admin/`.

Na primeira vez, o Windows pode exibir um aviso do firewall. Permita o acesso
em **redes privadas**. Não é necessário liberar redes públicas.

## 6. Acessar o PostgreSQL

O banco é publicado em `127.0.0.1:5432` (ou na porta definida em
`POSTGRES_HOST_PORT`). Ele fica acessível somente pela sua máquina por padrão.

### 6.1. Pelo pgAdmin

1. Instale o **pgAdmin 4** em <https://www.pgadmin.org/download/>.
   Se preferir, procure o pacote com `winget search pgadmin`.
2. Abra o pgAdmin e clique em **Servers → Register → Server**.
3. Preencha:

| Campo | Valor |
| --- | --- |
| **General → Name** | `ShareCar local` |
| **Connection → Host name/address** | `127.0.0.1` |
| **Connection → Port** | `5432` (ou `POSTGRES_HOST_PORT`) |
| **Connection → Maintenance database** | `aluguel_carro` (ou `POSTGRES_DB`) |
| **Connection → Username** | `aluguel_carro` (ou `POSTGRES_USER`) |
| **Connection → Password** | valor de `POSTGRES_PASSWORD` |

4. Salve e abra **Databases → aluguel_carro → Schemas → public → Tables**.

Use o **Query Tool** para executar SQL. Exemplo:

```sql
SELECT * FROM administracao_configuracaocomissao;
```

### 6.2. Pelo terminal (`psql`)

A forma mais simples no Windows é usar o cliente que já existe no container do
PostgreSQL:

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Dentro do `psql`:

```text
\dt
\d+ reservas_reserva
SELECT * FROM administracao_configuracaocomissao;
\q
```

Se você já tiver o cliente `psql` instalado no Windows, também pode conectar
pela porta publicada:

```powershell
psql -h 127.0.0.1 -p 5432 -U aluguel_carro -d aluguel_carro -W
```

Substitua usuário, banco e porta se tiver alterado o `.env`.

Para testar se a porta está aberta:

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 5432
```

O resultado deve conter `TcpTestSucceeded : True`.

### 6.3. Acesso a partir de outra máquina

Por padrão, o banco escuta apenas em `127.0.0.1`. Para permitir acesso de outro
computador da mesma rede, altere no `.env`:

```dotenv
POSTGRES_BIND_ADDRESS=0.0.0.0
```

Recrie os containers com `docker compose up -d` e libere a porta no firewall
do Windows para a rede privada. Use o IP da máquina no pgAdmin/psql. **Não faça
isso em redes públicas** e mantenha uma senha forte; para produção, use uma
camada de rede/VPN e regras de firewall restritas.

## 7. Parar, remover e preservar os dados

Os dados ficam em **volumes nomeados** do Docker, não dentro do container:

- `postgres_data` — banco PostgreSQL;
- `media_data` — fotos enviadas;
- `private_media_data` — documentos de identidade.

O Docker prefixa os nomes com o nome do projeto (normalmente o nome da pasta).

| Operação | Comando | Dados |
| --- | --- | --- |
| Parar sem remover containers | `docker compose stop` | preservados |
| Retomar | `docker compose start` | preservados |
| Reiniciar | `docker compose restart` | preservados |
| Remover containers e rede | `docker compose down` | **preservados** |
| Recriar com os mesmos dados | `docker compose up -d` | preservados |
| Remover containers **e volumes** | `docker compose down --volumes` | **APAGADOS** |

**Nunca use `docker compose down -v` ou `docker compose down --volumes` se
quiser manter os dados.** O mesmo vale para remover volumes manualmente em
**Docker Desktop → Volumes**.

Os volumes podem ser vistos com:

```powershell
docker volume ls
```

### 7.1. Backup e restauração (opcional)

Backup lógico seguro no PowerShell, sem problemas de codificação:

```powershell
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/sharecar.dump'
docker compose cp db:/tmp/sharecar.dump .\sharecar.dump
```

Restauração (para o ambiente de desenvolvimento):

```powershell
docker compose stop web
docker compose cp .\sharecar.dump db:/tmp/sharecar.dump
docker compose exec db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /tmp/sharecar.dump'
docker compose start web
```

### 7.2. Alterou usuário, senha ou nome do banco?

As variáveis `POSTGRES_*` só são usadas pelo PostgreSQL **na primeira
inicialização do volume**. Depois disso, mudar o `.env` não altera o banco já
criado.

- Para trocar a senha, conecte e execute
  `ALTER USER aluguel_carro WITH PASSWORD 'nova-senha';` e atualize o `.env`.
- Para trocar o nome do banco, crie o novo banco via SQL e atualize o `.env`.
- Recriar o volume resolve a divergência, mas **apaga os dados**. Só faça isso
  se puder perder o conteúdo atual.

## 8. Atualizar o projeto

```powershell
git pull
docker compose up -d --build
```

O entrypoint aplica automaticamente as migrações pendentes antes de iniciar o
Django. Se você criou models novos e ainda não gerou as migrações, execute:

```powershell
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

Como o código é copiado para a imagem (não há bind mount do projeto), alterações
em arquivos Python exigem `docker compose up -d --build` para aparecerem no
container.

## 9. Problemas comuns

| Sintoma | Causa provável | Solução |
| --- | --- | --- |
| `docker: command not found` | Docker Desktop não instalado ou `PATH` não carregado | Instale/abra o Docker Desktop e abra um novo PowerShell |
| `Cannot connect to the Docker daemon` | Docker Desktop parado | Abra o Docker Desktop e aguarde o status **Running** |
| `WSL 2 installation is incomplete` | WSL desatualizado | `wsl --update`, reinicie e abra o Docker Desktop |
| `Virtualization support not detected` | Virtualização desligada | Habilite VT-x/AMD-V na BIOS/UEFI |
| `no matching manifest for windows/amd64` | Docker em modo Windows containers | Ícone do Docker → **Switch to Linux containers** |
| `Ports are not available ... 5432` | Porta ocupada | Altere `POSTGRES_HOST_PORT=5433` no `.env` e rode `docker compose up -d`; no pgAdmin use 5433 |
| `Ports are not available ... 8000` | Porta ocupada | Altere `DJANGO_HOST_PORT=8001` e acesse `http://localhost:8001` |
| `password authentication failed` | `.env` diferente do banco já inicializado | Confira a senha; se o volume foi criado com outra, altere via SQL ou recrie o volume (perda de dados) |
| `database "..." does not exist` | Nome do banco mudou após a criação do volume | Crie o banco via SQL ou recrie o volume (perda de dados) |
| `Invalid HTTP_HOST header` | Host não permitido | Adicione o host/IP em `DJANGO_ALLOWED_HOSTS` e rode `docker compose up -d` |
| `entrypoint.sh: not found` ou erro com `^M` | Arquivo com CRLF | Veja a seção de finais de linha abaixo |
| pgAdmin não conecta | Container parado ou porta errada | `docker compose ps`, `docker compose port db 5432`, `Test-NetConnection` |
| Build muito lento | Antivírus/OneDrive ou pouca memória | Mantenha o projeto em `C:\dev`, exclua a pasta do antivírus e ajuste recursos do Docker Desktop |
| Disco cheio | Imagens/camadas antigas | `docker system df`; remova imagens não usadas, mas **não** remova os volumes do projeto |

Para investigar, os logs são a primeira fonte:

```powershell
docker compose ps
docker compose logs --tail=100 db
docker compose logs --tail=100 web
```

### 9.1. Finais de linha (CRLF) e o `entrypoint.sh`

O projeto inclui um `.gitattributes` que força `LF` em scripts e arquivos de
configuração. Se você clonou o repositório antes dessa configuração ou editou
`docker/entrypoint.sh` no Windows, o arquivo pode ter virado CRLF e o container
falhar com `^M`.

A correção mais segura é converter o arquivo para LF no editor. No VS Code,
abra `docker/entrypoint.sh`, clique em **CRLF** no canto inferior direito e
mude para **LF**. Também é possível usar o WSL:

```powershell
wsl sed -i 's/\r$//' docker/entrypoint.sh
```

Para futuros clones, configure o Git para não converter os finais de linha:

```powershell
git config --global core.autocrlf input
```

Depois de corrigir, reconstrua:

```powershell
docker compose up -d --build
```

## 10. Checklist final

- [ ] `wsl --status` mostra WSL 2 e a distribuição está na versão 2.
- [ ] `docker run --rm hello-world` funciona.
- [ ] `docker compose version` responde.
- [ ] O `.env` existe, tem chave e senha preenchidas e não está no Git.
- [ ] `docker compose up -d --build` sobe `db` e `web`.
- [ ] O log mostra `PostgreSQL pronto` e as migrações aplicadas.
- [ ] `http://localhost:8000/admin/` abre.
- [ ] O pgAdmin ou o `psql` conecta em `127.0.0.1:5432`.
- [ ] `docker compose down` e depois `docker compose up -d` mantêm os dados.

## 11. Comandos úteis

```powershell
# Subir/atualizar
docker compose up -d --build

# Status e logs
docker compose ps
docker compose logs -f web
docker compose logs -f db

# Comandos Django
docker compose exec web python manage.py check
docker compose exec web python manage.py showmigrations
docker compose exec web python manage.py createsuperuser

# Banco pelo terminal
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# Parar sem apagar dados
docker compose stop

# Remover containers mantendo volumes
docker compose down

# NUNCA use se quiser manter os dados:
# docker compose down --volumes
```

Para dúvidas sobre o projeto, models, variáveis e execução com Podman, consulte
o [README principal](../README.md).
