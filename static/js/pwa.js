(() => {
  if (!window.isSecureContext || !("serviceWorker" in navigator)) {
    return;
  }
  const workerUrl = document.currentScript?.dataset.serviceWorkerUrl;
  if (!workerUrl) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(workerUrl, { updateViaCache: "none" })
      .catch(() => console.warn("Não foi possível ativar a PWA do ShareCar."));
  }, { once: true });
})();
