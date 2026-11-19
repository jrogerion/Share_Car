# Revisão de segurança — 18/11/2026

## Escopo desta entrega

Revisão de código de autenticação, permissões, documentos, imagens de vistoria,
reservas, pagamentos e cache. Regressões executadas em PostgreSQL descartável,
com arquivos fictícios e armazenamento de teste isolado. Não houve ataques ou
testes destrutivos contra os dados locais, nem testes em serviços de terceiros.

## Achados corrigidos

- A ação de bloquear/reativar usuários permitia que staff sem superusuário
  alterasse outras contas administrativas, inclusive reativando um superusuário.
  A verificação agora protege essas contas também em POST direto, com transação
  e bloqueio da linha. Superusuários continuam gerenciando staff.
- Documentos JPEG/PNG não tinham limite próprio de resolução. Novos envios
  passam a aceitar no máximo 20 megapixels, além dos 5 MB já exigidos.
- Novos documentos e fotos de vistoria são recriados sem EXIF, metadados ou bytes
  anexados ao fim do arquivo, preservando a orientação visual. Fotos de vistoria
  recebem nomes aleatórios. Isso é proteção de privacidade e redução de conteúdo
  inesperado, não evidência de execução de código nos downloads anteriores.
- Downloads de documentos recebem proteção de origem e de referrer e tratam
  erros de leitura sem apresentar caminhos internos.
- Alteração de senha, confirmação da alteração e configuração de comissão
  não enviavam `Cache-Control: no-store`. As três telas agora usam `never_cache`,
  alinhando sua proteção de cache às demais páginas privadas.

Os arquivos antigos **não foram reprocessados**. Limites e validações de imagem
continuam no servidor, mesmo que o navegador seja manipulado.

## Verificações

- Os testes de reprodução falharam antes das correções e passaram depois.
- Suíte completa: **512 testes passaram**; `manage.py check` sem problemas e
  `makemigrations --check --dry-run` sem mudanças pendentes no modelo.
- Cobertura adicional: CSRF no bloqueio administrativo, injeção de privilégios
  no perfil, redirecionamento externo no login, resolução e metadados de uploads.
- A suíte também cobre acessos entre contas, documentos/vistorias privados,
  snapshots financeiros, repetição, transições e concorrência dos fluxos.
- A bateria integrada em `apps/core/test_seguranca_integrada.py` verifica
  permissões pelas URLs reais, CSRF em 23 operações, origem externa com token
  válido, GET sem transições e cache privado. Também cobre downloads com
  parâmetros e cabeçalhos forjados, logout, bloqueio de conta com sessão existente,
  campos públicos e escrita proibida na API, valores financeiros adulterados
  e payload SQL tratado como texto. Usa banco e arquivos isolados.
- Nenhum `.env`, certificado ou arquivo de chave privada foi encontrado entre
  os arquivos rastreados consultados. Isso não equivale a varrer todo o histórico
  Git ou comprovar ausência de segredos em qualquer formato.

## Pendências antes de publicação

O `check --deploy` no ambiente local apontou seis avisos: `security.W004`,
`W008`, `W009`, `W012`, `W016` e `W018`. São necessários revisão de chave secreta,
`DEBUG=False`, HTTPS/proxy confiável, HSTS quando apropriado e cookies seguros.
Não se deve simplesmente ativar flags HTTPS em um ambiente que só atende HTTP.
Alterar a chave pode invalidar sessões e tokens; exige preparação e autorização.

- Ainda falta proteção contra tentativas automatizadas de login/recuperação,
  com critérios e armazenamento compartilhado adequados ao ambiente publicado.
- Não foi executado scanner externo de CVEs das dependências nem pentest externo.
- Backup/restauração em ambiente separado ainda precisa ser validado.
- Fotos antigas podem conservar metadados; qualquer reprocessamento retroativo
  precisa de autorização própria e plano de preservação.
- Uma futura hospedagem deve servir apenas fotos públicas de anúncios, nunca
  `private_media`, e impedir cache de conteúdo privado, conforme APRESENTACAO.md.

Esta revisão não é certificação nem garantia de ausência de vulnerabilidades.
