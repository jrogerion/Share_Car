(() => {
  const form = document.querySelector("[data-payment-form]");
  if (!form) return;
  const installments = form.querySelector('[name="parcelas"]');
  const field = form.querySelector("[data-payment-installments]");
  const options = [...document.querySelectorAll("[data-payment-option]")];
  if (!installments || !field || !options.length) return;

  const update = () => {
    const method = form.querySelector('[name="meio"]:checked')?.value;
    const pix = method === "pix";
    // O servidor revalida todas as condições, mesmo sem JavaScript.
    field.hidden = pix && !field.querySelector(".errorlist");
    installments.disabled = pix;
    if (pix) installments.value = "1";
    const quantity = installments.value || "1";
    options.forEach((option) => {
      option.hidden = Boolean(method) && (
        option.dataset.meio !== method || option.dataset.parcelas !== quantity
      );
    });
  };
  form.addEventListener("change", update);
  window.addEventListener("pageshow", update);
  update();
})();
