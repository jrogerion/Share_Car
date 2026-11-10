(() => {
  const forms = document.querySelectorAll("[data-search-form]");

  if (!forms.length) {
    return;
  }

  const setLoading = (form, loading) => {
    const button = form.querySelector("[data-search-submit]");
    const status = form.querySelector("[data-search-status]");
    const icon = form.querySelector("[data-search-icon]");
    const spinner = form.querySelector("[data-search-spinner]");
    const label = form.querySelector("[data-search-label]");

    if (loading) {
      form.setAttribute("aria-busy", "true");
    } else {
      form.removeAttribute("aria-busy");
    }

    if (button) {
      button.disabled = loading;
      if (loading) {
        button.setAttribute("aria-disabled", "true");
      } else {
        button.removeAttribute("aria-disabled");
      }
    }

    if (icon) {
      icon.hidden = loading;
    }

    if (spinner) {
      spinner.hidden = !loading;
    }

    if (label) {
      label.textContent = loading ? "Buscando..." : label.dataset.idleLabel;
    }

    if (status) {
      status.textContent = loading ? "Carregando resultados da busca..." : "";
    }
  };

  forms.forEach((form) => {
    const label = form.querySelector("[data-search-label]");

    if (label) {
      label.dataset.idleLabel = label.textContent.trim();
    }

    form.addEventListener("submit", () => setLoading(form, true));
  });

  // Restaura o formulário ao voltar pelo histórico ou pelo cache do navegador.
  window.addEventListener("pageshow", () => {
    forms.forEach((form) => setLoading(form, false));
  });
})();
