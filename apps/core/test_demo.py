import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.files.storage import InMemoryStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image

from apps.avaliacoes.models import Avaliacao
from apps.contas.models import Usuario
from apps.locacoes.models import FotoRegistroLocacao, RegistroLocacao
from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva
from apps.veiculos.models import FotoVeiculo, Veiculo

from .management.commands.criar_demo import CONTAS, CREDITOS


@override_settings(DEBUG=True)
class CenarioDemoTests(TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        for slug in CREDITOS:
            Image.new("RGB", (2, 2)).save(self.pasta / f"{slug}.jpg")
        self.storages = []
        for model, nome in (
            (Usuario, "documento_identidade"),
            (FotoVeiculo, "foto"), (FotoRegistroLocacao, "foto"),
        ):
            storage = InMemoryStorage()
            self.storages.append(storage)
            troca = patch.object(model._meta.get_field(nome), "storage", storage)
            troca.start()
            self.addCleanup(troca.stop)

    def criar(self, **kwargs):
        with patch("sys.stdin", StringIO("Senha-somente-de-testes!4321\n")):
            return call_command(
                "criar_demo", confirmar_banco_local=True, senha_stdin=True,
                imagens_dir=self.pasta, stdout=StringIO(), **kwargs,
            )

    def test_exige_confirmacao_e_debug(self):
        with self.assertRaises(CommandError):
            call_command("criar_demo", stdout=StringIO())
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.criar()
        self.assertFalse(Usuario.objects.exists())

    def test_cria_cenario_completo_sem_privilegios_administrativos(self):
        self.criar()

        self.assertEqual(Usuario.objects.count(), 7)
        self.assertFalse(Usuario.objects.filter(is_staff=True).exists())
        self.assertFalse(Usuario.objects.filter(is_superuser=True).exists())
        self.assertEqual(Veiculo.objects.count(), 6)
        self.assertEqual(FotoVeiculo.objects.count(), 6)
        self.assertEqual(Reserva.objects.count(), 7)
        self.assertEqual(Pagamento.objects.count(), 4)
        self.assertEqual(RegistroLocacao.objects.count(), 5)
        self.assertEqual(FotoRegistroLocacao.objects.count(), 5)
        self.assertEqual(Avaliacao.objects.count(), 2)
        for usuario in Usuario.objects.all():
            self.assertTrue(usuario.check_password("Senha-somente-de-testes!4321"))
            self.assertTrue(usuario.documento_identidade.storage.exists(
                usuario.documento_identidade.name,
            ))
        self.assertEqual(Reserva.objects.filter(status="solicitada").count(), 2)
        self.assertEqual(Reserva.objects.filter(status="aceita").count(), 2)
        self.assertEqual(Reserva.objects.filter(status="em_andamento").count(), 1)
        self.assertEqual(Reserva.objects.filter(status="concluida").count(), 2)

    def test_preserva_dados_anteriores_e_reexecucao_nao_reinicia_cenario(self):
        real = Usuario.objects.create_user("usuario-anterior", "anterior@example.com")
        senha_anterior = real.password
        self.criar()
        reserva = Reserva.objects.filter(status="solicitada").first()
        reserva.status = Reserva.Status.CANCELADA
        reserva.save(update_fields=["status"])
        usuarios = list(Usuario.objects.order_by("pk").values())
        reservas = list(Reserva.objects.order_by("pk").values())
        fotos = list(FotoVeiculo.objects.values_list("foto", flat=True))
        self.criar()

        self.assertEqual(list(Usuario.objects.order_by("pk").values()), usuarios)
        self.assertEqual(list(Reserva.objects.order_by("pk").values()), reservas)
        self.assertEqual(list(FotoVeiculo.objects.values_list("foto", flat=True)), fotos)
        real.refresh_from_db()
        self.assertEqual(real.password, senha_anterior)

    def test_colisao_com_conta_existente_interrompe_sem_sobrescrever(self):
        real = Usuario.objects.create_user("demo_proprietario1", "real@example.com")
        with self.assertRaises(CommandError):
            self.criar()
        self.assertEqual(Usuario.objects.count(), 1)
        real.refresh_from_db()
        self.assertEqual(real.email, "real@example.com")
        self.assertFalse(Veiculo.objects.exists())

    def test_colisao_de_email_independe_de_maiusculas(self):
        Usuario.objects.create_user("outro", "PROPRIETARIO1@DEMO.EXAMPLE.COM")
        with self.assertRaises(CommandError):
            self.criar()
        self.assertEqual(Usuario.objects.count(), 1)

    def test_imagem_ausente_nao_cria_dados_parciais(self):
        with tempfile.TemporaryDirectory() as vazia:
            with self.assertRaises(CommandError):
                call_command(
                    "criar_demo", confirmar_banco_local=True,
                    imagens_dir=Path(vazia), stdout=StringIO(),
                )
        self.assertFalse(Usuario.objects.exists())

    def test_senha_invalida_nao_cria_contas(self):
        with patch("sys.stdin", StringIO("\n")), self.assertRaises(CommandError):
            call_command(
                "criar_demo", confirmar_banco_local=True, senha_stdin=True,
                imagens_dir=self.pasta, stdout=StringIO(),
            )
        self.assertFalse(Usuario.objects.exists())

    def test_falha_faz_rollback_e_remove_apenas_arquivos_criados(self):
        with patch(
            "apps.core.management.commands.criar_demo.Command._vistoria",
            side_effect=RuntimeError("Falha simulada"),
        ), self.assertRaises(RuntimeError):
            self.criar()
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(Veiculo.objects.exists())
        self.assertFalse(Reserva.objects.exists())
        for storage in self.storages:
            self.assertEqual(storage.listdir("")[1], [])

    def test_creditos_aparecem_nos_detalhes_dos_anuncios(self):
        self.criar()
        for veiculo in Veiculo.objects.all():
            self.assertIn("DEMONSTRAÇÃO FICTÍCIA", veiculo.caracteristicas)
            self.assertIn("Wikimedia", veiculo.caracteristicas)
            self.assertIn("creativecommons.org", veiculo.caracteristicas)
        self.assertEqual(len(CONTAS), 7)
