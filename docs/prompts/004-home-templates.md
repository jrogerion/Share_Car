# Etapa 4 — Home page e template base

Solicitação: criar um template base para a Home, com herança de templates e
organização por aplicativo (`app/templates/app/`), além da URL e da view
estáticas, sem lógica de backend.

Entregas:

- `apps/core/` — novo app para páginas gerais do site;
- `apps/core/templates/core/base.html` — estrutura comum, navbar, rodapé e
  blocos reutilizáveis;
- `apps/core/templates/core/home.html` — Home que estende `base.html`;
- `apps/core/views.py` — `HomeView` baseada em `TemplateView`, sem contexto;
- `apps/core/urls.py` e `config/urls.py` — rota `core:home` em `/`;
- `static/css/base.css` — estilos da Home e do layout;
- `config/settings.py` — inclusão de `apps.core` e `STATIC_URL` absoluto.

Decisão: usar um app `core` para hospedar o template base e a página inicial,
seguindo o exemplo do enunciado e evitando acoplar uma página geral a um app de
domínio (contas, veículos etc.). Nenhum model, formulário ou consulta foi
adicionado.

Validação: `manage.py check` sem erros; `GET /` retornou 200; a resposta usou
`core/home.html` e `core/base.html`; o CSS foi localizado por `findstatic`;
layouts desktop e mobile foram conferidos em capturas de tela.
