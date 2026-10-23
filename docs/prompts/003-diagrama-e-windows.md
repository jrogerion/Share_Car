# Etapa 3 — Diagrama do banco e tutorial Windows

Solicitação: gerar uma imagem da estrutura do banco a partir dos models e
colocá-la na pasta de documentação; criar um arquivo separado com o tutorial de
instalação do Docker e Docker Compose no Windows.

Entregas:

- `docs/diagrama-banco-de-dados.png` — diagrama ER com tabelas, colunas, tipos,
  chaves, cardinalidades e constraints;
- `docs/gerar_diagrama_banco.py` — gerador em Pillow, com posições e metadados
  mantidos manualmente a partir dos models;
- `docs/tutorial-docker-windows.md` — WSL 2, Docker Desktop, execução do
  projeto, pgAdmin/psql, persistência e diagnóstico no Windows;
- `.gitattributes` — força LF em scripts e configurações para evitar falhas de
  `entrypoint.sh` em checkouts Windows.

Decisão: manter a pasta `docs/` como pasta de documentação do repositório, já
referenciada pelo README. A imagem foi corrigida para não indicar NULL em
`documento_identidade`, que é `blank=True`, mas não `null=True`.
