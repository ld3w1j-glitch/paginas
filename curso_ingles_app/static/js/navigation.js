(() => {
  const toggle = document.querySelector("[data-mobile-menu-toggle]");
  const sheet = document.querySelector("[data-mobile-menu]");
  const backdrop = document.querySelector(".mobile-nav-backdrop");
  if (!toggle || !sheet || !backdrop) return;

  const setOpen = (open) => {
    sheet.hidden = !open;
    backdrop.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("mobile-menu-open", open);
  };

  toggle.addEventListener("click", () => setOpen(sheet.hidden));
  document.querySelectorAll("[data-mobile-menu-close]").forEach((button) => {
    button.addEventListener("click", () => setOpen(false));
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });
})();
