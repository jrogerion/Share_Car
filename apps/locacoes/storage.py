from django.core.files.storage import FileSystemStorage, storages


class ArmazenamentoVistoriasPrivado(FileSystemStorage):
    def url(self, name):
        raise ValueError("Fotos de vistoria exigem uma rota autenticada.")


def armazenamento_vistorias():
    return storages["vistorias"]
