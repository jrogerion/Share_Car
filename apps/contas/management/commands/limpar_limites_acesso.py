from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.contas.models import LimiteAcesso


class Command(BaseCommand):
    help = (
        "Confere contadores expirados, mantendo 24h após a expiração por padrão. "
        "Somente --executar permite excluir. Exige autorização para o banco alvo."
    )

    def add_arguments(self, parser):
        parser.add_argument("--executar", action="store_true")
        parser.add_argument(
            "--retencao-horas", type=int, default=24,
            help="Horas a manter após a expiração (mínimo 1; padrão 24).",
        )
        parser.add_argument(
            "--limite", type=int, default=1000,
            help="Máximo de contadores por execução (1 a 10000; padrão 1000).",
        )

    def handle(self, *args, **options):
        horas = options["retencao_horas"]
        limite = options["limite"]
        if horas < 1:
            raise CommandError("--retencao-horas deve ser pelo menos 1.")
        if not 1 <= limite <= 10000:
            raise CommandError("--limite deve estar entre 1 e 10000.")
        try:
            corte = timezone.now() - timedelta(hours=horas)
        except OverflowError as error:
            raise CommandError(
                "--retencao-horas fora do intervalo suportado.",
            ) from error

        elegiveis = LimiteAcesso.objects.filter(expira_em__lte=corte)
        quantidade = elegiveis[:limite].count()
        self.stdout.write(
            f"Retenção após expiração: {horas}h. Corte: {corte.isoformat()}."
        )
        self.stdout.write(
            f"Contadores elegíveis nesta conferência: {quantidade} "
            f"(máximo {limite})."
        )
        if not options["executar"]:
            self.stdout.write(
                "Somente conferência. Nenhum registro foi alterado. "
                "A exclusão exige --executar e autorização para o banco alvo."
            )
            return

        removidos = 0
        while removidos < limite:
            with transaction.atomic():
                # Login trava IP antes do par IP/identificador. Não esperamos
                # por linhas em uso, evitando disputa e inversão desses locks.
                chaves = list(
                    elegiveis.select_for_update(skip_locked=True)
                    .order_by("expira_em", "chave")
                    .values_list("chave", flat=True)[:min(100, limite - removidos)]
                )
                if not chaves:
                    break
                # O corte é fixo durante toda a execução. A condição é mantida
                # no DELETE para não alargar a seleção de dados elegíveis.
                quantidade, _ = elegiveis.filter(chave__in=chaves).delete()
            removidos += quantidade
            if not quantidade:
                break
        self.stdout.write(
            f"Contadores expirados removidos: {removidos}. "
            "Linhas em uso são ignoradas; pode haver elegíveis remanescentes."
        )
