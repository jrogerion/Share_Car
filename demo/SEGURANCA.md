# Revisão de segurança — 22/11/2026

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
- Suíte completa: **532 testes passaram**; `manage.py check` sem problemas e
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
- Proteção contra tentativas automatizadas testada com múltiplos clientes,
  aliases, CSRF válido, cabeçalhos de IP forjados, expiração e conexões
  concorrentes no PostgreSQL.
- Nenhum `.env`, certificado ou arquivo de chave privada foi encontrado entre
  os arquivos rastreados consultados. Isso não equivale a varrer todo o histórico
  Git ou comprovar ausência de segredos em qualquer formato.

## Pendências antes de publicação

O `check --deploy` no ambiente local apontou seis avisos: `security.W004`,
`W008`, `W009`, `W012`, `W016` e `W018`. São necessários revisão de chave secreta,
`DEBUG=False`, HTTPS/proxy confiável, HSTS quando apropriado e cookies seguros.
Não se deve simplesmente ativar flags HTTPS em um ambiente que só atende HTTP.
Alterar a chave pode invalidar sessões e tokens; exige preparação e autorização.

- A proteção de login/recuperação está ativa localmente. A migration
  `contas/0003_limiteacesso` foi aplicada com autorização, e o middleware ativo
  foi conferido no serviço web. Em outro ambiente, criar a tabela antes de
  disponibilizar o novo código.
- Não foi executado scanner externo de CVEs das dependências nem pentest externo.
- Backup/restauração validado em 22/11/2026 em PostgreSQL descartável, com
  comparação de 20 tabelas, 17 sequências e SHA-256 de 25 arquivos. Sessões,
  consultas e permissões privadas conferidas somente na cópia; detalhes em
  `APRESENTACAO.md`. Backup criptografado em outro dispositivo e recuperação
  das configurações/segredos ainda precisam de preparação própria.
- Fotos antigas podem conservar metadados; qualquer reprocessamento retroativo
  precisa de autorização própria e plano de preservação.
- Uma futura hospedagem deve servir apenas fotos públicas de anúncios, nunca
  `private_media`, e impedir cache de conteúdo privado, conforme APRESENTACAO.md.

Esta revisão não é certificação nem garantia de ausência de vulnerabilidades.

## Limitação de tentativas de autenticação

- Middleware após a proteção CSRF, restrito a POST nas rotas de login público,
  login do Django Admin e recuperação de senha, incluindo o alias `/contas/`.
  Os demais fluxos e as permissões de autenticação não foram alterados.
- Login: até 20 envios por IP e 5 por combinação IP/identificador em 5 minutos.
  Recuperação: até 5 por IP e 3 por combinação IP/e-mail em 15 minutos.
  Envios válidos e inválidos contam; login e recuperação têm contadores separados.
- Contadores no PostgreSQL, com transação e bloqueio de linha: funcionam entre
  processos, não dependem de cache em memória e não são reiniciados ao recriar
  o serviço web. A migration apenas cria a tabela, sem modificar contas existentes.
- Na ativação local, o Compose recriou os serviços e o entrypoint padrão aplicou
  a migration antes da consulta do plano. O histórico confirmou somente a nova
  `contas/0003_limiteacesso`; as páginas públicas de login e recuperação, seu
  alias e o login administrativo responderam HTTP 200 após a ativação.
- Bloqueio temporário responde HTTP 429, `Retry-After` e `no-store`, sem verificar
  se a conta existe. Não autentica nem envia e-mail durante o bloqueio.
  Tentativas bloqueadas não estendem a janela e não alteram `is_active`.
- IP e identificador normalizado são usados somente para gerar chaves HMAC;
  não são armazenados em claro na nova tabela, nem a senha é incluída nas chaves.
  Isso não equivale a anonimização absoluta. Rotacionar a chave secreta também
  muda essas chaves e reinicia efetivamente a contagem.
- Usa somente `REMOTE_ADDR`. Não confia em `X-Forwarded-For`, `X-Real-IP` ou
  `Forwarded`. Antes de publicar por proxy/túnel, validar como o IP chega à
  aplicação: se chegar apenas o IP do proxy, todos compartilharão os limites.
  Redes compartilhadas/NAT também compartilham o limite por IP.
- Não há bloqueio global por conta, evitando que um atacante impeça o acesso
  da vítima a partir de outra rede. Como contrapartida, ataques distribuídos
  precisam de proteção adicional no proxy/borda e monitoramento na publicação.
- Linhas expiradas são reutilizadas para a mesma chave, mas não removidas
  automaticamente. Definir retenção e limpeza controlada antes de exposição
  prolongada à internet; nenhuma exclusão de registros foi executada nesta entrega.

## Validação de IPs — 22/11/2026

### Resultado local

- O serviço web está publicado somente em `127.0.0.1:8000`. Não foi identificado
  proxy/túnel entre os containers e processos conhecidos consultados. Nenhum túnel
  foi instalado ou aberto nesta entrega.
- O GET de login no serviço real respondeu HTTP 200. O log padrão consultado
  não informou a origem; não foi adicionado endpoint de diagnóstico ao site.
- Um servidor WSGI descartável, usando a imagem da aplicação, a mesma rede
  Podman e publicação de porta restrita a loopback, recebeu conexões originadas
  em `127.0.0.1` e `127.0.0.2`. Após o encaminhamento, ambas chegaram com o mesmo
  `REMOTE_ADDR`. Isso demonstra compartilhamento de origem nesse caminho local;
  não comprova como chegariam visitantes externos por um futuro túnel.
- Nesse diagnóstico, `ip_da_conexao` permaneceu igual ao `REMOTE_ADDR`, mesmo
  com `X-Forwarded-For`, `X-Real-IP`, `Forwarded` e `CF-Connecting-IP` forjados.
  Foram usadas configurações fictícias, sem conexão ao banco real, e o container
  de diagnóstico foi encerrado.
- Novos testes com sockets HTTP reais, sem o encaminhamento de porta do Podman,
  confirmaram que origens distintas são preservadas e que headers não substituem
  a origem da conexão. Um teste integrado demonstrou o compartilhamento do limite
  por clientes com o mesmo `REMOTE_ADDR`, mesmo com `CF-Connecting-IP` diferente.
  POSTs adversariais e contadores ficaram restritos ao PostgreSQL de teste isolado.
- Não houve mudança na resolução de IP, middleware, publicação, `.env` ou dados
  locais, nem necessidade de migration ou recriação dos serviços existentes.

### Pendência para publicação

A validação externa **continua pendente** até existir uma topologia real de
proxy/túnel. Não basta confiar em `CF-Connecting-IP` por estar usando Cloudflare:
é necessário comprovar quem pode entregar esse header à aplicação.

Antes de liberar acesso externo:

1. Definir o proxy/túnel e verificar o IP da conexão que ele entrega ao backend.
2. Garantir que somente o intermediário autorizado alcance a origem e que ele
   remova/substitua cabeçalhos de IP fornecidos pelo visitante.
3. Se necessário, implementar restauração de IP restrita à origem confiável e
   ao header realmente controlado por ela, com validação de IPv4/IPv6. Não ativar
   confiança global em `X-Forwarded-For` ou escolher simplesmente o primeiro IP.
4. Testar duas redes externas distintas, confirmar contadores separados e testar
   falsificação de headers, inclusive tentativa de acesso direto à origem.

Até essa validação, clientes que cheguem com o mesmo IP de proxy/NAT compartilharão
o limite. Os testes locais não representam certificação de uma publicação futura.
