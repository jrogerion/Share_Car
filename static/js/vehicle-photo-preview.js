(() => {
  const form = document.querySelector("[data-photo-preview-form]");
  if (!form) return;
  const input = form.querySelector('input[type="file"]');
  const preview = form.querySelector("[data-photo-preview]");
  const image = form.querySelector("[data-photo-preview-image]");
  const caption = form.querySelector("[data-photo-preview-caption]");
  const status = form.querySelector("[data-photo-preview-status]");
  let objectUrl;
  const clear = () => {
    image.onload = null;
    image.onerror = null;
    image.removeAttribute("src");
    preview.hidden = true;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  };
  input.addEventListener("change", () => {
    clear();
    const file = input.files[0];
    if (!file) {
      status.textContent = "Selecione uma foto para conferir a prévia antes de enviar.";
      return;
    }
    if (!["image/jpeg", "image/png"].includes(file.type) || file.size > 5 * 1024 * 1024) {
      status.textContent = "A prévia aceita JPEG ou PNG de até 5 MB. Confira o arquivo selecionado.";
      return;
    }
    status.textContent = "Carregando prévia…";
    objectUrl = URL.createObjectURL(file);
    image.onload = () => {
      if (image.naturalWidth * image.naturalHeight > 20000000) {
        clear();
        status.textContent = "A foto deve ter até 20 megapixels. Escolha uma imagem menor.";
        return;
      }
      caption.textContent = `${file.name} · ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
      preview.hidden = false;
      status.textContent = "Prévia local. A foto só será enviada ao clicar em Adicionar foto e será validada pelo servidor.";
    };
    image.onerror = () => {
      clear();
      status.textContent = "Não foi possível exibir a prévia. Verifique se a imagem é válida.";
    };
    image.src = objectUrl;
  });
  window.addEventListener("pagehide", clear);
})();
