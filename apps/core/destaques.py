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

    @property
    def foto_principal(self) -> str:
        return self.fotos[0]


DESTAQUES = (
    Destaque(
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
        fotos=(
            "images/destaques/fiat-argo-1.svg",
            "images/destaques/fiat-argo-2.svg",
            "images/destaques/fiat-argo-3.svg",
        ),
    ),
    Destaque(
        slug="jeep-renegade",
        nome="Jeep Renegade",
        ano=2022,
        categoria="SUV",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Diesel",
        passageiros=5,
        preco_diaria=189,
        nota="4,9",
        descricao=(
            "SUV robusto para viagens e passeios fora do asfalto. "
            "Oferece posição de dirigir elevada, bom espaço para bagagem "
            "e resposta firme em diferentes tipos de terreno."
        ),
        equipamentos=(
            "Ar-condicionado digital",
            "Câmbio automático",
            "Controle de estabilidade",
            "Sensor de estacionamento",
            "Rodas de liga leve",
        ),
        fotos=(
            "images/destaques/jeep-renegade-1.svg",
            "images/destaques/jeep-renegade-2.svg",
            "images/destaques/jeep-renegade-3.svg",
        ),
    ),
    Destaque(
        slug="honda-city",
        nome="Honda City",
        ano=2023,
        categoria="Sedã",
        cidade="São Paulo",
        cambio="Automático",
        combustivel="Flex",
        passageiros=5,
        preco_diaria=240,
        nota="4,9",
        descricao=(
            "Sedã automático, confortável e completo, com bom espaço interno "
            "e porta-malas amplo. Uma opção equilibrada para viagens em "
            "família ou deslocamentos urbanos."
        ),
        equipamentos=(
            "Ar-condicionado",
            "Câmbio automático",
            "Central multimídia",
            "Câmera de ré",
            "Controle de cruzeiro",
        ),
        fotos=(
            "images/destaques/honda-city-1.svg",
            "images/destaques/honda-city-2.svg",
            "images/destaques/honda-city-3.svg",
        ),
    ),
    Destaque(
        slug="toyota-corolla",
        nome="Toyota Corolla",
        ano=2022,
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
        fotos=(
            "images/destaques/toyota-corolla-1.svg",
            "images/destaques/toyota-corolla-2.svg",
            "images/destaques/toyota-corolla-3.svg",
        ),
    ),
)

DESTAQUES_POR_SLUG = {destaque.slug: destaque for destaque in DESTAQUES}
