(() => {
  // Somente formulários de edição; buscas e ações administrativas mantêm seu fluxo.
  const forms = [...document.querySelectorAll('form.flow-fields[method="post"]')];
  const states = new WeakMap();
  const restoreAttribute = (element, name, value) => {
    if (value === null) element.removeAttribute(name);
    else element.setAttribute(name, value);
  };
  const reset = (form) => {
    const state = states.get(form);
    if (!state) return;
    restoreAttribute(form, "aria-busy", state.busy);
    state.buttons.forEach(({ button, disabled }) => {
      restoreAttribute(button, "aria-disabled", disabled);
    });
    state.spinner?.remove();
    state.status.textContent = "";
    states.delete(form);
  };
  forms.forEach((form) => {
    const status = document.createElement("p");
    status.className = "form-submit-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-atomic", "true");
    // Fora do aria-busy do formulário para não silenciar o aviso de envio.
    form.after(status);
    form.addEventListener("submit", (event) => {
      if (states.has(form)) {
        event.preventDefault();
        return;
      }
      if (event.defaultPrevented) return;
      const buttons = [...form.querySelectorAll('button:not([type]), button[type="submit"], input[type="submit"]')];
      const state = {
        busy: form.getAttribute("aria-busy"), status,
        buttons: buttons.map((button) => ({ button, disabled: button.getAttribute("aria-disabled") })),
      };
      states.set(form, state);
      form.setAttribute("aria-busy", "true");
      // Não usar disabled: preserva o nome/valor do botão no envio nativo.
      buttons.forEach((button) => button.setAttribute("aria-disabled", "true"));
      const submitter = event.submitter || buttons[0];
      if (submitter?.tagName === "BUTTON") {
        const spinner = document.createElement("span");
        spinner.className = "spinner-border spinner-border-sm form-submit-spinner";
        spinner.setAttribute("aria-hidden", "true");
        submitter.prepend(spinner);
        state.spinner = spinner;
      }
      status.textContent = form.enctype === "multipart/form-data"
        ? "Enviando dados e arquivos… aguarde a confirmação."
        : "Enviando… aguarde a confirmação.";
      // Outro componente pode cancelar o envio após este listener.
      queueMicrotask(() => {
        if (event.defaultPrevented && states.get(form) === state) reset(form);
      });
    });
  });
  window.addEventListener("pageshow", () => forms.forEach(reset));
  const errors = document.querySelector("[data-form-errors]");
  if (errors && !location.hash) errors.focus();
})();
