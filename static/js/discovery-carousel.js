(() => {
  const carousel = document.querySelector("[data-discovery-carousel]");
  if (!carousel) return;

  const track = carousel.querySelector(".discovery-cars");
  const cards = [...track.querySelectorAll(".discovery-car")];
  const controls = carousel.querySelector(".discovery-carousel-controls");
  const toggle = carousel.querySelector("[data-carousel-toggle]");
  const motionNote = carousel.querySelector("[data-carousel-motion-note]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let paused = reducedMotion.matches;
  let hovering = false;
  let timer;

  const hasOverflow = () => cards.length > 1 && track.scrollWidth > track.clientWidth + 2;
  const updateToggle = () => {
    toggle.textContent = paused ? "Retomar carrossel" : "Pausar carrossel";
    toggle.setAttribute("aria-pressed", String(paused));
    toggle.hidden = reducedMotion.matches;
    motionNote.hidden = !reducedMotion.matches;
  };
  const schedule = () => {
    window.clearTimeout(timer);
    if (paused || hovering || document.hidden || reducedMotion.matches ||
        track.matches(":focus-within") || !hasOverflow()) return;
    timer = window.setTimeout(() => {
      move(1);
      schedule();
    }, 6000);
  };
  const pause = () => {
    paused = true;
    updateToggle();
    schedule();
  };
  const move = (direction) => {
    const max = track.scrollWidth - track.clientWidth;
    const step = cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : 0;
    let left = track.scrollLeft + direction * step;
    if (direction > 0 && track.scrollLeft >= max - 2) left = 0;
    if (direction < 0 && track.scrollLeft <= 2) left = max;
    track.scrollTo({
      left: Math.max(0, Math.min(max, left)),
      behavior: reducedMotion.matches ? "instant" : "smooth",
    });
  };
  const manualMove = (direction) => {
    pause();
    move(direction);
  };
  carousel.querySelector("[data-carousel-prev]").addEventListener("click", () => manualMove(-1));
  carousel.querySelector("[data-carousel-next]").addEventListener("click", () => manualMove(1));
  toggle.addEventListener("click", () => {
    paused = !paused;
    updateToggle();
    schedule();
  });
  carousel.addEventListener("pointerenter", (event) => {
    if (event.pointerType !== "mouse") return;
    hovering = true;
    schedule();
  });
  carousel.addEventListener("pointerleave", () => {
    hovering = false;
    schedule();
  });
  track.addEventListener("pointerdown", pause);
  track.addEventListener("wheel", pause, { passive: true });
  track.addEventListener("focusin", pause);
  track.addEventListener("keydown", (event) => {
    if (event.target !== track || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    manualMove(event.key === "ArrowRight" ? 1 : -1);
  });
  document.addEventListener("visibilitychange", schedule);
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) paused = true;
    updateToggle();
    schedule();
  });
  const resize = () => {
    controls.hidden = !hasOverflow();
    schedule();
  };
  window.addEventListener("resize", resize);
  if ("ResizeObserver" in window) new ResizeObserver(resize).observe(track);
  updateToggle();
  resize();
})();
