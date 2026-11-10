from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import storages
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import DocumentoIdentidadeForm
from .models import Usuario


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "documentos": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
})
class DocumentoIdentidadeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            "pessoa", "pessoa@example.com", "Senha-teste!72rT9",
            aprovacao_documento="aprovado", aprovacao_cnh="aprovado",
        )
        cls.outro = Usuario.objects.create_user("outro", "outro@example.com")
        cls.funcionario = Usuario.objects.create_user(
            "operador", "operador@example.com", is_staff=True,
        )
        cls.superusuario = Usuario.objects.create_superuser(
            "administrador", "admin@example.com", "Senha-teste!72rT9",
        )

    def setUp(self):
        # O callable de storage do model é resolvido na importação. Troca-se
        # também a instância do campo para nunca escrever arquivos reais.
        storage_patch = patch.object(
            Usuario._meta.get_field("documento_identidade"),
            "storage", storages["documentos"],
        )
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.client.force_login(self.usuario)
        self.enviar_url = reverse("contas:enviar_documento")
        self.baixar_url = reverse(
            "contas:documento_identidade", args=[self.usuario.pk],
        )

    def imagem(self, formato="PNG", nome=None):
        buffer = BytesIO()
        Image.new("RGB", (8, 8), "white").save(buffer, format=formato)
        extensao = "jpg" if formato == "JPEG" else formato.lower()
        return SimpleUploadedFile(
            nome or f"documento-ficticio.{extensao}", buffer.getvalue(),
            content_type="application/octet-stream",
        )

    def enviar(self, arquivo=None, **dados):
        return self.client.post(self.enviar_url, {
            "documento_identidade": arquivo or self.imagem(), **dados,
        })

    def test_formulario_privado_com_csrf_e_multipart(self):
        response = self.client.get(self.enviar_url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'accept="image/jpeg,image/png"')
        self.assertNotContains(response, "Dados fictícios.")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_jpeg_e_png_validos_sao_armazenados_com_nome_aleatorio(self):
        for formato, extensao in (("JPEG", "jpg"), ("PNG", "png")):
            with self.subTest(formato=formato):
                response = self.enviar(self.imagem(
                    formato, f"nome-pessoal.{extensao}",
                ))
                self.assertRedirects(response, reverse("contas:perfil"))
                self.usuario.refresh_from_db()
                nome = self.usuario.documento_identidade.name
                self.assertRegex(
                    nome, rf"^identidades/[0-9a-f]{{32}}\.{extensao}$",
                )
                self.assertTrue(storages["documentos"].exists(nome))
                self.assertEqual(self.usuario.aprovacao_documento, "pendente")
                self.assertEqual(self.usuario.aprovacao_cnh, "aprovado")

    def test_rejeita_gif_pdf_e_imagem_corrompida(self):
        arquivos = (
            self.imagem("GIF", "disfarcado.png"),
            SimpleUploadedFile("documento.pdf", b"%PDF-1.4 teste"),
            SimpleUploadedFile(
                "falso.png", b"<script>alert(1)</script>", "image/png",
            ),
        )
        for arquivo in arquivos:
            with self.subTest(nome=arquivo.name):
                response = self.enviar(arquivo)
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "documento_identidade", response.context["form"].errors,
                )
                self.usuario.refresh_from_db()
                self.assertFalse(self.usuario.documento_identidade)
                self.assertEqual(self.usuario.aprovacao_documento, "aprovado")

    def test_rejeita_arquivo_acima_de_5mb(self):
        arquivo = self.imagem()
        arquivo.size = 5 * 1024 * 1024 + 1
        # A validação do campo acontece antes de decodificar a imagem.
        form = DocumentoIdentidadeForm(
            files={"documento_identidade": arquivo}, instance=self.usuario,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("5 MB", form.errors["documento_identidade"][0])

    def test_exige_novo_arquivo_mesmo_quando_ja_existe_documento(self):
        for existente in (False, True):
            with self.subTest(existente=existente):
                if existente:
                    self.enviar()
                response = self.client.post(self.enviar_url, {})
                self.assertEqual(response.status_code, 200)
                self.assertIn(
                    "documento_identidade", response.context["form"].errors,
                )

    def test_substituicao_preserva_arquivo_anterior_e_reinicia_aprovacao(self):
        self.enviar()
        self.usuario.refresh_from_db()
        anterior = self.usuario.documento_identidade.name
        Usuario.objects.filter(pk=self.usuario.pk).update(
            aprovacao_documento="aprovado",
        )
        response = self.enviar(self.imagem("JPEG"))
        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertNotEqual(self.usuario.documento_identidade.name, anterior)
        self.assertTrue(storages["documentos"].exists(anterior))
        self.assertEqual(self.usuario.aprovacao_documento, "pendente")

    def test_upload_invalido_nao_substitui_documento_atual(self):
        self.enviar()
        self.usuario.refresh_from_db()
        anterior = self.usuario.documento_identidade.name
        Usuario.objects.filter(pk=self.usuario.pk).update(
            aprovacao_documento="aprovado",
        )
        self.enviar(SimpleUploadedFile("invalido.png", b"invalido"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.documento_identidade.name, anterior)
        self.assertEqual(self.usuario.aprovacao_documento, "aprovado")

    def test_dono_baixa_arquivo_com_headers_seguros(self):
        arquivo = self.imagem()
        conteudo = arquivo.read()
        arquivo.seek(0)
        self.enviar(arquivo)
        response = self.client.get(self.baixar_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), conteudo)
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_superusuario_pode_baixar_documento(self):
        self.enviar()
        self.client.force_login(self.superusuario)
        response = self.client.get(self.baixar_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content))

    def test_outro_usuario_e_funcionario_nao_podem_baixar(self):
        self.enviar()
        for usuario in (self.outro, self.funcionario):
            with self.subTest(usuario=usuario.pk):
                self.client.force_login(usuario)
                self.assertEqual(
                    self.client.get(self.baixar_url).status_code, 404,
                )

    def test_visitante_precisa_login_para_enviar_e_baixar(self):
        self.client.logout()
        for url in (self.enviar_url, self.baixar_url):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("core:entrar")))
        self.assertEqual(self.enviar().status_code, 302)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.documento_identidade)

    def test_documento_ausente_ou_arquivo_inexistente_retornam_404(self):
        self.assertEqual(self.client.get(self.baixar_url).status_code, 404)
        Usuario.objects.filter(pk=self.usuario.pk).update(
            documento_identidade="identidades/inexistente.png",
        )
        self.assertEqual(self.client.get(self.baixar_url).status_code, 404)

    def test_perfil_nao_publica_nome_ou_url_do_storage(self):
        self.enviar()
        self.usuario.refresh_from_db()
        nome = self.usuario.documento_identidade.name
        for url in (reverse("contas:perfil"), self.enviar_url):
            response = self.client.get(url)
            self.assertNotContains(response, nome)
            self.assertNotContains(response, 'href="/media/')
        response = self.client.get(reverse("contas:perfil"))
        self.assertContains(response, f'href="{self.baixar_url}"')

    def test_post_forjado_nao_altera_outro_usuario_ou_privilegios(self):
        self.enviar(
            pk=self.outro.pk, id=self.outro.pk, is_superuser="on",
            aprovacao_documento="aprovado", email="outro-email@example.com",
        )
        self.usuario.refresh_from_db()
        self.outro.refresh_from_db()
        self.assertFalse(self.outro.documento_identidade)
        self.assertFalse(self.usuario.is_superuser)
        self.assertEqual(self.usuario.email, "pessoa@example.com")
        self.assertEqual(self.usuario.aprovacao_documento, "pendente")

    def test_upload_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        response = client.post(self.enviar_url, {
            "documento_identidade": self.imagem(),
        })
        self.assertEqual(response.status_code, 403)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.documento_identidade)
