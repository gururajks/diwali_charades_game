const lit = {
  title: document.getElementById("lit-title"),
  counter: document.getElementById("lit-counter"),
  list: document.getElementById("lit-list"),
  revealAll: document.getElementById("lit-reveal-all"),
  hideAll: document.getElementById("lit-hide-all"),
};

let litCards = [];

function setLitRevealed(card, revealed) {
  card.answer.hidden = !revealed;
  card.button.textContent = revealed ? "Hide" : "Reveal";
  card.button.setAttribute("aria-expanded", String(revealed));
  card.item.classList.toggle("revealed", revealed);
}

function updateLitCounter() {
  const revealed = litCards.filter((card) => !card.answer.hidden).length;
  lit.counter.textContent = `${revealed} of ${litCards.length} answers revealed`;
}

function setAllLit(revealed) {
  litCards.forEach((card) => setLitRevealed(card, revealed));
  updateLitCounter();
}

function buildLitCard(question, number) {
  const item = document.createElement("li");
  item.className = "lit-card";

  const meta = document.createElement("p");
  meta.className = "lit-meta";
  meta.textContent = `${number}. (${question.category})`;

  const clue = document.createElement("p");
  clue.className = "lit-clue";
  const strong = document.createElement("strong");
  strong.textContent = question.clue;
  clue.append(strong);

  const answer = document.createElement("p");
  answer.className = "lit-answer";
  answer.id = `lit-answer-${number}`;
  const check = document.createElement("span");
  check.className = "lit-check";
  check.setAttribute("aria-hidden", "true");
  check.textContent = "✓";
  answer.append(check, document.createTextNode(question.answer));

  const body = document.createElement("div");
  body.className = "lit-body";
  body.append(meta, clue, answer);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "lit-toggle";
  button.setAttribute("aria-controls", answer.id);

  item.append(body, button);

  const card = { item, answer, button };
  button.addEventListener("click", () => {
    setLitRevealed(card, card.answer.hidden);
    updateLitCounter();
  });
  setLitRevealed(card, false);
  return card;
}

async function initTranslation() {
  try {
    const res = await fetch("/api/lost-in-translation");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const game = await res.json();
    lit.title.textContent = game.title;
    litCards = game.questions.map((question, index) => buildLitCard(question, index + 1));
    lit.list.replaceChildren(...litCards.map((card) => card.item));
    updateLitCounter();
  } catch (err) {
    lit.counter.textContent = "Couldn't load the questions. Refresh to try again.";
    console.error(err);
  }
}

lit.revealAll.addEventListener("click", () => setAllLit(true));
lit.hideAll.addEventListener("click", () => setAllLit(false));

initTranslation();
