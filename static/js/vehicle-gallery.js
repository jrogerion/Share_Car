(() => {
  const gallery = document.querySelector("[data-vehicle-gallery]");
  if (!gallery) return;
  const figures = [...gallery.querySelectorAll("figure")];
  if (figures.length < 2) return;

  const thumbnails = document.createElement("div");
  thumbnails.className = "detail-thumbnails";
  thumbnails.setAttribute("role", "group");
  thumbnails.setAttribute("aria-label", "Escolher foto do veículo");
  const status = document.createElement("p");
  status.className = "flow-small";
  status.setAttribute("role", "status");
  const buttons = figures.map((figure, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", `Ver foto ${index + 1}`);
    const image = figure.querySelector("img").cloneNode();
    image.alt = "";
    image.loading = "lazy";
    button.append(image);
    button.addEventListener("click", () => select(index));
    button.addEventListener("keydown", (event) => {
      const keys = { ArrowRight: 1, ArrowLeft: -1 };
      if (!(event.key in keys)) return;
      event.preventDefault();
      const next = (index + keys[event.key] + figures.length) % figures.length;
      buttons[next].focus();
      select(next);
    });
    thumbnails.append(button);
    return button;
  });
  function select(selected) {
    figures.forEach((figure, index) => {
      figure.hidden = index !== selected;
      buttons[index].setAttribute("aria-pressed", String(index === selected));
    });
    status.textContent = `Foto ${selected + 1} de ${figures.length}`;
  }
  gallery.classList.add("detail-gallery");
  gallery.append(thumbnails, status);
  select(0);
})();
