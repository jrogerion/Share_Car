import tempfile
from io import StringIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from apps.contas.models import Usuario
from apps.core.media import servir_media_publica

from .models import FotoRegistroLocacao, RegistroLocacao
from .storage import ArmazenamentoVistoriasPrivado
from .tests import LocacaoBaseTests


class AcessoFotoVistoriaTests(LocacaoBaseTests):
    def setUp(self):
        self.reserva = self.criar_reserva()
        self.aprovar_pagamento(self.reserva)
        registro = self.registrar(self.reserva, "check_in", quilometragem=1000)
        self.foto = registro.fotos.first()
        self.url = reverse("locacoes:foto", args=[self.foto.pk])

    def test_visitante_e_terceiro_nao_acessam(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.outro)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"download": "1"}).status_code, 404)

    def test_participantes_e_administradores_acessam_sem_cache(self):
        admin = Usuario.objects.create_user("staff-vistoria", "staff@example.com", is_staff=True)
        superuser = Usuario.objects.create_user("super-vistoria", "super@example.com", is_superuser=True)
        for usuario in (self.locatario, self.proprietario, admin, superuser):
            with self.subTest(usuario=usuario.pk):
                self.client.force_login(usuario)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertIn(response["Content-Type"], ("image/jpeg", "image/png"))
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("Cookie", response["Vary"])
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response["Cross-Origin-Resource-Policy"], "same-origin")
                self.assertTrue(b"".join(response.streaming_content))

    def test_download_head_e_metodos(self):
        self.client.force_login(self.locatario)
        response = self.client.get(self.url, {"download": "1"})
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertNotIn(self.foto.foto.name, response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content))
        response = self.client.head(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        b"".join(response.streaming_content)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_foto_ausente_e_foto_de_outra_reserva_retornam_404(self):
        self.client.force_login(self.locatario)
        self.foto.foto.storage.delete(self.foto.foto.name)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(reverse("locacoes:foto", args=[999999])).status_code, 404)

    def test_reserva_exibe_link_autenticado_sem_nome_do_arquivo(self):
        self.client.force_login(self.proprietario)
        response = self.client.get(reverse("reservas:detalhe", args=[self.reserva.pk]))
        self.assertContains(response, self.url)
        self.assertNotContains(response, self.foto.foto.name)
        admin = Usuario.objects.create_user("admin-consulta-foto", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("administracao:reserva", args=[self.reserva.pk]))
        self.assertContains(response, self.url)


class MediaPublicaTests(SimpleTestCase):
    def test_storage_privado_nao_gera_url_publica(self):
        with tempfile.TemporaryDirectory() as pasta:
            storage = ArmazenamentoVistoriasPrivado(location=pasta)
            with self.assertRaises(ValueError):
                storage.url("locacoes/foto.png")

    def test_media_publica_bloqueia_vistorias_caminhos_alternativos_e_symlinks(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "veiculos").mkdir()
            (raiz / "locacoes").mkdir()
            (raiz / "veiculos/carro.png").write_bytes(b"foto-publica")
            (raiz / "locacoes/foto.png").write_bytes(b"foto-privada")
            (raiz / "veiculos/atalho.png").symlink_to(raiz / "locacoes/foto.png")
            factory = RequestFactory()
            for nome in ("locacoes/foto.png", "veiculos/../locacoes/foto.png", "veiculos/atalho.png", "identidades/documento.png"):
                with self.subTest(caminho=nome), self.assertRaises(Http404):
                    servir_media_publica(factory.get("/media/" + nome), nome, document_root=raiz)
            response = servir_media_publica(factory.get("/media/veiculos/carro.png"), "veiculos/carro.png", document_root=raiz)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"foto-publica")
            response.close()


class TransferenciaFotosTests(LocacaoBaseTests):
    def setUp(self):
        self.enterContext(override_settings(STORAGES={
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage", "OPTIONS": {"location": "/public-test"}},
            "vistorias": {"BACKEND": "django.core.files.storage.InMemoryStorage", "OPTIONS": {"location": "/private-test"}},
        }))
        self.origem = storages["default"]
        self.destino = storages["vistorias"]
        reserva = self.criar_reserva()
        self.registro = RegistroLocacao.objects.create(
            reserva=reserva, tipo="check_in", quilometragem=100, nivel_combustivel=50,
        )
        self.nome = "locacoes/foto-teste.png"
        FotoRegistroLocacao.objects.create(registro=self.registro, foto=self.nome)
        self.origem.save(self.nome, ContentFile(b"conteudo-ficticio"))

    def executar(self, **opcoes):
        output = StringIO()
        call_command("proteger_fotos_vistoria", stdout=output, **opcoes)
        return output.getvalue()

    def test_padrao_apenas_confere_e_nao_expoe_nomes(self):
        output = self.executar()
        self.assertIn("Somente verificação", output)
        self.assertNotIn(self.nome, output)
        self.assertTrue(self.origem.exists(self.nome))
        self.assertFalse(self.destino.exists(self.nome))

    def test_copia_e_limpeza_explicitas_reexecutaveis_preservam_registro(self):
        self.executar(executar=True)
        self.assertTrue(self.origem.exists(self.nome))
        self.assertTrue(self.destino.exists(self.nome))
        self.executar(executar=True, remover_originais=True)
        self.assertFalse(self.origem.exists(self.nome))
        with self.destino.open(self.nome) as arquivo:
            self.assertEqual(arquivo.read(), b"conteudo-ficticio")
        self.executar(executar=True, remover_originais=True)
        self.assertEqual(FotoRegistroLocacao.objects.get().foto.name, self.nome)

    def test_conflito_nao_sobrescreve_nem_remove_arquivos(self):
        self.destino.save(self.nome, ContentFile(b"conteudo-diferente"))
        with self.assertRaises(CommandError):
            self.executar(executar=True, remover_originais=True)
        self.assertTrue(self.origem.exists(self.nome))
        with self.destino.open(self.nome) as arquivo:
            self.assertEqual(arquivo.read(), b"conteudo-diferente")

    def test_falta_de_arquivo_aborta_antes_de_copiar(self):
        FotoRegistroLocacao.objects.create(registro=self.registro, foto="locacoes/ausente.png")
        with self.assertRaises(CommandError):
            self.executar(executar=True, remover_originais=True)
        self.assertFalse(self.destino.exists(self.nome))
        self.assertTrue(self.origem.exists(self.nome))

    def test_remocao_exige_execucao_explicita(self):
        with self.assertRaises(CommandError):
            self.executar(remover_originais=True)
        self.assertTrue(self.origem.exists(self.nome))
