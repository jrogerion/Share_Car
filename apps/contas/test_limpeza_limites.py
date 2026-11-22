from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Event
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from .limites import consumir_tentativa
from .models import LimiteAcesso, Usuario


class LimpezaLimitesTests(TestCase):
    def setUp(self):
        self.agora = timezone.now()
        self.enterContext(patch(
            "apps.contas.management.commands.limpar_limites_acesso.timezone.now",
            return_value=self.agora,
        ))

    def contador(self, chave, horas):
        return LimiteAcesso.objects.create(
            chave=chave, expira_em=self.agora - timedelta(hours=horas),
            tentativas=5,
        )

    def comando(self, *args):
        saida = StringIO()
        call_command("limpar_limites_acesso", *args, stdout=saida)
        return saida.getvalue()

    def test_conferencia_padrao_nao_exclui_e_nao_expoe_chaves(self):
        contador = self.contador("chave-sigilosa-de-teste", 25)
        antes = list(LimiteAcesso.objects.values())
        saida = self.comando()
        self.assertEqual(list(LimiteAcesso.objects.values()), antes)
        self.assertIn("Somente conferência", saida)
        self.assertIn("conferência: 1", saida)
        self.assertNotIn(contador.chave, saida)

    def test_remove_somente_expirados_fora_da_retencao(self):
        self.contador("antigo", 25)
        self.contador("no-corte", 24)
        recente = self.contador("recente", 23)
        ativo = self.contador("ativo", -1)
        saida = self.comando("--executar")
        self.assertIn("removidos: 2", saida)
        self.assertCountEqual(
            LimiteAcesso.objects.values_list("pk", flat=True),
            [recente.pk, ativo.pk],
        )

    def test_respeita_microssegundo_no_limite_de_retencao(self):
        contador = LimiteAcesso.objects.create(
            chave="apos-corte", tentativas=5,
            expira_em=self.agora - timedelta(hours=24) + timedelta(microseconds=1),
        )
        self.comando("--executar")
        self.assertTrue(LimiteAcesso.objects.filter(pk=contador.pk).exists())

    def test_retencao_configuravel(self):
        recente = self.contador("recente", 25)
        self.contador("antigo", 49)
        self.comando("--executar", "--retencao-horas", "48")
        self.assertEqual(LimiteAcesso.objects.get().pk, recente.pk)

    def test_limite_e_repeticao_segura(self):
        for indice in range(7):
            self.contador(f"contador-{indice}", 25)
        self.comando("--executar", "--limite", "3")
        self.assertEqual(LimiteAcesso.objects.count(), 4)
        self.comando("--executar", "--limite", "3")
        self.assertEqual(LimiteAcesso.objects.count(), 1)
        self.comando("--executar", "--limite", "3")
        self.assertFalse(LimiteAcesso.objects.exists())

    def test_conferencia_tambem_respeita_limite(self):
        for indice in range(4):
            self.contador(f"contador-{indice}", 25)
        saida = self.comando("--limite", "2")
        self.assertIn("conferência: 2", saida)
        self.assertEqual(LimiteAcesso.objects.count(), 4)

    def test_processa_multiplos_lotes(self):
        LimiteAcesso.objects.bulk_create([
            LimiteAcesso(
                chave=f"contador-{indice}", tentativas=5,
                expira_em=self.agora - timedelta(hours=25),
            ) for indice in range(205)
        ])
        saida = self.comando("--executar", "--limite", "203")
        self.assertIn("removidos: 203", saida)
        self.assertEqual(LimiteAcesso.objects.count(), 2)

    def test_opcoes_invalidas_nao_alteram_registros(self):
        self.contador("antigo", 25)
        for flag, value in (
            ("--retencao-horas", "0"), ("--retencao-horas", "-1"),
            ("--retencao-horas", "99999999999999999"),
            ("--limite", "0"), ("--limite", "-1"), ("--limite", "10001"),
        ):
            with self.subTest(flag=flag, value=value):
                with self.assertRaises(CommandError):
                    self.comando("--executar", flag, value)
                self.assertEqual(LimiteAcesso.objects.count(), 1)

    def test_tabela_vazia(self):
        self.assertIn("removidos: 0", self.comando("--executar"))

    def test_preserva_usuarios(self):
        Usuario.objects.create_user("limpeza-ficticio", "limpeza@example.com")
        antes = list(Usuario.objects.values())
        self.contador("antigo", 25)
        self.comando("--executar")
        self.assertEqual(list(Usuario.objects.values()), antes)

    def test_limpeza_nao_reinicia_bloqueio_ativo(self):
        for _ in range(5):
            self.assertEqual(consumir_tentativa(
                "login", "192.0.2.30", "limpeza@example.com",
            ), 0)
        antes = list(LimiteAcesso.objects.order_by("pk").values())
        self.contador("antigo", 25)
        self.comando("--executar")
        self.assertEqual(list(LimiteAcesso.objects.order_by("pk").values()), antes)
        self.assertGreater(consumir_tentativa(
            "login", "192.0.2.30", "limpeza@example.com",
        ), 0)


class ConcorrenciaLimpezaTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update_skip_locked")
    def test_ignora_contador_em_renovacao_sem_impedir_outras_exclusoes(self):
        agora = timezone.now()
        em_uso = LimiteAcesso.objects.create(
            chave="em-uso", tentativas=5,
            expira_em=agora - timedelta(hours=25),
        )
        LimiteAcesso.objects.create(
            chave="livre", tentativas=5,
            expira_em=agora - timedelta(hours=25),
        )
        bloqueado = Event()
        liberar = Event()

        def renovar():
            close_old_connections()
            try:
                with transaction.atomic():
                    contador = LimiteAcesso.objects.select_for_update().get(pk=em_uso.pk)
                    contador.expira_em = agora + timedelta(minutes=5)
                    contador.tentativas = 1
                    contador.save(update_fields=["expira_em", "tentativas"])
                    bloqueado.set()
                    if not liberar.wait(timeout=15):
                        raise TimeoutError("Teste não liberou a transação isolada.")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(renovar)
            try:
                self.assertTrue(bloqueado.wait(timeout=10))
                saida = StringIO()
                call_command("limpar_limites_acesso", "--executar", stdout=saida)
                self.assertIn("removidos: 1", saida.getvalue())
            finally:
                liberar.set()
            future.result(timeout=10)
        em_uso.refresh_from_db()
        self.assertEqual(em_uso.tentativas, 1)
        self.assertEqual(em_uso.expira_em, agora + timedelta(minutes=5))
        self.assertEqual(LimiteAcesso.objects.count(), 1)
