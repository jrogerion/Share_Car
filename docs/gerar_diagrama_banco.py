"""Gera o diagrama da estrutura do banco de dados a partir dos models do projeto.

Uso:
    .venv/bin/python docs/gerar_diagrama_banco.py

Saída:
    docs/diagrama-banco-de-dados.png

Requisitos: Pillow (já listado no ambiente) e as fontes Liberation do sistema.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Configuração visual
# ---------------------------------------------------------------------------

S = 2  # escala de renderização (2x para nitidez)
W, H = 2240, 1500

BG = "#F5F6FA"
INK = "#0F172A"
MUTED = "#64748B"
BORDER = "#E2E8F0"
STRIPE = "#FAFBFD"

FONT_DIR = Path("/usr/share/fonts")
SANS_R = FONT_DIR / "liberation-sans-fonts/LiberationSans-Regular.ttf"
SANS_B = FONT_DIR / "liberation-sans-fonts/LiberationSans-Bold.ttf"
MONO_R = FONT_DIR / "liberation-mono-fonts/LiberationMono-Regular.ttf"
MONO_B = FONT_DIR / "liberation-mono-fonts/LiberationMono-Bold.ttf"

ROW_H = 34
HEADER_H = 66
RADIUS = 12

COLORS = {
    "contas": "#7C3AED",
    "veiculos": "#2563EB",
    "reservas": "#0D9488",
    "pagamentos": "#D97706",
    "locacoes": "#0891B2",
    "avaliacoes": "#DB2777",
    "administracao": "#475569",
}

BADGES = {
    "PK": ("#92400E", "#FEF3C7"),
    "FK": ("#1D4ED8", "#DBEAFE"),
    "U": ("#6D28D9", "#EDE9FE"),
    "IX": ("#0F766E", "#CCFBF1"),
    "M2M": ("#BE123C", "#FFE4E6"),
}


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size * S)


F_TITLE = font(SANS_B, 40)
F_SUBTITLE = font(SANS_R, 19)
F_TABLE = font(MONO_B, 19)
F_APP = font(SANS_R, 12)
F_FIELD = font(MONO_R, 15)
F_TYPE = font(MONO_R, 12)
F_BADGE = font(SANS_B, 10)
F_EDGE = font(SANS_B, 12)
F_LEGEND = font(SANS_R, 13)
F_LEGEND_B = font(SANS_B, 13)

# ---------------------------------------------------------------------------
# Models -> tabelas
# ---------------------------------------------------------------------------

TABLES = [
    {
        "app": "contas",
        "model": "Usuario",
        "table": "contas_usuario",
        "x": 60,
        "y": 210,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("password", "varchar(128)", [], False),
            ("last_login", "timestamptz", [], True),
            ("is_superuser", "bool", [], False),
            ("username", "varchar(150)", ["U"], False),
            ("first_name", "varchar(150)", [], False),
            ("last_name", "varchar(150)", [], False),
            ("email", "varchar(254)", [], False),
            ("is_staff", "bool", [], False),
            ("is_active", "bool", [], False),
            ("date_joined", "timestamptz", [], False),
            ("proprietario", "bool", [], False),
            ("locatario", "bool", [], False),
            # blank=True no Django permite string vazia, mas a coluna não aceita NULL.
            ("documento_identidade", "varchar(100)", [], False),
            ("aprovacao_documento", "varchar(10)", [], False),
            ("cnh_numero", "varchar(20)", [], False),
            ("cnh_validade", "date", [], True),
            ("aprovacao_cnh", "varchar(10)", [], False),
            ("groups", "auth_group", ["M2M"], False),
            ("user_permissions", "auth_permission", ["M2M"], False),
        ],
    },
    {
        "app": "veiculos",
        "model": "Veiculo",
        "table": "veiculos_veiculo",
        "x": 620,
        "y": 210,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("proprietario_id", "bigint", ["FK"], False),
            ("caracteristicas", "text", [], False),
            ("cidade", "varchar(150)", ["IX"], False),
            ("categoria", "varchar(50)", [], False),
            ("cambio", "varchar(50)", [], False),
            ("combustivel", "varchar(50)", [], False),
            ("passageiros", "smallint", [], False),
            ("preco_diaria", "numeric(10,2)", [], False),
            ("ativo", "bool", [], False),
            ("bloqueado", "bool", [], False),
            ("aprovacao", "varchar(10)", [], False),
        ],
    },
    {
        "app": "veiculos",
        "model": "FotoVeiculo",
        "table": "veiculos_fotoveiculo",
        "x": 620,
        "y": 740,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("veiculo_id", "bigint", ["FK"], False),
            ("foto", "varchar(100)", [], False),
        ],
    },
    {
        "app": "veiculos",
        "model": "PeriodoAgenda",
        "table": "veiculos_periodoagenda",
        "x": 620,
        "y": 964,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("veiculo_id", "bigint", ["FK"], False),
            ("inicio", "date", [], False),
            ("fim", "date", [], False),
            ("tipo", "varchar(10)", [], False),
        ],
    },
    {
        "app": "reservas",
        "model": "Reserva",
        "table": "reservas_reserva",
        "x": 1180,
        "y": 210,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("veiculo_id", "bigint", ["FK"], False),
            ("locatario_id", "bigint", ["FK"], False),
            ("inicio", "date", [], False),
            ("fim", "date", [], False),
            ("status", "varchar(12)", [], False),
            ("preco_diaria", "numeric(10,2)", [], False),
            ("valor_diarias", "numeric(12,2)", [], False),
            ("taxas", "numeric(12,2)", [], False),
            ("total", "numeric(12,2)", [], False),
            ("percentual_comissao", "numeric(5,2)", [], False),
        ],
    },
    {
        "app": "pagamentos",
        "model": "Pagamento",
        "table": "pagamentos_pagamento",
        "x": 1740,
        "y": 210,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("reserva_id", "bigint", ["FK", "U"], False),
            ("meio", "varchar(6)", [], False),
            ("status", "varchar(9)", [], False),
            ("valor_bruto", "numeric(12,2)", [], False),
            ("comissao", "numeric(12,2)", [], False),
            ("repasse_proprietario", "numeric(12,2)", [], False),
        ],
    },
    {
        "app": "locacoes",
        "model": "RegistroLocacao",
        "table": "locacoes_registrolocacao",
        "x": 1740,
        "y": 570,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("reserva_id", "bigint", ["FK"], False),
            ("tipo", "varchar(9)", [], False),
            ("quilometragem", "int", [], False),
            ("nivel_combustivel", "smallint", [], False),
        ],
    },
    {
        "app": "locacoes",
        "model": "FotoRegistroLocacao",
        "table": "locacoes_fotoregistrolocacao",
        "x": 1740,
        "y": 862,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("registro_id", "bigint", ["FK"], False),
            ("foto", "varchar(100)", [], False),
        ],
    },
    {
        "app": "avaliacoes",
        "model": "Avaliacao",
        "table": "avaliacoes_avaliacao",
        "x": 1180,
        "y": 712,
        "fields": [
            ("id", "bigint", ["PK"], False),
            ("reserva_id", "bigint", ["FK"], False),
            ("autor_id", "bigint", ["FK"], False),
            ("avaliado_id", "bigint", ["FK"], False),
            ("nota", "smallint", [], False),
        ],
    },
    {
        "app": "administracao",
        "model": "ConfiguracaoComissao",
        "table": "administracao_configuracaocomissao",
        "x": 60,
        "y": 1016,
        "fields": [
            ("id", "smallint", ["PK"], False),
            ("percentual", "numeric(5,2)", [], False),
        ],
    },
]

TABLE_W = 430


def table_height(t: dict) -> int:
    return HEADER_H + ROW_H * len(t["fields"])


# ---------------------------------------------------------------------------
# Arestas (relacionamentos)
# ---------------------------------------------------------------------------

EDGES = [
    {
        "points": [(490, 293), (555, 293), (555, 327), (620, 327)],
        "color": COLORS["veiculos"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [
            (490, 300),
            (575, 300),
            (575, 160),
            (1130, 160),
            (1130, 361),
            (1180, 361),
        ],
        "color": COLORS["reservas"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
        "mid": ("locatário", 852, 160),
    },
    {
        "points": [
            (490, 307),
            (590, 307),
            (590, 1250),
            (1105, 1250),
            (1105, 863),
            (1180, 863),
        ],
        "color": COLORS["avaliacoes"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
        "mid": ("autor", 848, 1250),
    },
    {
        "points": [
            (490, 314),
            (603, 314),
            (603, 1272),
            (1122, 1272),
            (1122, 897),
            (1180, 897),
        ],
        "color": COLORS["avaliacoes"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
        "mid": ("avaliado", 848, 1272),
    },
    {
        "points": [(1050, 293), (1148, 293), (1148, 327), (1180, 327)],
        "color": COLORS["reservas"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [(900, 684), (900, 740)],
        "color": COLORS["veiculos"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [(1050, 330), (1090, 330), (1090, 1081), (1050, 1081)],
        "color": COLORS["veiculos"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [(1610, 293), (1700, 293), (1700, 327), (1740, 327)],
        "color": COLORS["pagamentos"],
        "target": "one",
        "src_label": "1",
        "dst_label": "1",
    },
    {
        "points": [(1610, 344), (1660, 344), (1660, 687), (1740, 687)],
        "color": COLORS["locacoes"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [(1300, 650), (1300, 712)],
        "color": COLORS["avaliacoes"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
    {
        "points": [(1860, 806), (1860, 862)],
        "color": COLORS["locacoes"],
        "target": "crow",
        "src_label": "1",
        "dst_label": "N",
    },
]


# ---------------------------------------------------------------------------
# Helpers de desenho
# ---------------------------------------------------------------------------


def hex_rgb(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
        alpha,
    )


def scaled(points):
    return [(x * S, y * S) for x, y in points]


def rounded(draw, box, radius, **kwargs):
    draw.rounded_rectangle(
        [box[0] * S, box[1] * S, box[2] * S, box[3] * S],
        radius=radius * S,
        **kwargs,
    )


def text(draw, xy, value, fnt, fill, anchor="lm", stroke=0, stroke_fill=None):
    draw.text(
        (xy[0] * S, xy[1] * S),
        value,
        font=fnt,
        fill=hex_rgb(fill) if isinstance(fill, str) else fill,
        anchor=anchor,
        stroke_width=stroke * S,
        stroke_fill=hex_rgb(stroke_fill) if isinstance(stroke_fill, str) else stroke_fill,
    )


def draw_crow(draw, anchor, direction, color, size=13):
    """Pé de galinha no ponto de entrada da tabela filha."""
    (ax, ay), (dx, dy) = anchor, direction
    import math

    base = math.degrees(math.atan2(dy, dx))
    for offset in (-30, 0, 30):
        angle = math.radians(base + 180 + offset)
        end = (ax + math.cos(angle) * size, ay + math.sin(angle) * size)
        draw.line(
            [(ax * S, ay * S), (end[0] * S, end[1] * S)],
            fill=color,
            width=int(1.7 * S),
        )


def draw_one(draw, anchor, direction, color, back=16, half=6):
    dx, dy = direction
    px, py = -dy, dx
    cx, cy = anchor[0] - dx * back, anchor[1] - dy * back
    draw.line(
        [
            ((cx + px * half) * S, (cy + py * half) * S),
            ((cx - px * half) * S, (cy - py * half) * S),
        ],
        fill=color,
        width=int(1.7 * S),
    )


def draw_edge(draw, edge):
    import math

    points = edge["points"]
    color = hex_rgb(edge["color"], 210)
    draw.line(scaled(points), fill=color, width=int(1.8 * S), joint="curve")

    # marcador de origem: 1 (lado "pai")
    x0, y0 = points[0]
    x1, y1 = points[1]
    d = math.hypot(x1 - x0, y1 - y0) or 1
    out = ((x1 - x0) / d, (y1 - y0) / d)
    draw_one(draw, (x0, y0), out, color)

    # marcador de destino
    xt, yt = points[-1]
    xp, yp = points[-2]
    d = math.hypot(xt - xp, yt - yp) or 1
    into = ((xt - xp) / d, (yt - yp) / d)
    if edge["target"] == "crow":
        draw_crow(draw, (xt, yt), into, color)
    else:
        draw_one(draw, (xt, yt), into, color)

    # rótulos de cardinalidade (o traço perpendicular já indica o lado "1")
    if edge.get("dst_label"):
        if abs(into[0]) > 0.5:  # trecho horizontal: rótulo acima da linha
            lx, ly = xt - into[0] * 34, yt - 14
        else:  # trecho vertical: rótulo à esquerda da linha
            lx, ly = xt - 14, yt - into[1] * 34
        text(
            draw,
            (lx, ly),
            edge["dst_label"],
            F_EDGE,
            edge["color"],
            anchor="mm",
            stroke=3,
            stroke_fill=BG,
        )

    if edge.get("mid"):
        label, mx, my = edge["mid"]
        text(
            draw,
            (mx, my - 12),
            label,
            F_EDGE,
            edge["color"],
            anchor="mm",
            stroke=3,
            stroke_fill=BG,
        )


def table_title_font(name: str) -> ImageFont.FreeTypeFont:
    """Reduz o corpo da fonte até o nome da tabela caber no cabeçalho."""
    size = 19
    while size > 12:
        candidate = font(MONO_B, size)
        if candidate.getlength(name) <= (TABLE_W - 40) * S:
            return candidate
        size -= 1
    return font(MONO_B, 12)


def draw_table(draw, t):
    x, y = t["x"], t["y"]
    h = table_height(t)
    color = t["color"]
    title_font = table_title_font(t["table"])

    # corpo
    rounded(
        draw,
        (x, y, x + TABLE_W, y + h),
        RADIUS,
        fill=hex_rgb("#FFFFFF"),
        outline=hex_rgb(BORDER),
        width=1,
    )

    # cabeçalho (cantos superiores arredondados + base reta)
    draw.rectangle(
        [x * S, (y + RADIUS) * S, (x + TABLE_W) * S, (y + HEADER_H) * S],
        fill=hex_rgb(color),
    )
    draw.rounded_rectangle(
        [x * S, y * S, (x + TABLE_W) * S, (y + RADIUS * 2) * S],
        radius=RADIUS * S,
        fill=hex_rgb(color),
    )
    # tarja inferior do cabeçalho, na cor do módulo
    draw.rectangle(
        [x * S, (y + HEADER_H - 3) * S, (x + TABLE_W) * S, (y + HEADER_H) * S],
        fill=hex_rgb(color),
    )

    text(
        draw,
        (x + 20, y + 23),
        t["table"],
        title_font,
        "#FFFFFF",
    )
    text(
        draw,
        (x + 20, y + 47),
        f'{t["app"]} · {t["model"]}',
        F_APP,
        hex_rgb("#FFFFFF", 205),
    )

    # linhas
    for i, (name, ftype, badges, nullable) in enumerate(t["fields"]):
        ry = y + HEADER_H + i * ROW_H
        if i % 2 == 1:
            draw.rectangle(
                [x * S, ry * S, (x + TABLE_W) * S, (ry + ROW_H) * S],
                fill=hex_rgb(STRIPE),
            )
        if i:
            draw.line(
                [(x * S, ry * S), ((x + TABLE_W) * S, ry * S)],
                fill=hex_rgb("#F1F5F9"),
                width=S,
            )

        cy = ry + ROW_H / 2
        bx = x + 14
        for badge in badges:
            fg, bg = BADGES[badge]
            bw = 12 + len(badge) * 7
            rounded(
                draw,
                (bx, cy - 8, bx + bw, cy + 8),
                4,
                fill=hex_rgb(bg),
            )
            text(draw, (bx + bw / 2, cy), badge, F_BADGE, fg, anchor="mm")
            bx += bw + 6

        # coluna fixa para os nomes, mantendo alinhamento mesmo sem badge
        text(draw, (x + 84, cy), name, F_FIELD, INK)

        suffix = " ?" if nullable else ""
        text(
            draw,
            (x + TABLE_W - 16, cy),
            ftype + suffix,
            F_TYPE,
            "#94A3B8",
            anchor="rm",
        )

    # moldura por cima das listras
    rounded(
        draw,
        (x, y, x + TABLE_W, y + h),
        RADIUS,
        outline=hex_rgb(BORDER),
        width=1,
    )
    draw.rectangle(
        [x * S, (y + RADIUS) * S, (x + TABLE_W) * S, (y + HEADER_H - 3) * S],
        fill=hex_rgb(color),
    )
    # repinta os textos do cabeçalho após a tarja
    text(draw, (x + 20, y + 23), t["table"], title_font, "#FFFFFF")
    text(
        draw,
        (x + 20, y + 47),
        f'{t["app"]} · {t["model"]}',
        F_APP,
        hex_rgb("#FFFFFF", 205),
    )


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def main() -> None:
    for t in TABLES:
        t["color"] = COLORS[t["app"]]

    # resolve a ordem de desenho dos campos com badges à esquerda
    image = Image.new("RGBA", (W * S, H * S), hex_rgb(BG))
    draw = ImageDraw.Draw(image)

    # grade sutil de fundo
    for gx in range(0, W, 40):
        draw.line([(gx * S, 0), (gx * S, H * S)], fill=hex_rgb("#EEF0F6"), width=1)
    for gy in range(0, H, 40):
        draw.line([(0, gy * S), (W * S, gy * S)], fill=hex_rgb("#EEF0F6"), width=1)

    # sombra das tabelas
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    for t in TABLES:
        sdraw.rounded_rectangle(
            [
                (t["x"] + 2) * S,
                (t["y"] + 8) * S,
                (t["x"] + TABLE_W + 2) * S,
                (t["y"] + table_height(t) + 8) * S,
            ],
            radius=RADIUS * S,
            fill=(15, 23, 42, 30),
        )
    shadow = shadow.filter(ImageFilter.GaussianBlur(7 * S))
    image = Image.alpha_composite(image, shadow)
    draw = ImageDraw.Draw(image)

    # faixa de acento do título
    accent = ["#7C3AED", "#2563EB", "#0D9488", "#0891B2", "#D97706", "#DB2777", "#475569"]
    for i, c in enumerate(accent):
        y0 = 52 + i * 9
        draw.rounded_rectangle(
            [58 * S, y0 * S, 67 * S, (y0 + 10) * S], radius=3 * S, fill=hex_rgb(c)
        )

    text(draw, (88, 58), "ShareCar — Estrutura do Banco de Dados", F_TITLE, INK)
    text(
        draw,
        (90, 105),
        "Modelo relacional PostgreSQL gerado a partir dos Django models · 7 apps · 10 tabelas de negócio",
        F_SUBTITLE,
        MUTED,
    )
    text(
        draw,
        (W - 60, 62),
        f"gerado em {date.today().strftime('%d/%m/%Y')}",
        F_LEGEND,
        "#94A3B8",
        anchor="rm",
    )
    draw.line(
        [(60 * S, 138 * S), ((W - 60) * S, 138 * S)],
        fill=hex_rgb("#E2E8F0"),
        width=2,
    )

    # arestas primeiro (ficam atrás das tabelas)
    for edge in EDGES:
        draw_edge(draw, edge)

    for t in TABLES:
        draw_table(draw, t)

    # rodapé
    footer = (60, 1330, W - 60, 1460)
    rounded(
        draw,
        footer,
        10,
        fill=hex_rgb("#FFFFFF"),
        outline=hex_rgb(BORDER),
        width=1,
    )
    text(draw, (82, 1352), "Legenda", F_LEGEND_B, INK)
    text(
        draw,
        (82, 1376),
        "PK chave primária · FK chave estrangeira · U único · IX índice · M2M N:N · ? aceita NULL · traço perpendicular = lado 1 · pé de galinha = lado N",
        F_LEGEND,
        MUTED,
    )
    text(draw, (82, 1402), "Regras", F_LEGEND_B, INK)
    text(
        draw,
        (82, 1426),
        "EXCLUDE reserva_sem_sobreposicao impede sobrepor reservas ativas por veículo; CHECKs de período (fim > início), valores, comissão 0–100 e nota 1–5.",
        F_LEGEND,
        MUTED,
    )
    text(
        draw,
        (82, 1446),
        "UNIQUE (reserva, tipo) · UNIQUE (reserva, autor) · 1 pagamento por reserva · comissão global única (id = 1). Auxiliares Django: auth_group, auth_permission, django_admin_log, django_content_type, django_migrations, django_session.",
        F_LEGEND,
        "#94A3B8",
    )

    output = Path(__file__).with_name("diagrama-banco-de-dados.png")
    image.convert("RGB").save(output, format="PNG", optimize=True)
    print(f"Diagrama gerado: {output} ({image.width}x{image.height}px)")


if __name__ == "__main__":
    main()
