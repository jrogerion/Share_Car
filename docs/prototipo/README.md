# ShareCar · Protótipo visual

Telas estáticas do MVP de aluguel de carros entre pessoas (P2P). **Somente visual**: não há backend, banco de dados ou regras implementadas. Os dados são fictícios.

## Como abrir

Dê dois cliques em `index.html` ou abra no navegador:

```
prototipo/index.html
```

Não precisa de servidor. A fonte Inter e os ícones do Bootstrap Icons vêm por CDN, então é necessário estar conectado à internet para vê-los. Sem conexão, o layout continua funcionando, mas sem os ícones.

## Telas

| # | Arquivo | Tela |
|---|---------|------|
| 01 | `01-entrar.html` | Entrar / Criar conta |
| 02 | `02-home.html` | Home / Busca |
| 03 | `03-resultados.html` | Resultados da busca |
| 04 | `04-detalhes.html` | Detalhes do veículo |
| 05 | `05-resumo.html` | Resumo da reserva |
| 06 | `06-pagamento.html` | Pagamento simulado |
| 07 | `07-reservas.html` | Minhas reservas |
| 08 | `08-checkin.html` | Detalhe da reserva + check-in/out |
| 09 | `09-veiculo.html` | Cadastro de veículo |
| 10 | `10-avaliacao.html` | Avaliação |

## Fluxo clicável

`01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 10`

O cadastro de veículo (`09`) é acessado pelo atalho "Tem um carro parado?" na home.

## Padrões visuais

- **Mobile-first**, com largura máxima de 440 px e moldura de celular no desktop.
- Barra inferior fixa: Início · Buscar · Reservas · Perfil.
- Verde-teal como cor da marca; cartões claros, cantos arredondados e sombras suaves.
- Fotos de carros são placeholders em SVG (`assets/car.svg`), com variações de cor.
- Datas fictícias em novembro de 2026.
- Exemplo financeiro alinhado à RN07: 4 diárias × R$ 150 = R$ 600; comissão de 15% (R$ 90); repasse de R$ 510.

## Estrutura

```
prototipo/
├── index.html          # galeria das 10 telas
├── 01-entrar.html      # ... 10 telas
├── css/style.css       # estilos compartilhados
└── assets/car.svg      # ilustração usada nos placeholders
```

## O que ainda não existe

Backend Django, API REST, PostgreSQL, autenticação real, upload real de imagens, PWA (manifesto e service worker) e testes. Esta etapa serve apenas para validar a aparência e a navegação antes do desenvolvimento.
