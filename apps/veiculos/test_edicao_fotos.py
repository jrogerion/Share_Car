from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from apps.contas.models import Usuario

from .forms import EdicaoVeiculoForm, ImagemVeiculoField
from .models import FotoVeiculo, Veiculo


class EdicaoFotosVeiculoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            "dono", "dono@example.com", "Senha-teste!72rT9",
            proprietario=True, aprovacao_documento="aprovado",
        )
        cls.outro = Usuario.objects.create_user("outro", "outro@example.com")
        cls.dados_base = {
            "caracteristicas": "Carro fictício para teste",
            "cidade": "Campinas", "categoria": "Hatch", "cambio": "Manual",
            "combustivel": "Flex", "passageiros": 5, "preco_diaria": "150.00",
        }
        cls.veiculo = Veiculo.objects.create(
            **cls.dados_base, proprietario=cls.usuario, aprovacao="aprovado",
        )
        cls.alheio = Veiculo.objects.create(
            **cls.dados_base, proprietario=cls.outro, aprovacao="aprovado",
        )

    def setUp(self):
        storage_patch = patch.object(
            FotoVeiculo._meta.get_field("foto"), "storage", InMemoryStorage(),
        )
        storage_patch.start()
        self.addCleanup(storage_patch.stop)
        self.client.force_login(self.usuario)
        self.editar_url = reverse("veiculos:editar", args=[self.veiculo.pk])
        self.fotos_url = reverse("veiculos:fotos", args=[self.veiculo.pk])
        self.dados = {**self.dados_base, "ativo": "on"}

    def imagem(self, formato="PNG", exif=False):
        buffer = BytesIO()
        kwargs = {}
        if exif:
            metadados = Image.Exif()
            metadados[0x010F] = "MARCA-PRIVADA-DE-TESTE"
            kwargs["exif"] = metadados
        Image.new("RGB", (8, 8), "white").save(
            buffer, format=formato, **kwargs,
        )
        extensao = "jpg" if formato == "JPEG" else formato.lower()
        return SimpleUploadedFile(
            f"nome-pessoal.{extensao}", buffer.getvalue(),
            content_type="application/octet-stream",
        )

    def test_visitante_precisa_login(self):
        self.client.logout()
        for url in (self.editar_url, self.fotos_url):
            response = self.client.get(url)
            self.assertRedirects(
                response, f'{reverse("core:entrar")}?next={url}',
            )
            self.assertEqual(
                self.client.post(url, self.dados).status_code, 302,
            )

    def test_dono_ve_formulario_e_links_em_meus_veiculos(self):
        response = self.client.get(self.editar_url)
        self.assertContains(response, 'value="Campinas"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, 'name="bloqueado"')
        self.assertIn("no-store", response["Cache-Control"])
        response = self.client.get(reverse("veiculos:meus"))
        self.assertContains(response, f'href="{self.editar_url}"')
        self.assertContains(response, f'href="{self.fotos_url}"')

    def test_outro_dono_nao_consulta_nem_altera(self):
        self.client.force_login(self.outro)
        for url in (self.editar_url, self.fotos_url):
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(
                self.client.post(url, self.dados).status_code, 404,
            )
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")
        self.assertFalse(FotoVeiculo.objects.exists())

    def test_alteracoes_de_dados_retornam_para_analise(self):
        response = self.client.post(self.editar_url, {
            **self.dados, "cidade": "São Paulo", "preco_diaria": "200.00",
        })
        self.assertRedirects(response, reverse("veiculos:meus"))
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.cidade, "São Paulo")
        self.assertEqual(str(self.veiculo.preco_diaria), "200.00")
        self.assertEqual(self.veiculo.aprovacao, "pendente")
        response = self.client.get(reverse("veiculos_api:lista"))
        ids = {item["id"] for item in response.json()["results"]}
        self.assertNotIn(self.veiculo.pk, ids)
        self.assertIn(self.alheio.pk, ids)

    def test_ativar_desativar_preserva_aprovacao_e_bloqueio(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(bloqueado=True)
        for ativo in ("", "on"):
            response = self.client.post(self.editar_url, {
                **self.dados, "ativo": ativo,
            })
            self.assertRedirects(response, reverse("veiculos:meus"))
            self.veiculo.refresh_from_db()
            self.assertEqual(self.veiculo.ativo, bool(ativo))
            self.assertEqual(self.veiculo.aprovacao, "aprovado")
            self.assertTrue(self.veiculo.bloqueado)

    def test_edicao_sem_alteracoes_preserva_aprovacao(self):
        self.client.post(self.editar_url, self.dados)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")

    def test_post_nao_transfere_dono_ou_remove_bloqueio(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(bloqueado=True)
        self.client.post(self.editar_url, {
            **self.dados, "caracteristicas": "Descrição atualizada",
            "proprietario": self.outro.pk, "aprovacao": "aprovado",
            "bloqueado": "", "pk": self.alheio.pk,
        })
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.proprietario_id, self.usuario.pk)
        self.assertTrue(self.veiculo.bloqueado)
        self.assertEqual(self.veiculo.aprovacao, "pendente")
        self.alheio.refresh_from_db()
        self.assertEqual(
            self.alheio.caracteristicas, self.dados_base["caracteristicas"],
        )

    def test_edicao_invalida_nao_salva(self):
        for campo, valor in (("preco_diaria", "0"), ("passageiros", "0"),
                             ("cidade", ""), ("caracteristicas", "")):
            with self.subTest(campo=campo):
                response = self.client.post(self.editar_url, {
                    **self.dados, campo: valor,
                })
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")

    def test_edicao_nao_sobrescreve_decisao_administrativa_concorrente(self):
        self.veiculo.refresh_from_db()
        form = EdicaoVeiculoForm(self.dados, instance=self.veiculo)
        self.assertTrue(form.is_valid())
        Veiculo.objects.filter(pk=self.veiculo.pk).update(
            bloqueado=True, aprovacao="rejeitado",
        )
        form.save()
        self.veiculo.refresh_from_db()
        self.assertTrue(self.veiculo.bloqueado)
        self.assertEqual(self.veiculo.aprovacao, "rejeitado")

    def test_upload_jpeg_e_png_com_reaprovacao(self):
        for formato in ("JPEG", "PNG"):
            with self.subTest(formato=formato):
                response = self.client.post(self.fotos_url, {
                    "foto": self.imagem(formato),
                    "veiculo": self.alheio.pk, "aprovacao": "aprovado",
                })
                self.assertRedirects(response, self.fotos_url)
        self.assertEqual(self.veiculo.fotos.count(), 2)
        self.assertFalse(self.alheio.fotos.exists())
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "pendente")
        for foto in self.veiculo.fotos.all():
            self.assertRegex(
                foto.foto.name, r"^veiculos/[0-9a-f]{32}\.(jpg|png)$",
            )
            with foto.foto.open("rb") as arquivo:
                Image.open(arquivo).verify()

    def test_rejeita_arquivo_ausente_gif_pdf_e_conteudo_falso(self):
        casos = (
            {}, {"foto": self.imagem("GIF")},
            {"foto": SimpleUploadedFile("arquivo.pdf", b"%PDF-1.4 teste")},
            {"foto": SimpleUploadedFile(
                "falso.png", b"nao-e-imagem", "image/png",
            )},
        )
        for dados in casos:
            response = self.client.post(self.fotos_url, dados)
            self.assertEqual(response.status_code, 200)
            self.assertIn("foto", response.context["form"].errors)
        self.assertFalse(FotoVeiculo.objects.exists())
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.aprovacao, "aprovado")

    def test_rejeita_arquivo_acima_de_5mb(self):
        arquivo = self.imagem()
        arquivo.size = 5 * 1024 * 1024 + 1
        with self.assertRaisesMessage(ValidationError, "no máximo 5 MB"):
            ImagemVeiculoField().clean(arquivo)

    def test_rejeita_resolucao_excessiva_antes_de_decodificar(self):
        arquivo = SimpleNamespace(image=SimpleNamespace(
            format="PNG", width=5000, height=4001,
        ))
        with patch("django.forms.ImageField.to_python", return_value=arquivo):
            with self.assertRaisesMessage(ValidationError, "20 megapixels"):
                ImagemVeiculoField().to_python(None)

    def test_nao_aceita_varias_fotos_no_mesmo_envio(self):
        response = self.client.post(self.fotos_url, {
            "foto": [self.imagem(), self.imagem()],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Envie uma foto por vez.")
        self.assertFalse(FotoVeiculo.objects.exists())

    def test_foto_publica_sem_exif_ou_conteudo_anexado(self):
        arquivo = self.imagem("JPEG", exif=True)
        dados = arquivo.read() + b"CONTEUDO-ANEXADO-DE-TESTE"
        arquivo = SimpleUploadedFile("pessoal.jpg", dados, "image/jpeg")
        self.client.post(self.fotos_url, {"foto": arquivo})
        foto = FotoVeiculo.objects.get()
        with foto.foto.open("rb") as salvo:
            conteudo = salvo.read()
        self.assertNotIn(b"CONTEUDO-ANEXADO-DE-TESTE", conteudo)
        self.assertNotIn(b"MARCA-PRIVADA-DE-TESTE", conteudo)
        with Image.open(BytesIO(conteudo)) as imagem:
            self.assertFalse(imagem.getexif())

    def test_galeria_e_links(self):
        response = self.client.get(self.fotos_url)
        self.assertContains(response, "Nenhuma foto cadastrada.")
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.client.post(self.fotos_url, {"foto": self.imagem()})
        foto = FotoVeiculo.objects.get()
        response = self.client.get(self.fotos_url)
        self.assertContains(response, f'src="{foto.foto.url}"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_foto_nao_remove_bloqueio_ou_desativacao(self):
        Veiculo.objects.filter(pk=self.veiculo.pk).update(
            bloqueado=True, ativo=False,
        )
        self.client.post(self.fotos_url, {"foto": self.imagem()})
        self.veiculo.refresh_from_db()
        self.assertTrue(self.veiculo.bloqueado)
        self.assertFalse(self.veiculo.ativo)

    def test_rotas_rejeitam_post_sem_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(
            client.post(self.editar_url, self.dados).status_code, 403,
        )
        response = client.post(self.fotos_url, {"foto": self.imagem()})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(FotoVeiculo.objects.exists())

    def test_conta_inativa_nao_edita_ou_envia_foto(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(is_active=False)
        for url in (self.editar_url, self.fotos_url):
            response = self.client.post(url, self.dados)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("core:entrar")))
