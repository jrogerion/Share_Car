# Relatório do Projeto ShareCar

> Documento de acompanhamento do desenvolvimento.
> Última atualização: 03/11/2026.

## 1. Visão geral

O **ShareCar** é um marketplace de aluguel de carros entre pessoas físicas (modelo
peer-to-peer). O projeto está sendo construído como uma aplicação web em Django com
PostgreSQL, seguindo os requisitos de um MVP acadêmico descrito em
`docs/AluguelCarro — Orientações do Projeto.docx`.

A proposta é permitir que um proprietário anuncie seu veículo, defina preço e
disponibilidade, e que um locatário encontre, reserve, pague e devolva o carro. A
plataforma intermedeia a negociação e retém uma comissão sobre a locação.

O repositório também mantém um protótipo visual estático em `docs/prototipo/`, usado
como referência de interface para os templates Django.

## 2. Objetivo

O objetivo do projeto é entregar um MVP funcional de aluguel de carros P2P, cobrindo:

- cadastro, autenticação e perfis de usuário;
- cadastro de veículos com fotos, preço e agenda;
- busca com filtros e página de detalhes;
- reserva com cálculo de valores;
- pagamento simulado;
- check-in e check-out com fotos, quilometragem e combustível;
- avaliações entre as partes;
- área administrativa;
- funcionamento como PWA instalável.

## 3. Escopo do MVP

O documento de orientações divide o escopo em:

| Categoria | Itens |
| --- | --- |
| Obrigatório (MVP) | Cadastro/login/perfis, cadastro de veículos, busca e filtros, reserva, pagamento simulado, check-in/check-out, avaliações, área administrativa, PWA |
| Opcional (diferencial) | Painéis com indicadores, notificações, contrato de locação, aluguel por horas, política de cancelamento |
| Fora do escopo | GPS/rastreamento, gateway de pagamento real, abertura do carro por IoT, validação oficial de documentos |

Perfis previstos:

- **Proprietário**: anuncia veículos, define preço e agenda, aceita/recusa reservas e recebe repasses.
- **Locatário**: busca, reserva, paga, faz check-in/check-out e avalia.
- **Administrador**: aprova usuários e veículos, acompanha reservas e pagamentos, configura comissão e bloqueia contas.

Um mesmo usuário pode ser proprietário e locatário ao mesmo tempo. No modelo atual,
isso é representado pelos campos `proprietario` e `locatario` em `Usuario`.

## 4. Stack e infraestrutura

| Camada | Tecnologia |
| --- | --- |
| Linguagem | Python 3.14 |
| Framework web | Django 6.1.2 |
| API | Django REST Framework 3.18.3 (instalado, ainda sem endpoints próprios) |
| Banco de dados | PostgreSQL 18 |
| Driver | psycopg 3 |
| Imagens | Pillow |
| Configuração | django-environ |
| Containers | Docker e Docker Compose |
| Front-end | Templates Django, HTML semântico, CSS próprio e Bootstrap Icons |

Infraestrutura:

- `db`: PostgreSQL 18 com volume persistente e healthcheck.
- `web`: aplicação Django servida na porta 8000, com `migrate` automático no entrypoint.
- Volumes separados para banco, mídia pública (`media`) e documentos privados (`private_media`).
- Configurações sensíveis lidas de variáveis de ambiente (`.env`), com exemplo em `.env.example`.

Configurações relevantes em `config/settings.py`:

- `AUTH_USER_MODEL = "contas.Usuario"`.
- Idioma `pt-br` e fuso `America/Sao_Paulo`.
- Documentos pessoais usam o storage privado `documentos`, fora de `MEDIA_URL`.

## 5. Estrutura do projeto

```text
Share_Car/
├── apps/
│   ├── core/            # Home, busca e páginas de demonstração do fluxo
│   ├── contas/          # Usuário customizado, documentos e CNH
│   ├── veiculos/        # Veículos, fotos, agenda, consultas e formulários
│   ├── reservas/        # Solicitações de reserva e valores
│   ├── pagamentos/      # Pagamento simulado, comissão e repasse
│   ├── locacoes/        # Check-in/check-out, km, combustível e fotos
│   ├── avaliacoes/      # Avaliações entre locatário e proprietário
│   └── administracao/   # Configuração de comissão
├── config/              # settings, URLs, WSGI e ASGI
├── docker/              # Entrypoint dos containers
├── docs/                # Orientações, diagrama, protótipo e prompts
├── static/              # CSS e imagens
├── docker-compose.yml
├── Dockerfile
├── manage.py
└── requirements.txt
```

### Responsabilidade dos apps

| App | Responsabilidade atual |
| --- | --- |
| `core` | Home, formulário de busca, página de resultados e templates do fluxo de demonstração |
| `contas` | `Usuario` customizado com papéis, documento de identidade, CNH e status de aprovação |
| `veiculos` | `Veiculo`, `FotoVeiculo`, `PeriodoAgenda`, formulário de busca e consultas ao banco |
| `reservas` | `Reserva` com período, status, diária, taxas, total e comissão |
| `pagamentos` | `Pagamento` com meio, status, valor bruto, comissão e repasse |
| `locacoes` | `RegistroLocacao` e fotos de check-in/check-out |
| `avaliacoes` | `Avaliacao` entre autor e avaliado, vinculada à reserva |
| `administracao` | `ConfiguracaoComissao`, com percentual padrão |

### Arquivos centrais da busca

- `apps/veiculos/consultas.py`: regra de visibilidade pública e todos os filtros.
- `apps/veiculos/forms.py`: `BuscaVeiculoForm`, com opções dinâmicas e validações.
- `apps/core/views.py`: `HomeView` e `ResultadosView` (paginação).
- `apps/core/templates/core/resultados.html`: formulário, resultados, estados e paginação.
- `apps/core/tests.py`: testes de páginas, filtros, privacidade e paginação.

## 6. Modelo de dados

| Entidade | Principais campos e regras |
| --- | --- |
| `Usuario` | Estende `AbstractUser`; papéis `proprietario`/`locatario`; documento privado; CNH; aprovações |
| `Veiculo` | Proprietário, características, cidade, categoria, câmbio, combustível, passageiros, diária, ativo, bloqueado e aprovação |
| `FotoVeiculo` | Imagem vinculada ao veículo |
| `PeriodoAgenda` | Período `inicio`/`fim` com tipo `disponivel` ou `bloqueado` |
| `Reserva` | Veículo, locatário, período, status, diária, valor das diárias, taxas, total e comissão |
| `Pagamento` | Um por reserva; meio, status, valor bruto, comissão e repasse |
| `RegistroLocacao` | Check-in/check-out com quilometragem e nível de combustível |
| `FotoRegistroLocacao` | Fotos do registro de locação |
| `Avaliacao` | Reserva, autor, avaliado e nota |
| `ConfiguracaoComissao` | Percentual único de comissão da plataforma |

Restrições relevantes:

- `preco_diaria > 0` e `passageiros > 0` em `Veiculo`.
- `fim > inicio` em `PeriodoAgenda`.
- Exclusão protegida (`PROTECT`) para usuários e veículos ligados a reservas.
- Diárias calculadas no intervalo `[início, fim)`, com bloqueios prevalecendo sobre disponibilidade.

## 7. O que já foi implementado

### 7.1 Base do projeto

- Estrutura Django com configurações separadas e oito apps de negócio.
- Usuário customizado e modelagem completa do domínio.
- Migrations iniciais aplicadas para todos os apps.
- Diagrama do banco em `docs/diagrama-banco-de-dados.png`.
- Containers `web` e `db` funcionando via Docker Compose.

### 7.2 Interface

- Home com hero, formulário de busca, categorias, destaques, “Como funciona” e chamada para proprietários.
- Templates das etapas do fluxo: login, resultados, detalhes, resumo, pagamento, reservas, check-in, cadastro de veículo e avaliação.
- Layout compartilhado em `core/base.html` e `core/page.html`, com navegação desktop e mobile.
- CSS próprio em `static/css/` e uso de Bootstrap Icons.
- Acessibilidade básica: HTML semântico, labels associados, `aria-current`, estados de erro e foco.
- Páginas de demonstração não aceitam `POST` (retornam 405).

### 7.3 Etapa 1 — Busca real no banco

Substituição dos resultados fictícios por consultas reais:

- Busca por **cidade** com correspondência parcial e sem diferenciar maiúsculas.
- Filtros por **categoria**, **câmbio** e **combustível**, com opções carregadas apenas de veículos públicos.
- Filtro por **capacidade mínima de passageiros**.
- Todos os filtros são combinados na mesma consulta.
- Regra central de visibilidade pública:
  - `ativo = True`
  - `aprovacao = "aprovado"`
  - `bloqueado = False`
- Formulário da Home envia a cidade para `/buscar/` via `GET`.
- Cards exibem dados reais: categoria, cidade, características, câmbio, combustível, passageiros e diária.
- Estado de “nenhum resultado” e tratamento de filtros inválidos.
- Nenhum dado do proprietário é renderizado.

### 7.4 Etapa 2 — Faixa de diária

- Novos campos **Diária mínima** e **Diária máxima**.
- Consulta com `preco_diaria__gte` e `preco_diaria__lte`.
- Faixa combinada com os demais filtros.
- Validação: máximo deve ser maior ou igual ao mínimo.
- Layout dos filtros ajustado para quatro colunas no desktop e responsivo no mobile.

### 7.5 Etapa 3 — Paginação

- Resultados paginados em **6 veículos por página**.
- Controles “Anterior” e “Próxima” com “Página X de Y”.
- Filtros preservados nos links de paginação via `{% querystring %}`.
- Controles desabilitados nas extremidades.
- Total do cabeçalho usa a contagem real do paginador.
- Paginação restrita ao conjunto de veículos públicos.
- Sem controles quando todos os resultados cabem em uma página.

### 7.6 Estado atual em números

- **30 testes automatizados** em `apps.core`, todos passando.
- `python manage.py check` sem erros.
- `makemigrations --check` sem alterações pendentes.
- Nenhuma migration foi necessária nas etapas 1 a 3.

## 8. Rotas disponíveis

| Rota | Nome | Situação |
| --- | --- | --- |
| `/` | `core:home` | Home com busca |
| `/buscar/` | `core:resultados` | Busca real com filtros e paginação |
| `/entrar/` | `core:entrar` | Template de demonstração |
| `/veiculo/` | `core:detalhes` | Template estático, ainda sem veículo específico |
| `/reserva/resumo/` | `core:resumo` | Template de demonstração |
| `/reserva/pagamento/` | `core:pagamento` | Template de demonstração |
| `/reservas/` | `core:reservas` | Template de demonstração |
| `/reserva/vistoria/` | `core:checkin` | Template de demonstração |
| `/anunciar/` | `core:veiculo` | Template de demonstração |
| `/reserva/avaliacao/` | `core:avaliacao` | Template de demonstração |
| `/admin/` | — | Django Admin |

## 9. Critérios de aceite

| Critério | Situação |
| --- | --- |
| Exibir publicamente apenas veículos ativos, aprovados e não bloqueados | **Atendido** na busca |
| Filtros funcionam de forma combinada | **Atendido** |
| Veículos não públicos inacessíveis pelos detalhes | **Pendente** — depende da página de detalhes por veículo |
| Nenhum dado pessoal ou documento do proprietário exposto | **Atendido** nos resultados |
| Navegação da busca para os detalhes mantém o veículo correto | **Pendente** — página de detalhes será implementada na etapa 5 |
| Paginação | **Atendido** |

## 10. Testes e validação

Os testes ficam em `apps/core/tests.py` e cobrem:

- renderização e navegação das páginas de demonstração;
- formulário da Home apontando para a busca;
- exibição apenas de veículos públicos;
- filtros de cidade, categoria, câmbio, combustível e passageiros;
- diária mínima, máxima, faixa e combinação com outros filtros;
- faixa inválida sem quebra da página;
- paginação em 6 itens, segunda página e preservação de filtros;
- veículos não públicos fora da contagem e das páginas;
- ausência de dados do proprietário na resposta;
- ausência de opções de filtro vindas de veículos não públicos;
- `POST` não permitido na busca.

Comandos executados com sucesso:

```bash
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py test apps.core
```

Resultado: **30 testes OK**, nenhuma pendência de migration.

## 11. Como executar

Pré-requisitos: Docker, Docker Compose e um arquivo `.env` baseado em `.env.example`.

```bash
# Subir os containers
docker compose up -d --build

# Acompanhar logs
docker compose logs -f web

# Rodar verificações
docker compose exec -T web python manage.py check

# Rodar os testes
docker compose exec -T web python manage.py test apps.core

# Criar superusuário para o admin
docker compose exec -T web python manage.py createsuperuser

# Encerrar
docker compose down
```

A aplicação fica disponível em `http://127.0.0.1:8000/`.

## 12. Pendências e próximos passos

1. **Página de detalhes por veículo** (`/veiculos/<id>/`), com restrição de acesso aos veículos não públicos.
2. **Fotos e dados completos** do veículo na página de detalhes.
3. **Estados de carregamento** e refinamento dos estados de erro.
4. **Endpoints/API** do módulo de busca e detalhes, com testes.
5. **Disponibilidade por período**: usar as datas da Home para consultar `PeriodoAgenda` e reservas.
6. **Autenticação e perfis**: cadastro, login, recuperação de senha e aprovação de documentos.
7. **Fluxo de reserva e pagamento simulado** com cálculo de diárias, taxas, comissão e repasse.
8. **Check-in/check-out** com upload de fotos, quilometragem e combustível.
9. **Avaliações** e exibição de nota média.
10. **Administração** de aprovações, bloqueios e comissão.
11. **PWA**: manifesto, ícones e service worker.
12. **Dados de demonstração** para que a busca deixe de exibir apenas o estado vazio em desenvolvimento.

## 13. Limitações conhecidas

- O banco de desenvolvimento está sem veículos cadastrados; `/buscar/` mostra o estado vazio até que existam registros públicos.
- `Veiculo` não possui marca, modelo ou ano; os cards usam categoria, cidade e características como identificação.
- A página de detalhes ainda é estática e não recebe um veículo por ID.
- As datas informadas na Home são preservadas na URL, mas ainda não filtram disponibilidade.
- A paginação usa o comportamento padrão do `ListView`: uma página fora do intervalo retorna 404.
- A API está instalada, porém ainda não há serializers, viewsets ou rotas de API.
- O fluxo de reserva, pagamento, check-in e avaliação existe apenas como protótipo visual.

## 14. Situação do versionamento

As alterações das etapas 1 a 3 estão no diretório de trabalho e não foram
commitadas. Também não foi feito `push`. O arquivo `README.md` permanece inalterado.
Nenhuma operação destrutiva no banco foi executada.
