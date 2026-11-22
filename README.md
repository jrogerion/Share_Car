# ShareCar

Aplicação acadêmica para aluguel de veículos entre pessoas, desenvolvida com
Python, Django e PostgreSQL. Proprietários anunciam seus carros e gerenciam a
disponibilidade; locatários buscam veículos e acompanham suas reservas.

## Objetivos e funcionalidades

- Organizar o fluxo de anúncio, aprovação, reserva e acompanhamento do aluguel.
- Oferecer cadastro, login por e-mail e perfis de proprietário e locatário.
- Controlar documentos, CNH, agenda, vistorias e avaliações entre participantes.
- Disponibilizar um painel administrativo para análises e acompanhamento.
- Simular pagamentos e comissões, **sem cobranças ou transações financeiras reais**.

O projeto utiliza Python 3.14, Django 6.1.2, Django REST Framework, PostgreSQL 18,
Django Templates e Bootstrap. As versões das dependências estão em
[`requirements.txt`](requirements.txt).

## Como executar na sua máquina

O caminho recomendado é usar **containers**. Você não precisa instalar Python
ou PostgreSQL diretamente: o Docker prepara o ambiente da aplicação e do banco.
Não é necessário domínio, Cloudflare ou hospedagem externa.

Você precisará de Git, Docker com suporte a containers Linux, Docker Compose v2
e internet para baixar imagens e dependências. Parte da interface também utiliza
fontes, ícones e estilos por CDN; não considere a experiência totalmente offline.

### 1. Preparar o ambiente e baixar o projeto

#### Linux

1. Instale o Git pelo gerenciador de pacotes da sua distribuição.
2. Instale o [Docker Engine](https://docs.docker.com/engine/install/) e o
   [plugin Docker Compose](https://docs.docker.com/compose/install/linux/),
   seguindo as instruções oficiais para sua distribuição.
3. Inicie o Docker e configure o acesso conforme a documentação oficial. Não
   libere o socket do Docker para todos os usuários; acesso ao daemon concede
   privilégios elevados.
4. Em um terminal, verifique a instalação e faça o clone:

```sh
git --version
docker --version
docker compose version
git clone https://github.com/jrogerion/Share_Car.git
cd Share_Car
cp .env.example .env
```

O comando de cópia é para um **clone novo**. Se já existir um `.env`, preserve-o.
Edite o arquivo com seu editor de texto e siga a etapa 2.

#### Windows

1. Instale o [Git para Windows](https://git-scm.com/downloads/win).
2. Em uma versão do Windows compatível com o Docker Desktop, instale o
   [WSL 2](https://learn.microsoft.com/pt-br/windows/wsl/install). O procedimento
   pode exigir PowerShell como administrador e reinicialização do computador.
3. Instale o [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/),
   habilite o backend WSL 2 e utilize **containers Linux**. A virtualização deve
   estar habilitada. O Docker Desktop já inclui o Docker Compose.
4. Abra o Docker Desktop e aguarde o mecanismo iniciar.
5. Abra um **PowerShell comum**, em uma pasta onde queira guardar o projeto:

```powershell
git --version
docker --version
docker compose version
git clone https://github.com/jrogerion/Share_Car.git
Set-Location Share_Car
Copy-Item .env.example .env
notepad .env
```

A cópia também é somente para um **clone novo**: não sobrescreva um `.env`
existente. Salve o arquivo com esse nome exato, não como `.env.txt`.

Os próximos comandos `docker` são iguais no PowerShell e no terminal Linux.
Não é necessário executar os comandos Linux dentro do PowerShell.

### 2. Configurar o arquivo `.env`

O arquivo `.env.example` contém o modelo de configuração, mas a chave do Django
e a senha do PostgreSQL estão vazias. Gere valores próprios com os comandos
abaixo, que usam Python dentro de um container:

```sh
docker run --rm python:3.14-slim python -c "import secrets; print(secrets.token_urlsafe(64))"
docker run --rm python:3.14-slim python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copie o resultado do **primeiro** comando para `DJANGO_SECRET_KEY` e o do
**segundo** para `POSTGRES_PASSWORD`, substituindo os valores vazios no `.env`.
Não coloque espaços em torno do sinal `=` e não compartilhe esses valores.

Mantenha as demais opções do modelo para o primeiro uso local:

- `DJANGO_DEBUG=True`.
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`.
- `POSTGRES_DB` e `POSTGRES_USER` com os nomes já indicados no modelo.
- Endereços de publicação em `127.0.0.1`, mantendo o acesso restrito à máquina.

O Compose configura a conexão entre os containers usando `db:5432`; você não
precisa substituir esse endereço por um IP. O `.env` é ignorado pelo Git e não
deve ser incluído em commits, capturas de tela ou mensagens públicas.

### 3. Construir e iniciar

Na pasta que contém `docker-compose.yml`, execute:

```sh
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

A primeira execução pode demorar enquanto baixa e constrói as imagens. O
entrypoint aguarda uma conexão autenticada com o PostgreSQL e aplica as
**migrations automaticamente**, criando as tabelas no banco novo.

Quando o servidor estiver pronto, abra:

**<http://127.0.0.1:8000/>**

Use `Ctrl+C` para sair do acompanhamento dos logs; isso não desliga os containers.
Se ainda houver erro ou o servidor não iniciar, confira a seção de problemas comuns.

Para verificar a configuração do Django:

```sh
docker compose exec web python manage.py check
```

### 4. Criar a conta administrativa

Não são criados usuários ou veículos automaticamente. Crie seu administrador:

```sh
docker compose exec web python manage.py createsuperuser
```

Informe um nome de usuário, um **e-mail válido e exclusivo** e uma senha própria.
É normal a senha não aparecer enquanto você digita.

- Para entrar pelo site, em <http://127.0.0.1:8000/entrar/>, use o **e-mail**.
- Para entrar no Django Admin, em <http://127.0.0.1:8000/admin/>, use o **nome de usuário**.
- O painel do ShareCar fica em <http://127.0.0.1:8000/administracao/>.

Mantenha essa conta exclusivamente para administração: contas administrativas
não participam dos fluxos pessoais de anúncio e aluguel. Complete nome e
sobrenome no perfil se desejar identificá-la na interface.

### 5. Cadastrar manualmente as contas e testar o site

Use o formulário **Criar uma conta**, disponível na tela de login, para cadastrar
contas pessoais com e-mails diferentes do administrador. Para testar as duas
partes do aluguel, crie pelo menos um proprietário e um locatário.

1. **Proprietário:** selecione “Quero anunciar meu carro”, complete o perfil e
   envie uma imagem fictícia de documento para análise.
2. **Administrador:** entre em uma janela ou perfil de navegador separado e
   aprove o documento no painel.
3. **Proprietário:** cadastre um veículo, adicione fotos e confira a agenda de
   disponibilidade para as datas que pretende usar nos testes.
4. **Administrador:** analise e aprove o anúncio.
5. **Locatário:** cadastre-se com “Quero alugar carros”, complete os dados
   fictícios de CNH e informe uma validade que cubra as datas do aluguel.
6. **Administrador:** aprove a CNH no painel.
7. **Locatário:** busque o veículo e solicite uma reserva em datas disponíveis.
8. **Proprietário:** aceite ou recuse a solicitação. O administrador não faz
   esse aceite no lugar do proprietário.
9. Continue pela interface para testar pagamento simulado, vistorias e avaliações,
   conforme os requisitos e a sequência apresentados em cada etapa.

Use somente dados e imagens fictícios, sem documentos pessoais reais ou dados
de cartões. Não envie uma imagem inválida apenas renomeando sua extensão.

No modo local padrão, a recuperação de senha mostra o e-mail e o link no console
do serviço web, em vez de enviar uma mensagem real. Consulte os logs apenas no
seu computador; não compartilhe links de redefinição. Para envio real, seria
necessário configurar um serviço de e-mail separadamente.

### 6. Parar, iniciar e preservar os dados

Para parar os serviços:

```sh
docker compose stop
```

Para iniciar novamente os containers existentes:

```sh
docker compose start
```

O banco, as fotos públicas e os arquivos privados ficam em volumes distintos e
persistem ao parar ou recriar os containers. **Não use `docker compose down -v`
nem remova os volumes**: essas ações podem apagar seus dados.

O entrypoint executa migrations ao iniciar o serviço web. Em um ambiente já
utilizado, revise as mudanças e faça backup antes de atualizar o código ou
reconstruir os containers. Alterar `POSTGRES_PASSWORD` no `.env` não troca a
senha de um banco já inicializado; não apague os volumes para contornar isso.

Veja o procedimento de [backup e restauração](demo/APRESENTACAO.md#backup-local).
Ele usa Podman, o ambiente validado pelo projeto; ao usar Docker, os comandos e
nomes dos containers precisam ser adaptados e a restauração deve ser conferida
em um ambiente separado.

## Problemas comuns

| Problema | Como proceder |
| --- | --- |
| `docker compose` não é reconhecido | Instale o plugin Compose v2 no Linux ou atualize/inicie o Docker Desktop no Windows. |
| Não é possível conectar ao Docker | Confira se o serviço/desktop está ativo e se seu usuário tem acesso conforme a instalação oficial. |
| Docker Desktop não inicia | Confira os requisitos do Windows, WSL 2, virtualização e modo de containers Linux. |
| Variável obrigatória ausente | Confira o nome `.env`, sua localização e o preenchimento da chave e da senha. |
| Porta 8000 ou 5432 ocupada | Ajuste `DJANGO_HOST_PORT` ou `POSTGRES_HOST_PORT` no `.env` antes de subir. Se mudar a porta web para 8001, acesse `http://127.0.0.1:8001/`. As portas internas permanecem as mesmas. |
| Site ainda não abre | Confira `docker compose ps` e os logs de `web` e `db`; aguarde a inicialização e procure erros antes de repetir comandos. |
| Login administrativo falha | Use e-mail no site e nome de usuário no Django Admin. Muitas tentativas geram bloqueio temporário; aguarde o prazo indicado. |
| Anúncio ou reserva não é liberado | Confira documento, CNH, aprovação do anúncio, disponibilidade e o papel da conta usada. |

## Observações sobre o ambiente

- Esta configuração é de **desenvolvimento local**, com `DEBUG=True` e servidor
  de desenvolvimento do Django. Não a exponha diretamente à internet.
- Documentos e fotos de vistoria são privados; não publique `private_media` nem
  disponibilize esses arquivos por um servidor de arquivos separado.
- A PWA não torna o sistema totalmente offline: reservas, pagamentos e consultas
  precisam do servidor e do PostgreSQL.
- A construção da imagem e a inicialização em banco vazio foram validadas em
  Linux com Podman, incluindo migrations automáticas, criação do administrador,
  cadastro pelos formulários e login com CSRF ativo. Os passos com Docker e
  Docker Desktop/Windows ainda precisam de validação prática nesses ambientes.
- Para usar Podman no Linux, instale também um provedor Compose e utilize
  `podman` no lugar de `docker`, inclusive `podman compose`. O comportamento do
  provedor deve ser conferido; nomes de containers podem diferir dos do Docker.

Mais informações: [apresentação e backups](demo/APRESENTACAO.md) e
[revisão de segurança](demo/SEGURANCA.md).
