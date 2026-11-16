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

## Backup local (procedimento manual, não executado automaticamente)

Faça backup do banco **e** dos arquivos. Pare temporariamente o serviço web para
evitar que uploads e dados mudem durante a cópia; mantenha o PostgreSQL ligado.
Exemplo para os nomes atuais dos containers Podman, em um terminal Linux:

```sh
umask 077
BACKUP="$HOME/.local/share/sharecar-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
podman stop share_car_web_1
podman exec share_car_db_1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP/banco.dump"
podman cp share_car_web_1:/app/media "$BACKUP/media"
podman cp share_car_web_1:/app/private_media "$BACKUP/private_media"
```

Confira se todos os comandos terminaram sem erro. Ao religar o web, considere a
regra do entrypoint sobre migrations. Guarde configurações e acessos privados
separadamente, com acesso restrito, fora do Git e de pastas compartilhadas.

Para validar uma restauração, use **outro banco e outros diretórios/volumes**:
crie um banco vazio com nome novo, restaure o dump com `pg_restore`, copie as
pastas de mídia e aponte uma instância de teste para esse ambiente. Confira login,
reservas, fotos e documentos. Não sobrescreva o banco nem os volumes atuais.
A criação desse ambiente e a restauração exigem autorização específica; os
comandos acima não comprovam, sozinhos, que um backup é restaurável.

As fotos de vistoria continuam públicas por decisão anterior. Use somente dados
fictícios na apresentação; esta PWA não resolve a pendência do armazenamento.
