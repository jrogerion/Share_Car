from dataclasses import dataclass


@dataclass(frozen=True)
class Destaque:
    """Dados ilustrativos de um veículo exibido na home."""

    slug: str
    nome: str
    ano: int
    categoria: str
    cidade: str
    cambio: str
    combustivel: str
    passageiros: int
    preco_diaria: int
    nota: str
    descricao: str
    equipamentos: tuple[str, ...]
    fotos: tuple[str, ...]
    fotos_reais: bool = False
    creditos: str = ""
    capa: str = ""

    @property
    def foto_principal(self) -> str:
        return self.capa or self.fotos[0]


def _exemplo(
    *,
    slug: str,
    nome: str,
    ano: int,
    categoria: str,
    cidade: str,
    cambio: str,
    combustivel: str,
    passageiros: int,
    preco_diaria: int,
    nota: str,
    descricao: str,
    equipamentos: tuple[str, ...],
    creditos: str,
) -> Destaque:
    """Cria um destaque usando a convenção de nomes das fotos reais."""

    return Destaque(
        slug=slug,
        nome=nome,
        ano=ano,
        categoria=categoria,
        cidade=cidade,
        cambio=cambio,
        combustivel=combustivel,
        passageiros=passageiros,
        preco_diaria=preco_diaria,
        nota=nota,
        descricao=descricao,
        equipamentos=equipamentos,
        fotos=tuple(
            f"images/destaques/{slug}-{indice}.jpg" for indice in (1, 2, 3)
        ),
        fotos_reais=True,
        creditos=creditos,
        capa=f"images/destaques/{slug}-capa.jpg",
    )


SEDAS = (
    _exemplo(
        slug="toyota-corolla",
        nome="Toyota Corolla",
        ano=2020,
        categoria="Sedã",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=320,
        nota="5,0",
        descricao=(
            "Sedã automático, confortável e econômico, com acabamento "
            "refinado e direção suave. Indicado para quem busca tranquilidade "
            "em viagens longas e no trânsito da cidade."
        ),
        equipamentos=(
            "Ar-condicionado digital",
            "Câmbio automático",
            "Central multimídia",
            "Controle de cruzeiro",
            "Sensor de estacionamento",
        ),
        creditos=(
            "Fotos reais: LuvsMG481 (frente e traseira) e Vauxford "
            "(interior), Wikimedia Commons, CC BY-SA 4.0."
        ),
    ),
    _exemplo(
        slug="honda-city",
        nome="Honda City",
        ano=2022,
        categoria="Sedã",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=240,
        nota="4,9",
        descricao=(
            "Sedã automático com bom espaço interno e porta-malas amplo. "
            "Consumo equilibrado e conforto para viagens em família."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de cruzeiro",
        ),
        creditos="Fotos reais: Ethan Llamas — Wikimedia Commons, CC BY-SA 4.0.",
    ),
    _exemplo(
        slug="volkswagen-virtus",
        nome="Volkswagen Virtus",
        ano=2023,
        categoria="Sedã",
        cidade="Campinas",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=210,
        nota="4,8",
        descricao=(
            "Sedã com acabamento caprichado, direção firme e bom desempenho "
            "na estrada. Ideal para quem viaja com frequência."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Controle de cruzeiro",
            "Sensor de estacionamento",
        ),
        creditos=(
            "Fotos reais: Dairokkan9 e DriveSpark — Wikimedia Commons, "
            "CC BY-SA 4.0 e CC BY 3.0."
        ),
    ),
    _exemplo(
        slug="chevrolet-onix-plus",
        nome="Chevrolet Onix Plus",
        ano=2022,
        categoria="Sedã",
        cidade="Belo Horizonte",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=190,
        nota="4,7",
        descricao=(
            "Sedã compacto e econômico, com central multimídia e bom espaço "
            "para bagagem. Prático para o dia a dia e para viagens curtas."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Vidros elétricos",
        ),
        creditos="Fotos reais: Just a Man — Wikimedia Commons, CC BY 4.0.",
    ),
    _exemplo(
        slug="fiat-cronos",
        nome="Fiat Cronos",
        ano=2022,
        categoria="Sedã",
        cidade="Curitiba",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=180,
        nota="4,7",
        descricao=(
            "Sedã com porta-malas generoso e manutenção acessível. Uma opção "
            "equilibrada para famílias e deslocamentos urbanos."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de cruzeiro",
        ),
        creditos="Fotos reais: Just a Man — Wikimedia Commons, CC BY 4.0.",
    ),
)

HATCHES = (
    _exemplo(
        slug="fiat-argo",
        nome="Fiat Argo",
        ano=2021,
        categoria="Hatch",
        cidade="São Paulo",
        cambio="Manual",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=150,
        nota="4,8",
        descricao=(
            "Hatch compacto e econômico, ideal para o dia a dia na cidade. "
            "Tem direção leve, bom espaço interno e porta-malas suficiente "
            "para uma viagem curta."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção elétrica",
            "Central multimídia",
            "Bluetooth",
            "Câmera de ré",
        ),
        creditos=(
            "Fotos reais: NaBUru38 e Arthur RPereira — Wikimedia Commons, "
            "CC BY-SA 4.0 e CC0."
        ),
    ),
    _exemplo(
        slug="volkswagen-polo",
        nome="Volkswagen Polo",
        ano=2021,
        categoria="Hatch",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=170,
        nota="4,8",
        descricao=(
            "Hatch compacto com direção leve e bom isolamento acústico. "
            "Fácil de estacionar e econômico na cidade."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Controle de cruzeiro",
            "Vidros elétricos",
        ),
        creditos=(
            "Fotos reais: AIMHO'S REBELLION 8490s — Wikimedia Commons, "
            "CC BY-SA 4.0."
        ),
    ),
    _exemplo(
        slug="chevrolet-onix",
        nome="Chevrolet Onix",
        ano=2020,
        categoria="Hatch",
        cidade="Rio de Janeiro",
        cambio="Manual",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=140,
        nota="4,6",
        descricao=(
            "Hatch ágil e econômico, com boa posição de dirigir e porta-malas "
            "suficiente para o dia a dia."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção elétrica",
            "Central multimídia",
            "Bluetooth",
            "Vidros elétricos",
        ),
        creditos=(
            "Fotos reais: Heduardo55 e NaBUru38 — Wikimedia Commons, "
            "CC0 e CC BY-SA 4.0."
        ),
    ),
    _exemplo(
        slug="hyundai-hb20",
        nome="Hyundai HB20",
        ano=2023,
        categoria="Hatch",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=160,
        nota="4,8",
        descricao=(
            "Hatch moderno, bem equipado e confortável. Bom para quem "
            "enfrenta trânsito e precisa de agilidade."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de estabilidade",
        ),
        creditos="Fotos reais: Autosdeprimera — Wikimedia Commons, CC BY 3.0.",
    ),
    _exemplo(
        slug="fiat-mobi",
        nome="Fiat Mobi",
        ano=2021,
        categoria="Hatch",
        cidade="Campinas",
        cambio="Manual",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=120,
        nota="4,6",
        descricao=(
            "Hatch pequeno e econômico, ideal para a cidade. Estaciona com "
            "facilidade e tem custo de manutenção baixo."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção elétrica",
            "Central multimídia",
            "Bluetooth",
            "Vidros elétricos",
        ),
        creditos=(
            "Fotos reais: NaBUru38 e Heduardo55 — Wikimedia Commons, "
            "CC BY-SA 4.0 e CC0."
        ),
    ),
)

SUVS = (
    _exemplo(
        slug="jeep-renegade",
        nome="Jeep Renegade",
        ano=2021,
        categoria="SUV",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Híbrido",
        passageiros=5,
        preco_diaria=249,
        nota="4,9",
        descricao=(
            "SUV compacto com posição de dirigir elevada e boa altura do "
            "solo. Versátil para a cidade e para passeios fora do asfalto."
        ),
        equipamentos=(
            "Ar-condicionado digital",
            "Câmbio automático",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de estabilidade",
        ),
        creditos="Fotos reais: Alexander Migl — Wikimedia Commons, CC BY-SA 4.0.",
    ),
    _exemplo(
        slug="volkswagen-t-cross",
        nome="Volkswagen T-Cross",
        ano=2020,
        categoria="SUV",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=220,
        nota="4,8",
        descricao=(
            "SUV compacto com bom espaço interno e porta-malas versátil. "
            "Confortável na cidade e estável na estrada."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de estabilidade",
        ),
        creditos="Fotos reais: Vauxford — Wikimedia Commons, CC BY-SA 4.0.",
    ),
    _exemplo(
        slug="hyundai-creta",
        nome="Hyundai Creta",
        ano=2022,
        categoria="SUV",
        cidade="Belo Horizonte",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=230,
        nota="4,8",
        descricao=(
            "SUV com bom espaço para passageiros e bagagem, além de posição "
            "de dirigir elevada. Indicado para famílias."
        ),
        equipamentos=(
            "Ar-condicionado digital",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de estabilidade",
        ),
        creditos="Fotos reais: Dinkun Chen — Wikimedia Commons, CC BY-SA 4.0.",
    ),
    _exemplo(
        slug="nissan-kicks",
        nome="Nissan Kicks",
        ano=2019,
        categoria="SUV",
        cidade="Curitiba",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=200,
        nota="4,7",
        descricao=(
            "SUV leve e econômico, com suspensão confortável e bom espaço "
            "interno. Prático para o uso urbano."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de estabilidade",
        ),
        creditos=(
            "Fotos reais: Kevauto e Ethan Llamas — Wikimedia Commons, "
            "CC BY-SA 4.0."
        ),
    ),
    _exemplo(
        slug="renault-duster",
        nome="Renault Duster",
        ano=2021,
        categoria="SUV",
        cidade="Porto Alegre",
        cambio="Manual",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=190,
        nota="4,6",
        descricao=(
            "SUV robusto, com bom vão de bagagem e suspensão para estradas "
            "irregulares. Uma opção para viagens mais longas."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção elétrica",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de estabilidade",
        ),
        creditos=(
            "Fotos reais: ROCostiTheBunnyCZ e Rutger van der Maar — "
            "Wikimedia Commons, CC BY-SA 4.0 e CC BY 2.0."
        ),
    ),
)

PICAPES = (
    _exemplo(
        slug="fiat-toro",
        nome="Fiat Toro",
        ano=2022,
        categoria="Picape",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Diesel",
        passageiros=5,
        preco_diaria=320,
        nota="4,8",
        descricao=(
            "Picape intermediária com caçamba versátil e cabine confortável. "
            "Atende tanto o trabalho quanto o lazer."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de tração",
        ),
        creditos="Fotos reais: NaBUru38 — Wikimedia Commons, CC BY-SA 4.0.",
    ),
    _exemplo(
        slug="volkswagen-saveiro",
        nome="Volkswagen Saveiro",
        ano=2024,
        categoria="Picape",
        cidade="Campinas",
        cambio="Manual",
        combustivel="Flex",
        passageiros=2,
        preco_diaria=180,
        nota="4,7",
        descricao=(
            "Picape compacta com caçamba útil e direção leve. Prática para "
            "o dia a dia e pequenos transportes."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção elétrica",
            "Central multimídia",
            "Bluetooth",
            "Vidros elétricos",
        ),
        creditos="Fotos reais: Just a Man — Wikimedia Commons, CC BY 4.0.",
    ),
    _exemplo(
        slug="chevrolet-s10",
        nome="Chevrolet S10",
        ano=2017,
        categoria="Picape",
        cidade="Curitiba",
        cambio="Manual",
        combustivel="Diesel",
        passageiros=5,
        preco_diaria=280,
        nota="4,6",
        descricao=(
            "Picape com boa capacidade de carga e cabine espaçosa. Indicada "
            "para trabalho e viagens com bagagem."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Direção hidráulica",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de tração",
        ),
        creditos=(
            "Fotos reais: Maxi-Napo-99 e Chevrolet México — Wikimedia "
            "Commons, CC BY-SA 4.0 e CC BY 3.0."
        ),
    ),
    _exemplo(
        slug="toyota-hilux",
        nome="Toyota Hilux",
        ano=2022,
        categoria="Picape",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Diesel",
        passageiros=5,
        preco_diaria=420,
        nota="4,9",
        descricao=(
            "Picape robusta, com tração e capacidade de carga para diferentes "
            "terrenos. Confortável em viagens longas."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de tração",
        ),
        creditos=(
            "Fotos reais: LuvsMG481 e Vauxford — Wikimedia Commons, "
            "CC BY-SA 4.0."
        ),
    ),
    _exemplo(
        slug="ford-ranger",
        nome="Ford Ranger",
        ano=2020,
        categoria="Picape",
        cidade="Belo Horizonte",
        cambio="Automático",
        combustivel="Diesel",
        passageiros=5,
        preco_diaria=380,
        nota="4,8",
        descricao=(
            "Picape forte para trabalho e aventura, com cabine ampla e boa "
            "capacidade de carga."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Sensor de estacionamento",
            "Controle de tração",
        ),
        creditos=(
            "Fotos reais: LuvsMG481 e Vauxford — Wikimedia Commons, "
            "CC BY-SA 4.0."
        ),
    ),
)

DESTAQUES = SEDAS + HATCHES + SUVS + PICAPES

DESTAQUES_POR_SLUG = {destaque.slug: destaque for destaque in DESTAQUES}
