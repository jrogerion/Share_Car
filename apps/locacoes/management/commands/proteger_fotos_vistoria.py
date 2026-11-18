import hashlib
from pathlib import PurePosixPath

from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError

from apps.locacoes.models import FotoRegistroLocacao


def assinatura(storage, nome):
    digest = hashlib.sha256()
    with storage.open(nome, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


class Command(BaseCommand):
    help = (
        "Confere as fotos referenciadas no banco e prepara cópias privadas. "
        "Sem --executar, apenas verifica. Pare os uploads antes de executar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--executar", action="store_true")
        parser.add_argument(
            "--remover-originais", action="store_true",
            help="Remove somente originais públicos com cópia privada conferida. Exige autorização específica.",
        )

    def handle(self, *args, **options):
        executar = options["executar"]
        remover = options["remover_originais"]
        if remover and not executar:
            raise CommandError("--remover-originais exige --executar.")
        origem = storages["default"]
        destino = storages["vistorias"]
        if origem is destino or (
            getattr(origem, "location", None) is not None
            and getattr(origem, "location", None) == getattr(destino, "location", None)
        ):
            raise CommandError("Origem pública e destino privado precisam ser distintos.")
        plano = []
        privadas = 0
        nomes = FotoRegistroLocacao.objects.order_by("foto").values_list("foto", flat=True).distinct()
        # Pré-verificação completa: não iniciar cópias ou exclusões em caso de falta/conflito.
        for nome in nomes.iterator():
            partes = PurePosixPath(nome).parts
            if not nome or "\\" in nome or not nome.startswith("locacoes/") or ".." in partes:
                raise CommandError("Nome de arquivo incompatível; nenhuma limpeza foi iniciada.")
            publica = origem.exists(nome)
            privada = destino.exists(nome)
            if not publica:
                if not privada:
                    raise CommandError("Há foto sem arquivo público nem privado; revise o backup.")
                privadas += 1
                continue
            digest = assinatura(origem, nome)
            if privada and assinatura(destino, nome) != digest:
                raise CommandError("Conflito entre arquivo público e privado; nada será sobrescrito.")
            plano.append((nome, digest, privada))
        self.stdout.write(f"Fotos já privadas: {privadas}. Originais públicos referenciados: {len(plano)}.")
        if not executar:
            self.stdout.write("Somente verificação. Nenhum arquivo ou registro foi alterado.")
            return

        copias = 0
        for nome, digest, existente in plano:
            if not existente:
                with origem.open(nome, "rb") as arquivo:
                    gravado = destino.save(nome, arquivo)
                if gravado != nome:
                    raise CommandError("O armazenamento renomeou uma cópia; revise o destino. Originais preservados.")
                copias += 1
            if assinatura(destino, nome) != digest:
                raise CommandError("Falha de integridade na cópia privada. Originais preservados.")

        # Reconfere TODOS os arquivos antes de permitir a remoção do primeiro original.
        if remover:
            for nome, digest, _ in plano:
                if assinatura(origem, nome) != digest or assinatura(destino, nome) != digest:
                    raise CommandError("Arquivos mudaram durante a operação; limpeza interrompida.")
            for nome, _, _ in plano:
                origem.delete(nome)
            self.stdout.write(f"Originais públicos removidos após conferência: {len(plano)}.")
        else:
            self.stdout.write("Originais públicos mantidos. A limpeza autorizada ainda é necessária.")
        self.stdout.write(f"Cópias privadas criadas: {copias}. Referências do banco preservadas.")
