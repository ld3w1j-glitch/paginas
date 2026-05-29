function revealOnScroll() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add("is-visible");
    });
  }, { threshold: 0.12 });

  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

function loadState(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function saveState(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function countCompleted(map) {
  return Object.keys(map).filter((key) => map[key]).length;
}

function refreshDashboard() {
  const modules = loadState("english-track-completed", {});
  const lessons = loadState("english-track-lessons", {});
  const words = loadState("english-track-words", {});

  const moduleTotal = countCompleted(modules);
  const lessonTotal = countCompleted(lessons);
  const wordsTotal = countCompleted(words);
  const xp = moduleTotal * 120 + lessonTotal * 25 + wordsTotal * 3;

  const summary = document.querySelector("[data-progress-summary]");
  if (summary) {
    summary.textContent = `${moduleTotal} módulo(s) · ${lessonTotal} lição(ões) · ${wordsTotal} palavra(s) marcadas`;
  }

  const dashboard = document.querySelector("[data-dashboard-summary]");
  if (dashboard) {
    dashboard.innerHTML = `<strong>${xp} XP</strong><br><span>${moduleTotal} módulos concluídos · ${lessonTotal} lições concluídas · ${wordsTotal} palavras dominadas</span>`;
  }
}

function initModuleProgress() {
  const completed = loadState("english-track-completed", {});
  const buttons = document.querySelectorAll("[data-module-toggle]");

  const refreshButtons = () => {
    buttons.forEach((button) => {
      const slug = button.dataset.moduleToggle;
      const done = Boolean(completed[slug]);
      button.textContent = done ? "Módulo concluído ✓" : "Marcar módulo concluído";
      button.classList.toggle("is-done", done);
      const card = document.querySelector(`[data-module-card="${slug}"]`);
      if (card) card.classList.toggle("is-done", done);
    });
    refreshDashboard();
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const slug = button.dataset.moduleToggle;
      completed[slug] = !completed[slug];
      saveState("english-track-completed", completed);
      refreshButtons();
    });
  });

  refreshButtons();
}

function initLessonProgress() {
  const completed = loadState("english-track-lessons", {});
  const buttons = document.querySelectorAll("[data-lesson-toggle]");

  const refresh = () => {
    buttons.forEach((button) => {
      const key = button.dataset.lessonToggle;
      const done = Boolean(completed[key]);
      button.textContent = done ? "lição concluída ✓" : "concluir lição";
      button.classList.toggle("is-done", done);
      const card = document.querySelector(`[data-lesson-card="${key}"]`);
      if (card) card.classList.toggle("is-done", done);
    });
    refreshDashboard();
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.lessonToggle;
      completed[key] = !completed[key];
      saveState("english-track-lessons", completed);
      refresh();
    });
  });

  refresh();
}

function initWordBank() {
  const knownWords = loadState("english-track-words", {});
  const chips = document.querySelectorAll("[data-word-chip]");

  const refresh = () => {
    chips.forEach((chip) => {
      const key = chip.dataset.wordChip;
      chip.classList.toggle("is-known", Boolean(knownWords[key]));
    });
    refreshDashboard();
  };

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const key = chip.dataset.wordChip;
      knownWords[key] = !knownWords[key];
      saveState("english-track-words", knownWords);
      refresh();
    });
  });

  refresh();
}

function initModuleNotes() {
  document.querySelectorAll("[data-module-notes]").forEach((textarea) => {
    const slug = textarea.dataset.moduleNotes;
    const key = `english-track-note-${slug}`;
    textarea.value = localStorage.getItem(key) || "";
    textarea.addEventListener("input", () => {
      localStorage.setItem(key, textarea.value);
    });
  });
}

function initFlipCards() {
  document.querySelectorAll("[data-flip-card]").forEach((card) => {
    card.addEventListener("click", () => card.classList.toggle("is-flipped"));
  });
}

function renderQuiz(root, items, storageKey) {
  if (!items.length) {
    root.innerHTML = '<div class="summary-box">Nenhum quiz disponível neste filtro.</div>';
    return;
  }

  let index = 0;
  let score = 0;

  const render = () => {
    if (index >= items.length) {
      const best = Math.max(loadState(storageKey, 0), score);
      saveState(storageKey, best);
      root.innerHTML = `
        <div class="summary-box">
          <strong>Você concluiu este bloco.</strong><br>
          <span>Pontuação: ${score} / ${items.length}</span><br>
          <span>Melhor pontuação salva: ${best}</span>
        </div>
      `;
      return;
    }

    const item = items[index];
    root.innerHTML = `
      <div class="quiz-screen">
        <p class="eyebrow">Questão ${index + 1} de ${items.length}</p>
        <h3>${item.question}</h3>
        <div class="quiz-options">
          ${item.options.map((option, optionIndex) => `
            <button class="btn btn-ghost quiz-option" data-index="${optionIndex}">${option}</button>
          `).join("")}
        </div>
        <div class="summary-box" id="quiz-feedback">Escolha uma opção.</div>
      </div>
    `;

    const feedback = root.querySelector("#quiz-feedback");
    root.querySelectorAll(".quiz-option").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = Number(button.dataset.index);
        const correct = selected === item.answer;
        if (correct) score += 1;
        feedback.innerHTML = `${correct ? "Acertou." : "Errou."}<br>${item.explanation}`;
        root.querySelectorAll(".quiz-option").forEach((node) => {
          node.disabled = true;
          if (Number(node.dataset.index) === item.answer) node.classList.add("is-done");
        });
        setTimeout(() => {
          index += 1;
          render();
        }, 1200);
      });
    });
  };

  render();
}

function initQuiz() {
  const root = document.getElementById("quiz-app");
  if (!root) return;
  const items = JSON.parse(root.dataset.quiz || "[]");
  renderQuiz(root, items, "english-track-best-quiz");
}

function initFinalExam() {
  const root = document.getElementById("final-exam-app");
  if (!root) return;
  const items = JSON.parse(root.dataset.exam || "[]");
  if (!items.length) return;

  let index = 0;
  let score = 0;
  const skillHits = {};
  const skillTotals = {};
  items.forEach((item) => {
    skillTotals[item.skill] = (skillTotals[item.skill] || 0) + 1;
    skillHits[item.skill] = skillHits[item.skill] || 0;
  });

  const render = () => {
    if (index >= items.length) {
      const summary = Object.keys(skillTotals).map((skill) => {
        const hits = skillHits[skill];
        const total = skillTotals[skill];
        return `<li>${skill}: ${hits}/${total}</li>`;
      }).join("");
      const best = Math.max(loadState("english-track-final-exam-best", 0), score);
      saveState("english-track-final-exam-best", best);
      root.innerHTML = `
        <div class="summary-box">
          <strong>Prova final concluída.</strong><br>
          <span>Pontuação: ${score}/${items.length}</span><br>
          <span>Melhor pontuação salva: ${best}</span>
          <ul class="practice-list">${summary}</ul>
        </div>
      `;
      return;
    }

    const item = items[index];
    root.innerHTML = `
      <div class="quiz-screen">
        <p class="eyebrow">Questão ${index + 1} de ${items.length} · ${item.skill}</p>
        <h3>${item.question}</h3>
        <div class="quiz-options">
          ${item.options.map((option, optionIndex) => `
            <button class="btn btn-ghost quiz-option" data-index="${optionIndex}">${option}</button>
          `).join("")}
        </div>
        <div class="summary-box" id="exam-feedback">Escolha uma opção.</div>
      </div>
    `;

    const feedback = root.querySelector("#exam-feedback");
    root.querySelectorAll(".quiz-option").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = Number(button.dataset.index);
        const correct = selected === item.answer;
        if (correct) {
          score += 1;
          skillHits[item.skill] += 1;
        }
        feedback.innerHTML = `${correct ? "Acertou." : "Errou."}<br>${item.explanation}`;
        root.querySelectorAll(".quiz-option").forEach((node) => {
          node.disabled = true;
          if (Number(node.dataset.index) === item.answer) node.classList.add("is-done");
        });
        setTimeout(() => {
          index += 1;
          render();
        }, 1200);
      });
    });
  };

  render();
}

document.addEventListener("DOMContentLoaded", () => {
  revealOnScroll();
  initModuleProgress();
  initLessonProgress();
  initModuleNotes();
  initFlipCards();
  initQuiz();
  initWordBank();
  initFinalExam();
  refreshDashboard();
});
