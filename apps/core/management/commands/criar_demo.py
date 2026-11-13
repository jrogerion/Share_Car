import getpass
import sys
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.avaliacoes.services import avaliar_reserva
from apps.contas.models import Usuario
from apps.locacoes.services import registrar_locacao
from apps.pagamentos.services import simular_pagamento
from apps.reservas.services import aceitar_reserva, criar_reserva
from apps.veiculos.forms import FotoVeiculoForm
from apps.veiculos.models import FotoVeiculo, Veiculo


MARCADOR = "Demonstracao ShareCar v1"
CONTAS = (
    ("proprietario1", "Ana", True),
    ("proprietario2", "Bruno", True),
    ("proprietario3", "Carla", True),
    ("locatario1", "Diego", False),
    ("locatario2", "Elisa", False),
    ("locatario3", "Felipe", False),
    ("locatario4", "Gabriela", False),
)
VEICULOS = (
    ("fiat-argo", "Fiat Argo", "Hatch", "São Paulo", "150.00", 0),
    ("honda-city", "Honda City", "Sedã", "Campinas", "200.00", 0),
    ("jeep-renegade", "Jeep Renegade", "SUV", "São Paulo", "250.00", 1),
    ("fiat-toro", "Fiat Toro", "Picape", "Curitiba", "280.00", 1),
    ("fiat-argo", "Fiat Argo", "Hatch", "Belo Horizonte", "160.00", 2),
    ("honda-city", "Honda City", "Sedã", "Rio de Janeiro", "190.00", 2),
)
CREDITOS = {
    "fiat-argo": (
        "Maxi-Napo-99", "CC BY 4.0", "by",
        "2023_Fiat_Argo_1.3_Drive_(facelift,_Brazil).jpg",
    ),
    "honda-city": (
        "Dairokkan9", "CC BY-SA 4.0", "by-sa",
        "2022_Honda_City_ZX_i-VTEC_(India)_front_view_(cropped).jpg",
    ),
    "jeep-renegade": (
        "Cutlass", "CC0", None,
        "2017_Jeep_Renegade_Latitude_in_Black,_front_left,_06-23-2026.jpg",
    ),
    "fiat-toro": (
        "NaBUru38", "CC BY-SA 4.0", "by-sa",
        "Fiat_Toro_2022_1.8_Freedom_in_Punta_del_Este_(front).jpg",
    ),
}


class Command(BaseCommand):
    help = "Cria um cenário fictício local, sem apagar ou reiniciar dados."

    def add_arguments(self, parser):
        parser.add_argument("--confirmar-banco-local", action="store_true")
        parser.add_argument("--senha-stdin", action="store_true")
        parser.add_argument(
            "--imagens-dir", type=Path,
            default=settings.BASE_DIR / "demo" / "imagens" / "veiculos",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG or not options["confirmar_banco_local"]:
            raise CommandError(
                "Somente em desenvolvimento (DEBUG=True). Confirme o banco "
                "local com --confirmar-banco-local.",
            )
        self.arquivos_criados = []
        try:
            with transaction.atomic():
                if self._ja_existe():
                    self.stdout.write(
                        "Cenário já criado. Dados, datas, senhas e progresso "
                        "foram preservados; nenhum registro foi reiniciado.",
                    )
                    return
                fotos = self._carregar_fotos(options["imagens_dir"])
                senha = (
                    sys.stdin.readline().rstrip("\r\n")
                    if options["senha_stdin"]
                    else getpass.getpass("Senha das contas fictícias: ")
                )
                try:
                    validate_password(senha)
                except ValidationError as exc:
                    raise CommandError(" ".join(exc.messages)) from exc
                self._criar_cenario(senha, fotos)
        except Exception:
            # O banco faz rollback; removem-se apenas arquivos desta execução.
            for storage, nome in reversed(self.arquivos_criados):
                storage.delete(nome)
            raise
        self.stdout.write(self.style.SUCCESS(
            "Demonstração criada: 7 contas, 6 veículos e 7 reservas. "
            "Nenhum usuário administrativo foi criado.",
        ))
        for codigo, _, _ in CONTAS:
            self.stdout.write(f"{codigo}@demo.example.com")

    def _ja_existe(self):
        nomes = {f"demo_{codigo}" for codigo, _, _ in CONTAS}
        emails = {f"{codigo}@demo.example.com" for codigo, _, _ in CONTAS}
        existentes = Usuario.objects.alias(email_normalizado=Lower("email"))
        usuarios = list(existentes.filter(
            Q(username__in=nomes) | Q(email_normalizado__in=emails),
        ))
        if not usuarios:
            return False
        if len(usuarios) != len(CONTAS) or any(
            u.username not in nomes
            or u.email != f"{u.username.removeprefix('demo_')}@demo.example.com"
            or u.last_name != MARCADOR
            or u.is_staff or u.is_superuser
            for u in usuarios
        ):
            raise CommandError(
                "Há contas conflitantes ou um cenário incompleto. "
                "Nada será alterado; revise os registros manualmente.",
            )
        return True

    def _carregar_fotos(self, pasta):
        fotos = {}
        for slug in CREDITOS:
            try:
                conteudo = (pasta / f"{slug}.jpg").read_bytes()
            except OSError as exc:
                raise CommandError(f"Foto ausente: {slug}.jpg.") from exc
            form = FotoVeiculoForm(files={
                "foto": ContentFile(conteudo, name=f"{slug}.jpg"),
            })
            if not form.is_valid():
                raise CommandError(f"Foto inválida: {slug}.jpg.")
            fotos[slug] = form.cleaned_data["foto"].read()
        return fotos

    def _salvar_arquivo(self, campo, nome, conteudo):
        campo.save(nome, ContentFile(conteudo), save=False)
        self.arquivos_criados.append((campo.storage, campo.name))

    @staticmethod
    def _imagem_ficticia(texto):
        imagem = Image.new("RGB", (800, 450), "#e6f4f1")
        desenho = ImageDraw.Draw(imagem)
        desenho.text((40, 130), "SHARECAR - DEMONSTRACAO", fill="black")
        desenho.text((40, 180), texto, fill="black")
        desenho.text((40, 230), "FICTICIO - SEM VALIDADE REAL", fill="black")
        buffer = BytesIO()
        imagem.save(buffer, format="PNG")
        return buffer.getvalue()

    def _criar_cenario(self, senha, fotos):
        hoje = timezone.localdate()
        usuarios = []
        for indice, (codigo, nome, proprietario) in enumerate(CONTAS):
            usuario = Usuario(
                username=f"demo_{codigo}", email=f"{codigo}@demo.example.com",
                first_name=f"{nome} (demo)", last_name=MARCADOR,
                proprietario=proprietario, locatario=not proprietario,
                aprovacao_documento=Usuario.Aprovacao.APROVADO,
                aprovacao_cnh=Usuario.Aprovacao.APROVADO,
                cnh_numero=f"DEMO-CNH-{indice + 1:03d}",
                cnh_validade=hoje + timedelta(days=730),
            )
            usuario.set_password(senha)
            self._salvar_arquivo(
                usuario.documento_identidade, f"demo-{codigo}.png",
                self._imagem_ficticia("DOCUMENTO FICTICIO DE TESTE"),
            )
            usuario.save()
            usuarios.append(usuario)
        veiculos = []
        for slug, modelo, categoria, cidade, diaria, dono in VEICULOS:
            autor, licenca, tipo_licenca, fonte = CREDITOS[slug]
            url_licenca = (
                f"https://creativecommons.org/licenses/{tipo_licenca}/4.0/"
                if tipo_licenca
                else "https://creativecommons.org/publicdomain/zero/1.0/"
            )
            veiculo = Veiculo.objects.create(
                proprietario=usuarios[dono], categoria=categoria,
                cidade=cidade, cambio="Manual", combustivel="Gasolina",
                passageiros=5, preco_diaria=diaria,
                aprovacao=Veiculo.Aprovacao.APROVADO,
                caracteristicas=(
                    f"{modelo} — DEMONSTRAÇÃO FICTÍCIA, não disponível para "
                    f"locação real. Foto ilustrativa: {autor} / Wikimedia "
                    f"Commons / {licenca}. Cópia reduzida, sem EXIF. "
                    f"Fonte: https://commons.wikimedia.org/wiki/File:{fonte} "
                    f"Licença: {url_licenca} "
                    "Versão fotografada pode diferir do mercado brasileiro. "
                    "Características e preços apenas demonstrativos.",
                ),
            )
            foto = FotoVeiculo(veiculo=veiculo)
            self._salvar_arquivo(foto.foto, f"demo-{slug}.jpg", fotos[slug])
            foto.save()
            veiculos.append(veiculo)

        locatarios = usuarios[3:]
        # Um período por veículo, exceto duas solicitações não sobrepostas.
        cenarios = (
            (0, 0, 5, "solicitada"), (1, 1, 7, "solicitada"),
            (2, 0, 10, "aceita"), (3, 2, 12, "paga"),
            (4, 3, 0, "andamento"), (5, 1, 0, "concluida"),
            (0, 2, 20, "avaliada"),
        )
        for carro, locatario, dias, etapa in cenarios:
            inicio = hoje + timedelta(days=dias)
            reserva = criar_reserva(
                veiculo=veiculos[carro], locatario=locatarios[locatario],
                inicio=inicio, fim=inicio + timedelta(days=3),
            )
            if etapa != "solicitada":
                aceitar_reserva(reserva)
            if etapa in ("paga", "andamento", "concluida", "avaliada"):
                simular_pagamento(
                    reserva=reserva, meio="pix", resultado="aprovado",
                )
            if etapa in ("andamento", "concluida", "avaliada"):
                self._vistoria(reserva, "check_in", 10000)
            if etapa in ("concluida", "avaliada"):
                self._vistoria(reserva, "check_out", 10120)
                # Histórico fictício: mesmos três dias, em datas já passadas.
                deslocamento = 7 if etapa == "concluida" else 14
                reserva.inicio = hoje - timedelta(days=deslocamento)
                reserva.fim = reserva.inicio + timedelta(days=3)
                reserva.save(update_fields=["inicio", "fim"])
            if etapa == "avaliada":
                avaliar_reserva(reserva=reserva, autor=reserva.locatario, nota=5)
                avaliar_reserva(
                    reserva=reserva, autor=reserva.veiculo.proprietario, nota=4,
                )

    def _vistoria(self, reserva, tipo, km):
        registro = registrar_locacao(
            reserva=reserva, tipo=tipo, quilometragem=km,
            nivel_combustivel=80, fotos=[ContentFile(
                self._imagem_ficticia("VISTORIA FICTICIA - " + tipo),
                name="vistoria-demo.png",
            )],
        )
        for foto in registro.fotos.all():
            self.arquivos_criados.append((foto.foto.storage, foto.foto.name))
