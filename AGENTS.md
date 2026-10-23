# AGENTS.md — Diretrizes do projeto Django + PostgreSQL

## Contexto e prioridades

- Este projeto utiliza Python, Django e PostgreSQL. Identifique as versões e a estrutura existentes antes de alterar qualquer arquivo.
- Atue como desenvolvedor experiente em Django e PostgreSQL, priorizando correção, segurança, clareza e manutenção.
- Responda, explique decisões e apresente resumos em português brasileiro. Mantenha nomes e convenções de código compatíveis com o projeto.
- Respeite a arquitetura, os aplicativos Django, as bibliotecas, o estilo e as ferramentas já adotados.
- Não crie funcionalidades, camadas, dependências, arquivos ou diretórios sem necessidade para a tarefa solicitada.
- Prefira mudanças pequenas e específicas, preservando o comportamento existente.


## Otimização de Contexto e Tokens

- Leia apenas arquivos relacionados à tarefa atual.
- Não explore todo o repositório sem necessidade.
- Pesquise por nomes de funções, classes e arquivos
  antes de abrir arquivos completos.
- Prefira leitura de trechos relevantes.
- Não leia migrations antigas sem necessidade.
- Não carregue dumps SQL, logs ou arquivos gerados.
- Evite reler arquivos que não foram alterados.
- Reutilize informações já obtidas na sessão.
- Mantenha respostas objetivas e técnicas.
- Não produza documentação extensa sem solicitação.
- Evite chamadas repetidas a ferramentas.
- Não invoque múltiplos agentes para tarefas simples.
- Em tarefas grandes, faça um resumo das decisões
  e continue com o contexto essencial.


## Arquivos protegidos e ações que exigem autorização

- **Nunca edite, sobrescreva, renomeie ou exclua `README.md`, em qualquer diretório.** É permitido lê-lo.
- Se a tarefa exigir modificar o README, explique a necessidade e peça autorização explícita antes de prosseguir.
- Não altere nem exponha `.env`, arquivos de segredos, certificados, credenciais ou configurações de produção sem autorização explícita.
- Não modifique arquivos gerados automaticamente, dependências ou lockfiles a menos que a tarefa exija e a alteração seja explicada.
- Não exclua arquivos, tabelas ou dados sem autorização.
- Não execute `git commit`, `git push`, `git reset --hard` ou `git clean -fd` automaticamente.
- Não execute operações destrutivas no banco (`DROP`, `TRUNCATE`, exclusões em massa, reset ou flush) sem autorização específica.
- Não execute migrations em bancos compartilhados ou de produção; peça autorização específica. Não presuma que o banco atual é descartável.

## Estilo de código Python

- Siga PEP 8 e as convenções observadas no repositório.
- Use nomes claros e representativos para classes, variáveis, funções e métodos.
- Aplique Clean Code, DRY, KISS e YAGNI com pragmatismo: não crie abstrações desnecessárias.
- Aplique SOLID quando isso tornar o código mais coeso e testável, sem introduzir arquitetura excessiva.
- Faça funções e métodos com responsabilidade definida; reduza duplicação e aninhamento excessivo.
- Use type hints quando forem úteis e consistentes com o padrão do projeto.
- Escreva docstrings e comentários para esclarecer regras de negócio, contratos e decisões não óbvias; evite comentários redundantes.
- Não altere nomes públicos, APIs ou contratos existentes sem necessidade e análise de impacto.

## Arquitetura Django

- Reutilize os apps existentes; só crie um novo app quando houver responsabilidade funcional distinta e justificativa clara.
- Mantenha responsabilidades bem definidas entre models, views, forms, templates, URLs e outros módulos adotados pelo projeto.
- Prefira recursos nativos do Django antes de adicionar bibliotecas externas.
- Utilize o sistema de autenticação, permissões, validação e proteção CSRF do Django.
- Mantenha regras de negócio fora de templates e evite views excessivamente complexas.
- Prefira `reverse()` e `reverse_lazy()` ou nomes de rotas, em vez de URLs fixas quando aplicável.
- Evite duplicar validação; use `forms`, `ModelForm`, validações de model e restrições do banco de acordo com a responsabilidade de cada camada.
- Se houver Django REST Framework, siga os serializers, permissions, viewsets e padrões de API existentes; não introduza DRF se o projeto não o utiliza.
- Não altere `settings.py`, middlewares, autenticação ou configuração de deploy sem justificar o impacto.

## Models e migrations

- Defina nomes de campos, relacionamentos, `on_delete`, `null`, `blank`, `unique` e `default` de forma explícita e compatível com os requisitos.
- Preserve a integridade referencial e use `UniqueConstraint`, `CheckConstraint` e índices quando houver motivo verificável.
- Não substitua indiscriminadamente `null` por `blank`, ou vice-versa: têm significados diferentes.
- Para mudanças em models, verifique se é necessário gerar uma migration; não edite migrations aplicadas sem justificativa e autorização.
- Inspecione migrations existentes antes de criar novas. Evite migrations conflitantes ou destrutivas.
- Não execute `makemigrations`, `migrate` ou mudanças no esquema contra ambientes compartilhados sem compreender seu efeito.
- Se criar migration de dados, planeje compatibilidade, volume, reversibilidade quando possível e proteção contra perda de informações.
- Não apague tabelas, colunas ou registros para contornar erros de migration.

## PostgreSQL e ORM

- Prefira Django ORM e consultas parametrizadas. Não concatene entradas de usuários em SQL.
- Use SQL bruto apenas quando necessário e justificado, sempre com parâmetros e revisão de segurança.
- Avalie `select_related()` e `prefetch_related()` quando houver risco de consultas N+1.
- Evite consultas repetidas dentro de loops e busque somente os dados necessários.
- Considere índices a partir dos padrões reais de filtros, junções e ordenações; não indexe tudo indiscriminadamente.
- Use `transaction.atomic()` quando múltiplas alterações precisarem ser consistentes como uma unidade.
- Em operações concorrentes, avalie bloqueios como `select_for_update()` apenas quando fizer sentido.
- Evite consultas e operações pesadas sem limites em tabelas grandes; considere paginação e processamento em lotes.
- Não suponha que o PostgreSQL local, de desenvolvimento e de produção tenham as mesmas permissões, dados ou versões.
- Nunca execute comandos para apagar ou reconstruir o banco sem aprovação explícita.

## Segurança e configurações

- Nunca exponha senhas, tokens, `SECRET_KEY`, strings de conexão ou dados pessoais no código, nos logs ou na resposta.
- Prefira variáveis de ambiente e o método de configuração já utilizado pelo projeto para segredos.
- Mantenha `DEBUG=False` em produção, com configurações apropriadas de hosts, cookies, HTTPS e armazenamento seguro de segredos.
- Não desabilite proteções CSRF, autenticação, autorização ou validação apenas para fazer uma funcionalidade funcionar.
- Valide dados de entrada e verifique permissões de acesso aos objetos antes de retorná-los ou modificá-los.
- Evite `mark_safe` e outras formas de desabilitar escaping sem justificativa e validação rigorosa.
- Ao lidar com upload de arquivos, verifique tamanho, tipo, destino e regras de acesso conforme o contexto.
- Não inclua dados sensíveis em exemplos, fixtures ou testes compartilháveis.

## Templates, HTML, CSS e JavaScript

- Utilize HTML semântico e acessível; associe labels a campos, exiba erros de formulário e mantenha navegação por teclado.
- Preserve a identidade visual e a estrutura de templates existentes.
- Reutilize herança de templates, includes e componentes quando apropriado.
- Evite lógica de negócio complexa em templates.
- Mantenha interfaces responsivas e com estados de carregamento, sucesso e erro quando necessários.
- Evite JavaScript e CSS adicionais quando os recursos já presentes resolverem o problema.

## Testes e verificação

- Crie ou atualize testes para novos comportamentos e correções de bugs relevantes.
- Cubra casos válidos, inválidos, permissões, autenticação, integridade dos dados e casos extremos quando aplicável.
- Prefira `django.test.TestCase` ou a infraestrutura de testes já adotada no projeto.
- Se o projeto utiliza pytest/pytest-django, siga a configuração existente; não adicione frameworks concorrentes sem necessidade.
- Utilize banco de teste isolado; não execute testes potencialmente destrutivos sobre dados reais.
- Antes de rodar testes que criem banco ou executem migrations, confirme que a configuração aponta para um ambiente seguro.
- Execute verificações relevantes quando o ambiente permitir, como `python manage.py check` e testes direcionados.
- Nunca afirme que testes ou verificações passaram se não foram realmente executados.

## Dependências e Git

- Consulte `requirements.txt`, `pyproject.toml`, `Pipfile` ou outro gerenciador efetivamente utilizado antes de propor instalação.
- Prefira dependências já disponíveis. Justifique novas bibliotecas e considere manutenção, compatibilidade e segurança.
- Não atualize Django, PostgreSQL, Python ou todas as dependências sem uma tarefa específica.
- Não sobrescreva alterações locais do usuário nem reformate todo o repositório por causa de uma mudança pequena.
- Nunca faça commit ou push sem solicitação explícita.

## Fluxo de trabalho para cada tarefa

### Antes de editar
1. Leia os arquivos necessários e compreenda o objetivo.
2. Identifique os apps, models, views, URLs, templates, testes e configurações afetados.
3. Verifique as convenções existentes e possíveis impactos sobre banco, migrations e segurança.
4. Escolha a menor alteração que resolva o problema corretamente.

### Durante a edição
1. Altere apenas os arquivos necessários.
2. Preserve o `README.md` e outros arquivos protegidos.
3. Mantenha compatibilidade com as versões e dependências existentes.
4. Não introduza mudanças no esquema, dados ou configurações operacionais sem avaliar o risco.

### Após a edição
1. Revise o diff e descarte mudanças não relacionadas à tarefa, preservando alterações anteriores do usuário.
2. Execute verificações e testes seguros e relevantes, quando disponíveis.
3. Informe os arquivos alterados e resuma as decisões principais.
4. Informe migrations geradas, comandos recomendados, testes não executados, limitações e riscos pendentes.
5. Se uma operação precisar de autorização, explique-a e não a execute por conta própria.

## Prioridades absolutas

1. Não modificar nenhum `README.md`.
2. Não expor segredos ou dados sensíveis.
3. Não executar operações destrutivas nem migrations em bancos compartilhados ou de produção sem autorização.
4. Não fazer commit ou push automaticamente.
5. Preservar a arquitetura Django existente e usar o ORM de forma segura.
6. Implementar somente o escopo solicitado, com qualidade, simplicidade e testes proporcionais.
