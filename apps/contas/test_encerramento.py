from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.pagamentos.models import Pagamento
from apps.reservas.models import Reserva
from apps.reservas.services import ReservaInvalida, criar_reserva
from apps.veiculos.consultas import veiculos_publicos
from apps.veiculos.models import FotoVeiculo, Veiculo

from .models import AlteracaoEmail, Usuario
from .services import encerrar_conta, solicitar_alteracao_email


def carro_ficticio(dono):
    return Veiculo.objects.create(
        proprietario=dono, caracteristicas="Carro fictício do encerramento",
        cidade="Campinas", categoria="Hatch", cambio="Manual", combustivel="Flex",
        passageiros=5, preco_diaria="150.00", aprovacao="aprovado",
    )


def reserva_ficticia(carro, locatario, status, dias=5):
    inicio = timezone.localdate() + timedelta(days=dias)
    return Reserva.objects.create(
        veiculo=carro, locatario=locatario, inicio=inicio,
        fim=inicio + timedelta(days=1), status=status, preco_diaria="150.00",
        valor_diarias="150.00", taxas=0, total="150.00", percentual_comissao="15.00",
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EncerramentoContaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.senha = "SenhaFicticia!72rT9"
        cls.usuario = Usuario.objects.create_user(
            "encerrar-ficticio", "encerrar@example.com", cls.senha,
            first_name="Pessoa", last_name="Fictícia", proprietario=True,
            locatario=True, aprovacao_documento="aprovado", aprovacao_cnh="aprovado",
            cnh_numero="CNH-FICTICIA", cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.outro = Usuario.objects.create_user(
            "outra-conta", "outra-conta@example.com", cls.senha,
            locatario=True, proprietario=True, aprovacao_documento="aprovado",
            aprovacao_cnh="aprovado", cnh_numero="CNH-FICTICIA",
            cnh_validade=timezone.localdate() + timedelta(days=365),
        )
        cls.admin = Usuario.objects.create_superuser(
            "admin-encerramento", "admin-encerramento@example.com", cls.senha,
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.carro = carro_ficticio(self.usuario)

    def encerrar(self, **dados):
        return self.client.post(reverse("contas:encerrar"), {
            "senha_atual": self.senha, "confirmacao": "on", **dados,
        })

    def test_get_apenas_exibe_consequencias(self):
        antes = list(Usuario.objects.values())
        response = self.client.get(reverse("contas:encerrar"))
        self.assertContains(response, "não é exclusão definitiva")
        self.assertContains(response, "e-mail continuará reservado")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(list(Usuario.objects.values()), antes)
        self.carro.refresh_from_db()
        self.assertTrue(self.carro.ativo)

    def test_exige_senha_atual(self):
        response = self.encerrar(senha_atual="NaoMostrarSenhaErrada!41")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "NaoMostrarSenhaErrada!41")
        self.assertIn("senha_atual", response.wsgi_request.sensitive_post_parameters)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)
        self.assertIsNone(self.usuario.encerrada_em)

    def test_link_no_perfil_somente_para_contas_pessoais(self):
        self.assertContains(self.client.get(reverse("contas:perfil")), reverse("contas:encerrar"))
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse("contas:perfil")), reverse("contas:encerrar"))

    def test_exige_confirmacao_explicita(self):
        response = self.encerrar(confirmacao="")
        self.assertContains(response, "Confirme que deseja encerrar sua conta.")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_encerramento_desativa_sem_apagar_identidade(self):
        nome, email, pk = self.usuario.nome_exibicao, self.usuario.email, self.usuario.pk
        response = self.encerrar(usuario=self.outro.pk, is_active="on", email="forjado@example.com")
        self.assertRedirects(response, reverse("contas:encerrada"))
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.pk, pk)
        self.assertEqual(self.usuario.nome_exibicao, nome)
        self.assertEqual(self.usuario.email, email)
        self.assertFalse(self.usuario.is_active)
        self.assertIsNotNone(self.usuario.encerrada_em)
        self.assertFalse(self.usuario.has_usable_password())
        self.carro.refresh_from_db()
        self.assertFalse(self.carro.ativo)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.outro.refresh_from_db()
        self.assertTrue(self.outro.is_active)

    def test_bloqueia_reservas_nao_finalizadas_nos_dois_papeis(self):
        carro_outro = carro_ficticio(self.outro)
        for status in ("solicitada", "aceita", "em_andamento"):
            for papel in ("locatario", "proprietario"):
                with self.subTest(status=status, papel=papel):
                    carro = carro_outro if papel == "locatario" else self.carro
                    locatario = self.usuario if papel == "locatario" else self.outro
                    # Não usar POST aqui: a regra também precisa proteger o serviço.
                    reserva = reserva_ficticia(carro, locatario, status)
                    with self.assertRaises(ValidationError):
                        encerrar_conta(usuario=self.usuario, senha_atual=self.senha)
                    self.usuario.refresh_from_db()
                    self.assertTrue(self.usuario.is_active)
                    self.assertIsNone(self.usuario.encerrada_em)
                    reserva.status = "cancelada"
                    reserva.save(update_fields=["status"])

    def test_reserva_antiga_ainda_ativa_tambem_impede(self):
        reserva_ficticia(self.carro, self.outro, "aceita", dias=-30)
        response = self.encerrar()
        self.assertContains(response, "Finalize, cancele ou recuse")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_preserva_reservas_e_pagamentos_finalizados(self):
        reserva = reserva_ficticia(self.carro, self.outro, "concluida", dias=-10)
        Pagamento.objects.create(
            reserva=reserva, meio="pix", status="aprovado", valor_bruto="150.00",
            comissao="22.50", repasse_proprietario="127.50",
        )
        reserva_ficticia(self.carro, self.outro, "cancelada", dias=-5)
        reserva_ficticia(self.carro, self.outro, "recusada", dias=-1)
        antes = [list(model.objects.values()) for model in (Reserva, Pagamento)]
        self.assertEqual(self.encerrar().status_code, 302)
        self.assertEqual([list(model.objects.values()) for model in (Reserva, Pagamento)], antes)

    def test_documentos_e_fotos_permanecem_armazenados(self):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
        with patch.object(Usuario._meta.get_field("documento_identidade"), "storage", InMemoryStorage()), patch.object(FotoVeiculo._meta.get_field("foto"), "storage", InMemoryStorage()):
            self.usuario.documento_identidade = SimpleUploadedFile("documento-ficticio.png", buffer.getvalue(), "image/png")
            self.usuario.save(update_fields=["documento_identidade"])
            foto = FotoVeiculo.objects.create(veiculo=self.carro, foto=SimpleUploadedFile("carro-ficticio.png", buffer.getvalue(), "image/png"))
            self.assertEqual(self.encerrar().status_code, 302)
            self.usuario.refresh_from_db()
            self.assertTrue(self.usuario.documento_identidade.storage.exists(self.usuario.documento_identidade.name))
            self.assertTrue(foto.foto.storage.exists(foto.foto.name))
            self.assertEqual(FotoVeiculo.objects.count(), 1)
            url = reverse("contas:documento_identidade", args=[self.usuario.pk])
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.admin)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(b"".join(response.streaming_content))

    def test_cancela_solicitacao_de_email_pendente(self):
        _, token = solicitar_alteracao_email(
            usuario=self.usuario, novo_email="novo-encerrar@example.com", senha_atual=self.senha,
        )
        self.assertEqual(self.encerrar().status_code, 302)
        self.assertFalse(AlteracaoEmail.objects.filter(usuario=self.usuario).exists())
        self.assertEqual(self.client.get(reverse("contas:confirmar_email_link", args=[token])).status_code, 302)

    def test_falha_desfaz_desativacao_de_anuncios_e_cancelamento_de_pedido(self):
        solicitar_alteracao_email(usuario=self.usuario, novo_email="pendente@example.com", senha_atual=self.senha)
        antes = [list(model.objects.values()) for model in (Usuario, Veiculo, AlteracaoEmail)]
        with patch("apps.contas.services.Usuario.save", side_effect=RuntimeError("falha simulada")):
            with self.assertRaises(RuntimeError):
                encerrar_conta(usuario=self.usuario, senha_atual=self.senha)
        self.assertEqual([list(model.objects.values()) for model in (Usuario, Veiculo, AlteracaoEmail)], antes)

    def test_cadastro_em_andamento_revalida_conta_antes_de_salvar(self):
        encerrar_conta(usuario=self.usuario, senha_atual=self.senha)
        # Simula request já autenticado antes do encerramento. O form_valid
        # deve consultar a conta atual, não confiar nessa instância antiga.
        with patch("apps.contas.backends.EmailBackend.get_user", return_value=self.usuario):
            response = self.client.post(reverse("core:veiculo"), {
                "caracteristicas": "Anúncio não pode ser criado",
                "cidade": "Campinas", "categoria": "Hatch", "cambio": "Manual",
                "combustivel": "Flex", "passageiros": 5, "preco_diaria": "100.00",
            })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Veiculo.objects.count(), 1)

    def test_outros_dispositivos_perdem_acesso(self):
        outro_dispositivo = Client()
        outro_dispositivo.force_login(self.usuario)
        self.encerrar()
        self.assertEqual(outro_dispositivo.get(reverse("contas:perfil")).status_code, 302)
        self.assertEqual(outro_dispositivo.get(reverse("reservas:minhas")).status_code, 302)

    def test_login_e_recuperacao_nao_reativam_conta(self):
        token_anterior = default_token_generator.make_token(self.usuario)
        self.encerrar()
        self.usuario.refresh_from_db()
        self.assertFalse(default_token_generator.check_token(self.usuario, token_anterior))
        self.assertIsNone(authenticate(email=self.usuario.email, password=self.senha))
        self.assertIsNone(authenticate(username=self.usuario.username, password=self.senha))
        response = self.client.post(reverse("contas:recuperar_senha"), {"email": self.usuario.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_permanece_reservado(self):
        self.encerrar()
        response = self.client.post(reverse("contas:cadastro"), {
            "email": self.usuario.email, "first_name": "Outra", "last_name": "Pessoa",
            "locatario": "on", "password1": self.senha, "password2": self.senha,
        })
        self.assertContains(response, "Não é possível cadastrar este e-mail.")

    def test_administrador_nao_pode_encerrar_pelo_fluxo_pessoal(self):
        for flag in ("is_staff", "is_superuser"):
            usuario = Usuario.objects.create_user(f"protegido-{flag}", password=self.senha, **{flag: True})
            self.client.force_login(usuario)
            self.assertRedirects(self.encerrar(), reverse("administracao:painel"))
            with self.assertRaises(ValidationError):
                encerrar_conta(usuario=usuario, senha_atual=self.senha)
            usuario.refresh_from_db()
            self.assertTrue(usuario.is_active)

    def test_administracao_nao_reativa_conta_encerrada(self):
        self.encerrar()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("administracao:bloqueio_usuario", args=[self.usuario.pk]))
        self.assertRedirects(response, reverse("administracao:painel"))
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertIsNotNone(self.usuario.encerrada_em)
        self.assertContains(self.client.get(reverse("administracao:painel")), "Encerrada pelo titular")

    def test_django_admin_mantem_conta_encerrada_somente_leitura(self):
        self.encerrar()
        self.client.force_login(self.admin)
        url = reverse("admin:contas_usuario_change", args=[self.usuario.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"is_active": "on"}).status_code, 403)
        senha_url = reverse("admin:auth_user_password_change", args=[self.usuario.pk])
        self.assertEqual(self.client.post(senha_url, {"password1": self.senha, "password2": self.senha}).status_code, 403)

    def test_constraint_impede_reativacao_acidental(self):
        self.encerrar()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.filter(pk=self.usuario.pk).update(is_active=True)

    def test_anuncio_nao_reaparece_se_ativo_for_alterado_manualmente(self):
        self.encerrar()
        Veiculo.objects.filter(pk=self.carro.pk).update(ativo=True)
        self.assertFalse(veiculos_publicos().filter(pk=self.carro.pk).exists())
        self.assertEqual(self.client.get(reverse("core:detalhes", args=[self.carro.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("veiculos_api:detalhe", args=[self.carro.pk])).status_code, 404)
        self.carro.refresh_from_db()
        with self.assertRaises(ReservaInvalida):
            criar_reserva(veiculo=self.carro, locatario=self.outro,
                          inicio=timezone.localdate()+timedelta(days=10),
                          fim=timezone.localdate()+timedelta(days=11))

    def test_visitante_e_metodos_nao_permitidos(self):
        self.assertEqual(self.client.put(reverse("contas:encerrar"), "{}", content_type="application/json").status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("contas:encerrar")).status_code, 302)
        self.assertEqual(self.client.post(reverse("contas:encerrar"), {}).status_code, 302)

    def test_csrf_e_origem_continuam_exigidos(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.usuario)
        self.assertEqual(client.post(reverse("contas:encerrar"), {}).status_code, 403)
        client.get(reverse("contas:encerrar"))
        data = {"csrfmiddlewaretoken": client.cookies["csrftoken"].value,
                "senha_atual": self.senha, "confirmacao": "on"}
        for origem in ("null", "https://intruso.example"):
            self.assertEqual(client.post(reverse("contas:encerrar"), data, HTTP_ORIGIN=origem).status_code, 403)
        self.assertEqual(client.post(reverse("contas:encerrar"), data, HTTP_ORIGIN="http://testserver").status_code, 302)

    def test_alias_compartilha_limite_de_tentativas(self):
        for _ in range(3):
            self.assertEqual(self.encerrar(senha_atual="incorreta").status_code, 200)
        response = self.client.post(reverse("contas_legacy:encerrar"), {
            "senha_atual": self.senha, "confirmacao": "on",
        })
        self.assertEqual(response.status_code, 429)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_pagina_publica_de_resultado_nao_encerra_por_get(self):
        self.assertEqual(self.client.get(reverse("contas:encerrada")).status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)


class ConcorrenciaEncerramentoTests(TransactionTestCase):
    def setUp(self):
        self.senha = "SenhaFicticia!72rT9"
        dados = {"proprietario": True, "locatario": True, "aprovacao_documento": "aprovado",
                 "aprovacao_cnh": "aprovado", "cnh_numero": "CNH-FICTICIA",
                 "cnh_validade": timezone.localdate()+timedelta(days=365)}
        self.dono = Usuario.objects.create_user("dono-fechar", "dono-fechar@example.com", self.senha, **dados)
        self.loc = Usuario.objects.create_user("loc-fechar", "loc-fechar@example.com", self.senha, **dados)
        self.carro = carro_ficticio(self.dono)

    def paralelos(self, funcoes):
        barrier = Barrier(2)

        def chamar(funcao):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                try:
                    funcao()
                except (ValidationError, ReservaInvalida):
                    return False
                return True
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(chamar, funcoes))

    def test_reserva_simultanea_com_fechamento_do_proprietario(self):
        self.disputar(self.dono)

    def test_reserva_simultanea_com_fechamento_do_locatario(self):
        self.disputar(self.loc)

    def disputar(self, usuario):
        inicio = timezone.localdate()+timedelta(days=5)
        resultados = self.paralelos([
            lambda: encerrar_conta(usuario=usuario, senha_atual=self.senha),
            lambda: criar_reserva(veiculo=self.carro, locatario=self.loc,
                                 inicio=inicio, fim=inicio+timedelta(days=1)),
        ])
        self.assertEqual(sum(resultados), 1)
        usuario.refresh_from_db()
        self.assertEqual(Reserva.objects.exists(), usuario.is_active)
        if not usuario.is_active:
            self.assertIsNotNone(usuario.encerrada_em)

    def test_duplo_encerramento_nao_altera_data_novamente(self):
        resultados = self.paralelos([
            lambda: encerrar_conta(usuario=self.loc, senha_atual=self.senha),
            lambda: encerrar_conta(usuario=self.loc, senha_atual=self.senha),
        ])
        self.assertEqual(sum(resultados), 1)
        self.loc.refresh_from_db()
        self.assertFalse(self.loc.is_active)

    def test_anuncio_criado_antes_do_lock_da_conta_tambem_e_desativado(self):
        pronto, inserir = Event(), Event()

        def criar_anuncio():
            close_old_connections()
            try:
                with transaction.atomic():
                    dono = Usuario.objects.select_for_update().get(pk=self.dono.pk)
                    pronto.set()
                    if not inserir.wait(timeout=15):
                        raise TimeoutError("Teste não liberou criação isolada.")
                    carro_ficticio(dono)
            finally:
                connections.close_all()

        selecionar = Usuario.objects.select_for_update

        def permitir_insercao(*args, **kwargs):
            inserir.set()
            return selecionar(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(criar_anuncio)
            try:
                self.assertTrue(pronto.wait(timeout=10))
                with patch("apps.contas.services.Usuario.objects.select_for_update", side_effect=permitir_insercao) as lock:
                    encerrar_conta(usuario=self.dono, senha_atual=self.senha)
                    self.assertGreaterEqual(lock.call_count, 2)
            finally:
                inserir.set()
            future.result(timeout=10)
        self.assertEqual(Veiculo.objects.filter(proprietario=self.dono).count(), 2)
        self.assertFalse(Veiculo.objects.filter(proprietario=self.dono, ativo=True).exists())
