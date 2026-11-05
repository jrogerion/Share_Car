import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.reservas.models import Reserva
from apps.veiculos.models import Veiculo

from .models import Usuario

SENHA = "SenhaSegura!2026"


def criar_veiculo(proprietario, **dados):
    padrao = {
        "proprietario": proprietario,
        "caracteristicas": "Veículo de teste",
        "cidade": "São Paulo",
        "categoria": "Hatch",
        "cambio": "Manual",
        "combustivel": "Flex",
        "passageiros": 5,
        "preco_diaria": "150.00",
        "ativo": True,
        "bloqueado": False,
        "aprovacao": Veiculo.Aprovacao.APROVADO,
    }
    padrao.update(dados)
    return Veiculo.objects.create(**padrao)


def criar_reserva(veiculo, locatario, **dados):
    hoje = timezone.localdate()
    padrao = {
        "veiculo": veiculo,
        "locatario": locatario,
        "inicio": hoje + timedelta(days=2),
        "fim": hoje + timedelta(days=4),
        "status": Reserva.Status.SOLICITADA,
        "preco_diaria": "150.00",
        "valor_diarias": "300.00",
        "taxas": "0.00",
        "total": "300.00",
        "percentual_comissao": "10.00",
    }
    padrao.update(dados)
    return Reserva.objects.create(**padrao)


class CadastroTests(TestCase):
    """O cadastro deve criar a conta, definir papéis e autenticar o usuário."""

    def dados(self, **alteracoes):
        dados = {
            "username": "nova-pessoa",
            "first_name": "Nova",
            "last_name": "Pessoa",
            "email": "nova.pessoa@example.com",
            "papeis": ["locatario", "proprietario"],
            "password1": SENHA,
            "password2": SENHA,
        }
        dados.update(alteracoes)
        return dados

    def test_pagina_de_cadastro_exibe_formulario_e_papeis(self):
        response = self.client.get(reverse("contas:cadastro"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contas/cadastro.html")
        for campo in ("username", "email", "password1", "password2", "papeis"):
            with self.subTest(campo=campo):
                self.assertContains(response, f'name="{campo}"')
        self.assertContains(response, "Quero alugar veículos")
        self.assertContains(response, "Quero anunciar meu veículo")
        self.assertContains(response, reverse("core:entrar"))

    def test_cadastro_valido_cria_conta_e_autentica(self):
        response = self.client.post(
            reverse("contas:cadastro"),
            self.dados(),
        )

        self.assertRedirects(response, reverse("contas:painel"))
        usuario = Usuario.objects.get(username="nova-pessoa")
        self.assertTrue(usuario.locatario)
        self.assertTrue(usuario.proprietario)
        self.assertTrue(usuario.check_password(SENHA))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            usuario.pk,
        )

    def test_cadastro_exige_ao_menos_um_papel(self):
        response = self.client.post(
            reverse("contas:cadastro"),
            self.dados(papeis=[]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha pelo menos uma forma")
        self.assertFalse(
            Usuario.objects.filter(username="nova-pessoa").exists()
        )

    def test_cadastro_exige_email(self):
        response = self.client.post(
            reverse("contas:cadastro"),
            self.dados(email=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Usuario.objects.filter(username="nova-pessoa").exists()
        )

    def test_cadastro_impede_email_repetido_sem_diferenciar_maiusculas(self):
        Usuario.objects.create_user(
            username="existente",
            email="Pessoa@Example.com",
            password=SENHA,
        )

        response = self.client.post(
            reverse("contas:cadastro"),
            self.dados(email="pessoa@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe uma conta com este e-mail.")
        self.assertFalse(
            Usuario.objects.filter(username="nova-pessoa").exists()
        )

    def test_cadastro_impede_usuario_repetido(self):
        Usuario.objects.create_user(
            username="nova-pessoa",
            password=SENHA,
        )

        response = self.client.post(reverse("contas:cadastro"), self.dados())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Usuario.objects.filter(username="nova-pessoa").count(),
            1,
        )

    def test_cadastro_com_senhas_diferentes_nao_cria_conta(self):
        response = self.client.post(
            reverse("contas:cadastro"),
            self.dados(password2="OutraSenha!2026"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Usuario.objects.filter(username="nova-pessoa").exists()
        )

    def test_usuario_autenticado_e_redirecionado_ao_painel(self):
        usuario = Usuario.objects.create_user(
            username="conectado",
            password=SENHA,
            locatario=True,
        )
        self.client.force_login(usuario)

        response = self.client.get(reverse("contas:cadastro"))

        self.assertRedirects(response, reverse("contas:painel"))

    def test_pagina_de_entrada_oferece_cadastro_e_recuperacao(self):
        response = self.client.get(reverse("core:entrar"))

        self.assertContains(response, reverse("contas:cadastro"))
        self.assertContains(response, reverse("contas:recuperar_senha"))


class PerfilTests(TestCase):
    """O perfil deve permitir atualizar dados sem expor documentos privados."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_dir = tempfile.mkdtemp()
        cls.patch_storage = patch.object(
            Usuario._meta.get_field("documento_identidade"),
            "storage",
            FileSystemStorage(location=cls.private_dir),
        )
        cls.patch_storage.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch_storage.stop()
        shutil.rmtree(cls.private_dir, ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="perfil",
            email="perfil@example.com",
            password=SENHA,
            first_name="Nome",
            last_name="Antigo",
            locatario=True,
            proprietario=True,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados(self, **alteracoes):
        dados = {
            "first_name": "Nome",
            "last_name": "Atualizado",
            "email": "perfil@example.com",
            "papeis": ["locatario", "proprietario"],
            "cnh_numero": "",
            "cnh_validade": "",
        }
        dados.update(alteracoes)
        return dados

    def test_perfil_exige_autenticacao(self):
        self.client.logout()

        response = self.client.get(reverse("contas:perfil"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)

    def test_atualiza_dados_e_cnh(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                cnh_numero="12345678901",
                cnh_validade="2030-12-31",
            ),
        )

        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.last_name, "Atualizado")
        self.assertEqual(self.usuario.cnh_numero, "12345678901")
        self.assertEqual(
            self.usuario.cnh_validade.isoformat(),
            "2030-12-31",
        )
        self.assertEqual(
            self.usuario.aprovacao_cnh,
            Usuario.Aprovacao.PENDENTE,
        )

    def test_exige_numero_e_validade_da_cnh_juntos(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(cnh_numero="12345678901"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Informe o número e a validade da CNH juntos.",
        )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.cnh_numero, "")

    def test_documento_e_armazenado_fora_da_area_publica(self):
        arquivo = SimpleUploadedFile(
            "identidade.pdf",
            b"%PDF-1.4 documento de teste",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(documento_identidade=arquivo),
        )

        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.documento_identidade)
        caminho = Path(self.usuario.documento_identidade.path).resolve()
        self.assertTrue(caminho.exists())
        self.assertTrue(
            caminho.is_relative_to(Path(self.private_dir).resolve())
        )
        self.assertEqual(
            self.usuario.aprovacao_documento,
            Usuario.Aprovacao.PENDENTE,
        )

    def test_documento_nao_expoe_nome_ou_url_no_perfil(self):
        self.usuario.documento_identidade = SimpleUploadedFile(
            "documento-secreto.pdf",
            b"%PDF-1.4",
            content_type="application/pdf",
        )
        self.usuario.save()

        response = self.client.get(reverse("contas:perfil"))

        self.assertNotContains(response, "documento-secreto.pdf")
        self.assertNotContains(response, self.usuario.documento_identidade.url)
        self.assertContains(response, "armazenado em área privada")

    def test_troca_de_documento_reinicia_aprovacao(self):
        self.usuario.documento_identidade = SimpleUploadedFile(
            "antigo.pdf",
            b"%PDF-1.4",
            content_type="application/pdf",
        )
        self.usuario.aprovacao_documento = Usuario.Aprovacao.APROVADO
        self.usuario.save()

        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                documento_identidade=SimpleUploadedFile(
                    "novo.pdf",
                    b"%PDF-1.4 novo",
                    content_type="application/pdf",
                ),
            ),
        )

        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(
            self.usuario.aprovacao_documento,
            Usuario.Aprovacao.PENDENTE,
        )

    def test_troca_de_cnh_reinicia_aprovacao(self):
        self.usuario.cnh_numero = "11111111111"
        self.usuario.cnh_validade = timezone.localdate() + timedelta(days=365)
        self.usuario.aprovacao_cnh = Usuario.Aprovacao.APROVADO
        self.usuario.save()

        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                cnh_numero="22222222222",
                cnh_validade="2031-01-01",
            ),
        )

        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(
            self.usuario.aprovacao_cnh,
            Usuario.Aprovacao.PENDENTE,
        )

    def test_documento_com_extensao_invalida_e_rejeitado(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                documento_identidade=SimpleUploadedFile(
                    "arquivo.exe",
                    b"conteudo",
                    content_type="application/octet-stream",
                ),
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.documento_identidade)

    def test_documento_acima_do_limite_e_rejeitado(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                documento_identidade=SimpleUploadedFile(
                    "grande.pdf",
                    b"x" * (5 * 1024 * 1024 + 1),
                    content_type="application/pdf",
                ),
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no máximo 5 MB")
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.documento_identidade)

    def test_aprovacoes_nao_podem_ser_alteradas_pelo_formulario(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(
                aprovacao_documento=Usuario.Aprovacao.APROVADO,
                aprovacao_cnh=Usuario.Aprovacao.APROVADO,
                is_staff="True",
            ),
        )

        self.assertRedirects(response, reverse("contas:perfil"))
        self.usuario.refresh_from_db()
        self.assertEqual(
            self.usuario.aprovacao_documento,
            Usuario.Aprovacao.PENDENTE,
        )
        self.assertEqual(
            self.usuario.aprovacao_cnh,
            Usuario.Aprovacao.PENDENTE,
        )
        self.assertFalse(self.usuario.is_staff)

    def test_exige_ao_menos_um_papel(self):
        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(papeis=[]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escolha pelo menos uma forma")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.locatario)
        self.assertTrue(self.usuario.proprietario)

    def test_proprietario_com_veiculo_nao_pode_remover_papel(self):
        criar_veiculo(self.usuario, categoria="Veículo do perfil")

        response = self.client.post(
            reverse("contas:perfil"),
            self.dados(papeis=["locatario"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Você possui veículos cadastrados",
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.proprietario)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperacaoSenhaTests(TestCase):
    """A recuperação e a alteração de senha devem usar os fluxos do Django."""

    @classmethod
    def setUpTestData(cls):
        cls.usuario = Usuario.objects.create_user(
            username="recuperar",
            email="recuperar@example.com",
            password=SENHA,
            locatario=True,
        )

    def test_pagina_de_recuperacao_renderiza(self):
        response = self.client.get(reverse("contas:recuperar_senha"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "contas/recuperar_senha.html")
        self.assertContains(response, 'name="email"')

    def test_solicitacao_envia_link_e_permite_redefinir(self):
        response = self.client.post(
            reverse("contas:recuperar_senha"),
            {"email": "recuperar@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("contas:recuperar_senha_enviado"),
        )
        self.assertEqual(len(mail.outbox), 1)
        mensagem = mail.outbox[0]
        self.assertEqual(mensagem.to, ["recuperar@example.com"])
        self.assertIn("recuperar", mensagem.body)

        link = re.search(
            r"http://[^\s]+/conta/senha/redefinir/[^\s]+",
            mensagem.body,
        )
        self.assertIsNotNone(link)

        confirmacao = self.client.get(link.group(0), follow=True)
        self.assertEqual(confirmacao.status_code, 200)
        self.assertContains(confirmacao, 'name="new_password1"')

        nova_senha = "NovaSenha!2026"
        resposta = self.client.post(
            confirmacao.wsgi_request.path,
            {
                "new_password1": nova_senha,
                "new_password2": nova_senha,
            },
        )

        self.assertRedirects(
            resposta,
            reverse("contas:redefinir_senha_concluido"),
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(nova_senha))

    def test_email_desconhecido_nao_revela_cadastro(self):
        response = self.client.post(
            reverse("contas:recuperar_senha"),
            {"email": "ninguem@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("contas:recuperar_senha_enviado"),
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_link_invalido_informa_e_oferece_novo_pedido(self):
        uid = urlsafe_base64_encode(force_bytes(self.usuario.pk))

        response = self.client.get(
            reverse(
                "contas:redefinir_senha",
                kwargs={"uidb64": uid, "token": "token-invalido"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Link inválido")
        self.assertContains(response, "Solicite um novo link")
        self.assertContains(response, reverse("contas:recuperar_senha"))

    def test_alteracao_de_senha_exige_login(self):
        response = self.client.get(reverse("contas:alterar_senha"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)

    def test_alteracao_de_senha_com_senha_atual_valida(self):
        self.client.force_login(self.usuario)
        nova_senha = "OutraSenha!2026"

        response = self.client.post(
            reverse("contas:alterar_senha"),
            {
                "old_password": SENHA,
                "new_password1": nova_senha,
                "new_password2": nova_senha,
            },
        )

        self.assertRedirects(
            response,
            reverse("contas:alterar_senha_concluido"),
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(nova_senha))
        self.assertIn("_auth_user_id", self.client.session)

    def test_alteracao_com_senha_atual_incorreta_nao_altera(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse("contas:alterar_senha"),
            {
                "old_password": "senha-errada",
                "new_password1": "OutraSenha!2026",
                "new_password2": "OutraSenha!2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA))


class PainelTests(TestCase):
    """O painel deve mostrar indicadores apenas do próprio usuário."""

    @classmethod
    def setUpTestData(cls):
        cls.locatario = Usuario.objects.create_user(
            username="locatario-painel",
            email="locatario@example.com",
            password=SENHA,
            locatario=True,
        )
        cls.proprietario = Usuario.objects.create_user(
            username="proprietario-painel",
            email="proprietario@example.com",
            password=SENHA,
            proprietario=True,
        )
        cls.outro = Usuario.objects.create_user(
            username="outro-painel",
            email="outro@example.com",
            password=SENHA,
            proprietario=True,
            locatario=True,
        )

        cls.veiculo = criar_veiculo(
            cls.proprietario,
            categoria="Hatch do painel",
        )
        cls.outro_veiculo = criar_veiculo(
            cls.outro,
            categoria="Veículo de outro dono",
        )

        cls.reserva = criar_reserva(
            cls.veiculo,
            cls.locatario,
            status=Reserva.Status.SOLICITADA,
        )
        cls.reserva_aceita = criar_reserva(
            cls.outro_veiculo,
            cls.outro,
            status=Reserva.Status.ACEITA,
            inicio=timezone.localdate() + timedelta(days=10),
            fim=timezone.localdate() + timedelta(days=12),
        )

    def test_painel_exige_login(self):
        response = self.client.get(reverse("contas:painel"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:entrar"), response.url)

    def test_locatario_ve_apenas_secao_de_locatario(self):
        self.client.force_login(self.locatario)

        response = self.client.get(reverse("contas:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Como locatário")
        self.assertNotContains(response, "Como proprietário")
        self.assertEqual(response.context["resumo_locatario"]["total"], 1)
        self.assertEqual(response.context["resumo_locatario"]["ativas"], 0)
        self.assertEqual(
            response.context["resumo_locatario"]["solicitadas"],
            1,
        )
        self.assertNotContains(response, "Veículo de outro dono")

    def test_proprietario_ve_solicitacoes_e_veiculos(self):
        self.client.force_login(self.proprietario)

        response = self.client.get(reverse("contas:painel"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Como proprietário")
        self.assertNotContains(response, "Como locatário")
        self.assertEqual(
            response.context["resumo_proprietario"]["quantidade"],
            1,
        )
        self.assertEqual(
            response.context["resumo_proprietario"]["pendentes"],
            1,
        )
        self.assertEqual(response.context["resumo_veiculos"]["total"], 1)
        self.assertEqual(response.context["resumo_veiculos"]["publicados"], 1)
        self.assertContains(response, "locatario-painel")
        self.assertContains(response, "Hatch do painel")
        self.assertNotContains(response, "Veículo de outro dono")
        self.assertNotContains(response, "outro-painel")

    def test_usuario_com_dois_papeis_ve_as_duas_secoes(self):
        self.client.force_login(self.outro)

        response = self.client.get(reverse("contas:painel"))

        self.assertContains(response, "Como locatário")
        self.assertContains(response, "Como proprietário")
        self.assertEqual(response.context["resumo_locatario"]["ativas"], 1)
        self.assertEqual(response.context["resumo_proprietario"]["ativas"], 1)

    def test_usuario_sem_papel_recebe_orientacao(self):
        sem_papel = Usuario.objects.create_user(
            username="sem-papel",
            email="sem-papel@example.com",
            password=SENHA,
        )
        self.client.force_login(sem_papel)

        response = self.client.get(reverse("contas:painel"))

        self.assertContains(response, "Defina como você usa o ShareCar")
        self.assertContains(response, reverse("contas:perfil"))

    def test_painel_nao_expoe_documentos_nem_aprovacoes_editaveis(self):
        self.proprietario.documento_identidade.name = (
            "identidades/documento-privado.pdf"
        )
        self.proprietario.save(update_fields=["documento_identidade"])
        self.client.force_login(self.proprietario)

        response = self.client.get(reverse("contas:painel"))

        self.assertNotContains(response, "documento-privado.pdf")
        self.assertNotContains(response, self.proprietario.documento_identidade.url)
        self.assertNotContains(response, 'name="aprovacao_documento"')

    def test_navegacao_autenticada_aponta_para_o_painel(self):
        self.client.force_login(self.locatario)

        response = self.client.get(reverse("contas:painel"))

        self.assertContains(
            response,
            f'href="{reverse("contas:painel")}"',
        )
        self.assertContains(response, 'aria-current="page"')
