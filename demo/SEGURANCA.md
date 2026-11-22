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
- Suíte completa: **544 testes passaram**; `manage.py check` sem problemas e
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
- Consulta de vulnerabilidades Python realizada em 22/11/2026 pelas APIs públicas
  PyPI e OSV: nenhum alerta retornado para os nove pacotes instalados, sem versões
  ignoradas. O scanner `pip-audit` não concluiu sua execução no container
  descartável; sua execução automatizada permanece pendente. Bibliotecas nativas,
  sistema da imagem, Python e PostgreSQL não foram varridos. Não houve pentest externo.
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
- Linhas expiradas continuam sendo reutilizadas para a mesma chave. O comando
  `limpar_limites_acesso` implementa limpeza manual, com conferência por padrão
  e retenção padrão de 24 horas após a expiração. A exclusão exige `--executar`
  e autorização para o banco alvo; nenhuma exclusão foi executada no banco local.
  Não há limpeza automática nem agendamento. Veja o uso em `APRESENTACAO.md`.

### Limpeza controlada dos contadores — 22/11/2026

- Mantém contadores ativos e expirados dentro da retenção. O corte é fixado no
  início da execução; só registros com expiração anterior ou igual a esse corte
  são elegíveis. A retenção pode ser configurada, com mínimo de uma hora.
- Limita cada execução a 1000 contadores por padrão, configurável de 1 a 10000,
  com transações em lotes de até 100. A conferência também respeita o limite.
- Usa `select_for_update(skip_locked=True)` no PostgreSQL, ignora linhas em uso
  e mantém a condição de expiração no DELETE. Não reinicia bloqueios ativos nem
  apaga um contador que está sendo renovado por outra transação.
- Mostra somente corte, retenção e quantidades; não imprime chaves, IPs ou e-mails.
  Os contadores não substituem um registro de auditoria das tentativas de login.
- Doze testes adicionais cobrem conferência, corte exato e precisão, retenção,
  limites, repetição, múltiplos lotes, argumentos inválidos, tabela vazia,
  preservação de usuários e bloqueios ativos, além de concorrência real no banco.
- Testes de exclusão executados somente em PostgreSQL e arquivos isolados.
  Posteriormente, em 22/11/2026, a imagem foi disponibilizada no web local,
  preservando rede, aliases, porta, ambiente e volumes, sem reiniciar o PostgreSQL.
  Não havia migrations pendentes; o web foi iniciado diretamente sem o entrypoint
  que aplica migrations. Os arquivos de configuração e dependências não mudaram.
- Conferência local com `PGOPTIONS=-c default_transaction_read_only=on`, sem
  `--executar`: 1 contador elegível pelas 24 horas de retenção, nenhum excluído.
  Histórico de migrations e contadores preservados; `manage.py check` sem
  problemas e homepage, login e busca respondendo HTTP 200. Nenhum agendamento
  foi ativado. Detalhes operacionais em `APRESENTACAO.md`.

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

## Auditoria de dependências Python — 22/11/2026

O inventário foi obtido com `importlib.metadata` no container web em execução,
sem carregar configurações ou consultar o banco. As cinco dependências diretas
coincidem com `requirements.txt`; o inventário inclui também dependências
transitivas, a distribuição binária do psycopg e o instalador pip.

| Pacote instalado | Versão |
| --- | --- |
| Django | 6.1.2 |
| djangorestframework | 3.18.3 |
| psycopg | 3.3.6 |
| psycopg-binary | 3.3.6 |
| pillow | 13.0.0 |
| django-environ | 0.14.0 |
| asgiref | 3.12.1 |
| sqlparse | 0.6.0 |
| pip | 26.2.1 |

### Método e resultado

- Para cada pacote/versão, consulta HTTPS a
  `https://pypi.org/pypi/{pacote}/{versao}/json`: todas as nove versões foram
  reconhecidas, com `yanked=false` e lista `vulnerabilities` vazia.
- Consulta HTTPS POST a `https://api.osv.dev/v1/querybatch`, com nove consultas
  contendo somente nome, versão e ecossistema `PyPI`: nove resultados sem alertas,
  sem erros ou indicação de paginação adicional.
- Nenhuma versão foi ignorada. Não foi encontrada indicação de atualização
  corretiva pelas respostas consultadas. Isso não é garantia de ausência de
  vulnerabilidades: depende da cobertura e atualização das bases, que podem
  compartilhar suas fontes de advisories.
- Nenhuma dependência, imagem de serviço, configuração, chave ou dado local foi
  alterado. A consulta externa enviou somente nomes e versões de pacotes públicos.

### Limitações e acompanhamento

- A tentativa de executar `pip-audit` em um container descartável não completou
  a instalação/consulta externa. Portanto, **não houve execução bem-sucedida do
  scanner**; os resultados acima são das consultas estruturadas às APIs, não um
  relatório emitido pelo `pip-audit`. A ferramenta não foi instalada no projeto.
- Não foi verificada a integridade dos artefatos instalados contra os arquivos
  distribuídos no PyPI, nem feita resolução de novas versões ou atualização.
- A análise abrange o ambiente Linux do container. Não é uma auditoria de uma
  instalação Python nativa no Windows ou de pacotes opcionais não instalados.
- O runtime observado foi Python 3.14.8. A análise dos pacotes PyPI não cobre
  esse runtime, o PostgreSQL, o sistema Linux da imagem ou bibliotecas nativas
  embarcadas, como libpq e componentes de processamento de imagens.
- Repetir as consultas antes de mudanças de dependências e acompanhar avisos dos
  mantenedores. Automatizar o scanner e avaliar a imagem base são tarefas futuras;
  correções de versão devem ser entregues com testes e sem atualização indiscriminada.
