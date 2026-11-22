const GAMES = ["charades", "translation"];

const navEls = {
  menuBtn: document.getElementById("menu-btn"),
  scrim: document.getElementById("scrim"),
};

function setMenuOpen(open) {
  document.body.classList.toggle("nav-open", open);
  navEls.scrim.hidden = !open;
  navEls.menuBtn.setAttribute("aria-expanded", String(open));
}

function showGame(requested) {
  const game = GAMES.includes(requested) ? requested : GAMES[0];
  for (const id of GAMES) {
    document.getElementById(`game-${id}`).hidden = id !== game;
    const link = document.querySelector(`.nav-link[data-game="${id}"]`);
    if (id === game) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  setMenuOpen(false);
  document.dispatchEvent(new CustomEvent("gamechange", { detail: game }));
}

navEls.menuBtn.addEventListener("click", () => setMenuOpen(!document.body.classList.contains("nav-open")));
navEls.scrim.addEventListener("click", () => setMenuOpen(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});
for (const link of document.querySelectorAll(".nav-link")) {
  link.addEventListener("click", () => setMenuOpen(false));
}
window.addEventListener("hashchange", () => showGame(location.hash.slice(1)));
showGame(location.hash.slice(1));
