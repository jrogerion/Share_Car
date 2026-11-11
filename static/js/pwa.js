(() => {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  const script = document.currentScript;
  const serviceWorkerUrl = script?.dataset.swUrl || "/sw.js";

  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register(serviceWorkerUrl, { scope: "/" })
      .catch((error) => {
        console.warn("Service worker não registrado:", error);
      });
  });
})();
