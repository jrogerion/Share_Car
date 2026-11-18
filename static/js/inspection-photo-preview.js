(() => {
  const form = document.querySelector("[data-inspection-form]");
  if (!form) return;
  const input = form.querySelector('input[type="file"][name="fotos"]');
  const previews = form.querySelector("[data-inspection-previews]");
  const status = form.querySelector("[data-inspection-photo-status]");
  if (!input || !previews || !status) return;
  let urls = [];

  const clear = () => {
    previews.querySelectorAll("img").forEach((image) => {
      image.onload = null;
      image.onerror = null;
      image.removeAttribute("src");
    });
    previews.replaceChildren();
    previews.hidden = true;
    urls.forEach((url) => URL.revokeObjectURL(url));
    urls = [];
  };
  const render = () => {
    clear();
    const files = [...input.files];
    if (!files.length) {
      status.textContent = "Selecione as fotos para conferir as prévias antes do envio.";
      return;
    }
    if (files.length > 6) {
      status.textContent = `${files.length} fotos selecionadas. O limite é de 6 fotos por vistoria; selecione novamente os arquivos.`;
      return;
    }
    status.textContent = `${files.length} foto(s) selecionada(s). Prévias locais: nenhum arquivo foi enviado. O servidor validará todas as fotos ao confirmar.`;
    previews.hidden = false;
    files.forEach((file, index) => {
      const figure = document.createElement("figure");
      const caption = document.createElement("figcaption");
      caption.textContent = `${index + 1}. ${file.name}`;
      figure.append(caption);
      previews.append(figure);
      const warn = (message) => {
        const warning = document.createElement("p");
        warning.className = "inspection-preview-warning";
        warning.textContent = message;
        figure.append(warning);
      };
      if (file.size > 5 * 1024 * 1024 ||
          (file.type && !["image/jpeg", "image/png"].includes(file.type))) {
        warn("Escolha uma imagem JPG ou PNG de até 5 MB.");
        return;
      }
      const image = document.createElement("img");
      image.alt = `Prévia da foto ${index + 1}, ainda não enviada`;
      image.width = 320;
      image.height = 200;
      const url = URL.createObjectURL(file);
      urls.push(url);
      image.onload = () => {
        if (image.naturalWidth * image.naturalHeight > 20000000) {
          image.remove();
          URL.revokeObjectURL(url);
          warn("A foto deve ter até 20 megapixels. Escolha uma imagem menor.");
        }
      };
      image.onerror = () => {
        image.remove();
        URL.revokeObjectURL(url);
        warn("Prévia indisponível. Verifique se a imagem é válida.");
      };
      image.src = url;
      figure.prepend(image);
    });
  };
  input.addEventListener("change", render);
  window.addEventListener("pageshow", render);
  window.addEventListener("pagehide", clear);
  render();
})();
