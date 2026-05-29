const STORAGE_KEYS = {
  studied: "portugues_site_studied_lessons_v3",
  notes: "portugues_site_notes_v3",
  checks: "portugues_site_checks_v3",
  quiz: "portugues_site_quiz_stats_v3",
  finalExam: "portugues_site_final_exam_v3"
};

const LEGACY_KEYS = {
  studied: "portugues_site_studied_lessons_v2",
  notes: "portugues_site_notes_v2",
  checks: "portugues_site_checks_v2",
  quiz: "portugues_site_quiz_stats_v2"
};

const progressBar = document.getElementById("topProgress");
const revealItems = document.querySelectorAll(".reveal");
const menuToggle = document.getElementById("menuToggle");
const mainNav = document.getElementById("mainNav");
const clientSearch = document.getElementById("clientSearch");

const SITE_META = window.__SITE_META__ || { total_lessons: 0, total_quizzes: 0, final_exam_size: 0 };
const LESSONS = window.__LESSONS__ || [];
const LESSONS_BY_SLUG = Object.fromEntries(LESSONS.map((lesson) => [lesson.slug, lesson]));

function readStore(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (error) {
    return fallback;
  }
}

function writeStore(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function readStoreWithLegacy(primaryKey, legacyKey, fallback) {
  const primary = readStore(primaryKey, null);
  if (primary !== null) return primary;
  const legacy = legacyKey ? readStore(legacyKey, null) : null;
  return legacy !== null ? legacy : fallback;
}

function getStudiedLessons() {
  const value = readStoreWithLegacy(STORAGE_KEYS.studied, LEGACY_KEYS.studied, []);
  return Array.isArray(value) ? [...new Set(value)] : [];
}

function getNotesMap() {
  const value = readStoreWithLegacy(STORAGE_KEYS.notes, LEGACY_KEYS.notes, {});
  return value && typeof value === "object" ? value : {};
}

function getChecksMap() {
  const value = readStoreWithLegacy(STORAGE_KEYS.checks, LEGACY_KEYS.checks, {});
  return value && typeof value === "object" ? value : {};
}

function getQuizStats() {
  const legacy = readStoreWithLegacy(STORAGE_KEYS.quiz, LEGACY_KEYS.quiz, null);
  const base = {
    hits: 0,
    attempts: 0,
    bestScore: 0,
    answeredIds: [],
    lessonHits: {},
    lessonAttempts: {}
  };
  if (!legacy || typeof legacy !== "object") return base;
  return {
    ...base,
    ...legacy,
    answeredIds: Array.isArray(legacy.answeredIds) ? legacy.answeredIds : [],
    lessonHits: legacy.lessonHits && typeof legacy.lessonHits === "object" ? legacy.lessonHits : {},
    lessonAttempts: legacy.lessonAttempts && typeof legacy.lessonAttempts === "object" ? legacy.lessonAttempts : {}
  };
}

function getFinalExamStats() {
  const value = readStore(STORAGE_KEYS.finalExam, null);
  const base = {
    attempts: 0,
    bestScore: 0,
    lastScore: 0,
    completed: false,
    weakLessons: {},
    lastDate: ""
  };
  if (!value || typeof value !== "object") return base;
  return {
    ...base,
    ...value,
    weakLessons: value.weakLessons && typeof value === "object" ? value.weakLessons || {} : {}
  };
}

function saveQuizStats(nextStats) {
  writeStore(STORAGE_KEYS.quiz, nextStats);
}

function saveFinalExamStats(nextStats) {
  writeStore(STORAGE_KEYS.finalExam, nextStats);
}

function updateProgressBar() {
  if (!progressBar) return;
  const scrollTop = window.scrollY;
  const documentHeight = document.documentElement.scrollHeight - window.innerHeight;
  const progress = documentHeight <= 0 ? 0 : (scrollTop / documentHeight) * 100;
  progressBar.style.width = `${Math.min(progress, 100)}%`;
}

function setupReveal() {
  if (!("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  revealItems.forEach((item) => observer.observe(item));
}

function setupMenu() {
  if (!menuToggle || !mainNav) return;
  menuToggle.addEventListener("click", () => {
    mainNav.classList.toggle("open");
  });
}

function setupInlineFilter() {
  if (!clientSearch) return;
  clientSearch.addEventListener("input", () => {
    const query = clientSearch.value.trim().toLowerCase();
    const cards = document.querySelectorAll(".lesson-card");
    cards.forEach((card) => {
      const text = card.innerText.toLowerCase();
      card.style.display = text.includes(query) ? "" : "none";
    });
  });
}

function clampPercent(value) {
  const safe = Number.isFinite(value) ? value : 0;
  return Math.max(0, Math.min(100, Math.round(safe)));
}

function computeProgress() {
  const studied = getStudiedLessons();
  const notesMap = getNotesMap();
  const quizStats = getQuizStats();
  const finalStats = getFinalExamStats();

  const readingPercent = SITE_META.total_lessons
    ? (studied.length / SITE_META.total_lessons) * 100
    : 0;

  const uniqueAnswers = [...new Set(quizStats.answeredIds || [])];
  const practicePercent = SITE_META.total_quizzes
    ? (Math.min(uniqueAnswers.length, SITE_META.total_quizzes) / SITE_META.total_quizzes) * 100
    : 0;

  const examPercent = finalStats.completed ? finalStats.bestScore || 0 : 0;
  const overallPercent = (readingPercent * 0.45) + (practicePercent * 0.35) + (examPercent * 0.20);

  return {
    studied,
    notesMap,
    quizStats,
    finalStats,
    readingPercent: clampPercent(readingPercent),
    practicePercent: clampPercent(practicePercent),
    examPercent: clampPercent(examPercent),
    overallPercent: clampPercent(overallPercent),
    uniqueAnswersCount: uniqueAnswers.length
  };
}

function setWidthByPercent(element, percent) {
  if (!element) return;
  element.style.width = `${clampPercent(percent)}%`;
}

function setProgressCircle(element, percent) {
  if (!element) return;
  element.style.setProperty("--progress", clampPercent(percent));
}

function renderDashboardMetrics() {
  const progress = computeProgress();
  const accuracy = progress.quizStats.attempts
    ? Math.round((progress.quizStats.hits / progress.quizStats.attempts) * 100)
    : 0;

  const studiedCount = document.getElementById("studiedCount");
  const notesCount = document.getElementById("notesCount");
  const quizAccuracy = document.getElementById("quizAccuracy");
  const practiceBestScore = document.getElementById("practiceBestScore");
  const quizHits = document.getElementById("quizHits");
  const quizAttempts = document.getElementById("quizAttempts");
  const studiedOnPractice = document.getElementById("studiedOnPractice");
  const practiceProgressCounter = document.getElementById("practiceProgressCounter");
  const overallProgressPercent = document.getElementById("overallProgressPercent");
  const overallProgressCircle = document.getElementById("overallProgressCircle");

  const readingProgressPercent = document.getElementById("readingProgressPercent");
  const readingProgressLabel = document.getElementById("readingProgressLabel");
  const practiceProgressPercent = document.getElementById("practiceProgressPercent");
  const practiceProgressLabel = document.getElementById("practiceProgressLabel");
  const examProgressPercent = document.getElementById("examProgressPercent");
  const examProgressLabel = document.getElementById("examProgressLabel");

  const finalBestScore = document.getElementById("finalBestScore");
  const finalLastScore = document.getElementById("finalLastScore");

  if (studiedCount) studiedCount.textContent = String(progress.studied.length);
  if (notesCount) notesCount.textContent = String(Object.values(progress.notesMap).filter(Boolean).length);
  if (quizAccuracy) quizAccuracy.textContent = `${accuracy}%`;
  if (practiceBestScore) practiceBestScore.textContent = `${progress.quizStats.bestScore || 0}%`;
  if (quizHits) quizHits.textContent = String(progress.quizStats.hits || 0);
  if (quizAttempts) quizAttempts.textContent = String(progress.quizStats.attempts || 0);
  if (studiedOnPractice) studiedOnPractice.textContent = String(progress.studied.length);
  if (practiceProgressCounter) practiceProgressCounter.textContent = `${progress.practicePercent}%`;

  if (overallProgressPercent) overallProgressPercent.textContent = `${progress.overallPercent}%`;
  setProgressCircle(overallProgressCircle, progress.overallPercent);

  if (readingProgressPercent) readingProgressPercent.textContent = `${progress.readingPercent}%`;
  if (readingProgressLabel) readingProgressLabel.textContent = `${progress.studied.length} de ${SITE_META.total_lessons} lições`;
  if (practiceProgressPercent) practiceProgressPercent.textContent = `${progress.practicePercent}%`;
  if (practiceProgressLabel) practiceProgressLabel.textContent = `${progress.uniqueAnswersCount} de ${SITE_META.total_quizzes} questões`;
  if (examProgressPercent) examProgressPercent.textContent = `${progress.examPercent}%`;
  if (examProgressLabel) {
    examProgressLabel.textContent = progress.finalStats.completed
      ? `Melhor nota: ${progress.finalStats.bestScore || 0}%`
      : "Ainda não realizada";
  }

  setWidthByPercent(document.getElementById("readingProgressBar"), progress.readingPercent);
  setWidthByPercent(document.getElementById("practiceProgressBar"), progress.practicePercent);
  setWidthByPercent(document.getElementById("examProgressBar"), progress.examPercent);

  if (finalBestScore) finalBestScore.textContent = `${progress.finalStats.bestScore || 0}%`;
  if (finalLastScore) finalLastScore.textContent = `${progress.finalStats.lastScore || 0}%`;

  document.querySelectorAll("[data-study-chip]").forEach((chip) => {
    const slug = chip.dataset.studyChip;
    const done = progress.studied.includes(slug);
    chip.textContent = done ? "Estudada" : "Não estudada";
    chip.classList.toggle("is-done", done);
  });
}

function updateStudyState(slug, shouldAdd) {
  const current = getStudiedLessons();
  const next = shouldAdd
    ? [...new Set([...current, slug])]
    : current.filter((item) => item !== slug);
  writeStore(STORAGE_KEYS.studied, next);
  renderDashboardMetrics();
  return next;
}

function recordAnswer({ questionId, lessonSlug, hit }) {
  const stats = getQuizStats();
  stats.attempts += 1;
  if (hit) stats.hits += 1;

  const answeredIds = new Set(stats.answeredIds || []);
  answeredIds.add(questionId);
  stats.answeredIds = [...answeredIds];

  stats.lessonAttempts[lessonSlug] = (stats.lessonAttempts[lessonSlug] || 0) + 1;
  if (hit) {
    stats.lessonHits[lessonSlug] = (stats.lessonHits[lessonSlug] || 0) + 1;
  }

  const currentAccuracy = stats.attempts ? Math.round((stats.hits / stats.attempts) * 100) : 0;
  stats.bestScore = Math.max(stats.bestScore || 0, currentAccuracy);
  saveQuizStats(stats);
  renderDashboardMetrics();
}

function setupLessonControls() {
  const pageMeta = window.__LESSON_PAGE__;
  if (!pageMeta) return;

  const toggleButton = document.getElementById("toggleStudyButton");
  const statusPill = document.getElementById("lessonStatusPill");
  const notesField = document.getElementById("lessonNotes");
  const notesStatus = document.getElementById("notesStatus");
  const checksMap = getChecksMap();

  function syncLessonState() {
    const isDone = getStudiedLessons().includes(pageMeta.slug);
    if (toggleButton) {
      toggleButton.textContent = isDone ? "Remover marcação" : "Marcar como estudada";
      toggleButton.classList.toggle("btn-ghost", isDone);
      toggleButton.classList.toggle("btn-primary", !isDone);
    }
    if (statusPill) {
      statusPill.textContent = isDone ? "Lição marcada como estudada" : "Ainda não marcada";
      statusPill.classList.toggle("is-done", isDone);
    }
    renderDashboardMetrics();
  }

  if (toggleButton) {
    toggleButton.addEventListener("click", () => {
      const current = getStudiedLessons();
      const shouldAdd = !current.includes(pageMeta.slug);
      updateStudyState(pageMeta.slug, shouldAdd);
      syncLessonState();
    });
  }

  if (notesField) {
    const notesMap = getNotesMap();
    notesField.value = notesMap[pageMeta.slug] || "";
    notesField.addEventListener("input", () => {
      const nextNotes = getNotesMap();
      nextNotes[pageMeta.slug] = notesField.value;
      writeStore(STORAGE_KEYS.notes, nextNotes);
      if (notesStatus) notesStatus.textContent = "Anotação salva automaticamente.";
      renderDashboardMetrics();
    });
  }

  document.querySelectorAll("[data-lesson-check]").forEach((checkbox) => {
    const key = checkbox.dataset.lessonCheck;
    checkbox.checked = Boolean(checksMap[key]);
    checkbox.addEventListener("change", () => {
      const nextChecks = getChecksMap();
      nextChecks[key] = checkbox.checked;
      writeStore(STORAGE_KEYS.checks, nextChecks);
    });
  });

  syncLessonState();
}

function setupLessonExercises() {
  const pageMeta = window.__LESSON_PAGE__;
  const lessonRoot = document.getElementById("lessonExerciseApp");
  if (!pageMeta || !lessonRoot) return;

  const items = pageMeta.quizItems || [];
  if (!items.length) {
    lessonRoot.innerHTML = `<div class="quiz-empty">Esta lição ainda não tem exercícios cadastrados.</div>`;
    return;
  }

  let index = 0;
  let locked = false;

  function renderExercise() {
    const item = items[index];
    lessonRoot.innerHTML = `
      <div class="lesson-exercise-card">
        <div class="quiz-head">
          <div>
            <span class="eyebrow">Exercício ${index + 1} de ${items.length}</span>
            <div class="lesson-badge">${pageMeta.label}</div>
          </div>
          <button class="btn btn-ghost btn-small" id="nextLessonExercise">Próximo</button>
        </div>

        <div class="quiz-question">${item.question}</div>

        <div class="lesson-exercise-options">
          ${item.options.map((option, optionIndex) => `
            <button class="quiz-option" data-lesson-option="${optionIndex}">
              ${option}
            </button>
          `).join("")}
        </div>

        <div class="exercise-feedback" id="lessonExerciseFeedback">Escolha uma alternativa para conferir.</div>
      </div>
    `;

    locked = false;
    const feedback = document.getElementById("lessonExerciseFeedback");
    const buttons = lessonRoot.querySelectorAll("[data-lesson-option]");
    const nextButton = document.getElementById("nextLessonExercise");

    nextButton?.addEventListener("click", () => {
      index = (index + 1) % items.length;
      renderExercise();
    });

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        if (locked) return;
        locked = true;
        const selected = Number(button.dataset.lessonOption);
        const correct = item.answer_index;
        buttons.forEach((btn) => {
          const buttonIndex = Number(btn.dataset.lessonOption);
          if (buttonIndex === correct) btn.classList.add("correct");
          if (buttonIndex === selected && selected !== correct) btn.classList.add("wrong");
        });

        const hit = selected === correct;
        recordAnswer({ questionId: item.id, lessonSlug: item.lesson_slug, hit });
        feedback.textContent = item.explanation;

        if (hit) {
          updateStudyState(pageMeta.slug, true);
        }
      });
    });
  }

  renderExercise();
}

function shuffleArray(array) {
  const next = [...array];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [next[i], next[j]] = [next[j], next[i]];
  }
  return next;
}

function setupPracticePage() {
  const appData = window.__PRACTICE__;
  if (!appData) return;

  const quizRoot = document.getElementById("quizApp");
  const flashcardRoot = document.getElementById("flashcardApp");
  const prevFlashcardButton = document.getElementById("flashcardPrev");
  const nextFlashcardButton = document.getElementById("flashcardNext");
  const flipFlashcardButton = document.getElementById("flashcardFlip");
  const filterSelect = document.getElementById("practiceLessonFilter");
  const shuffleButton = document.getElementById("practiceShuffle");

  const allQuizzes = appData.quizzes || [];
  const allFlashcards = appData.flashcards || [];
  let activeQuizzes = [...allQuizzes];
  let quizIndex = 0;
  let locked = false;
  let flashIndex = 0;
  let isFlipped = false;

  function populateFilter() {
    if (!filterSelect) return;
    const options = [
      { slug: "all", label: "Todas as lições" },
      ...LESSONS.map((lesson) => ({ slug: lesson.slug, label: lesson.label }))
    ];
    filterSelect.innerHTML = options.map((item) => `
      <option value="${item.slug}">${item.label}</option>
    `).join("");

    filterSelect.addEventListener("change", () => {
      const slug = filterSelect.value;
      activeQuizzes = slug === "all"
        ? [...allQuizzes]
        : allQuizzes.filter((quiz) => quiz.lesson_slug === slug);
      quizIndex = 0;
      renderQuiz();
    });
  }

  function renderQuiz() {
    if (!quizRoot) return;
    if (!activeQuizzes.length) {
      quizRoot.innerHTML = `<div class="quiz-empty">Não há questões nesse filtro ainda.</div>`;
      return;
    }

    const item = activeQuizzes[quizIndex];
    const progressPercent = Math.round(((quizIndex + 1) / activeQuizzes.length) * 100);

    quizRoot.innerHTML = `
      <div class="quiz-head">
        <div>
          <span class="eyebrow">Questão ${quizIndex + 1} de ${activeQuizzes.length}</span>
          <div class="lesson-badge">${item.lesson_label}</div>
        </div>
        <button class="btn btn-ghost btn-small" id="nextQuestionTop">Pular</button>
      </div>

      <div class="quiz-progress-track">
        <div class="quiz-progress-bar" style="width:${progressPercent}%"></div>
      </div>

      <div class="quiz-question">${item.question}</div>

      <div class="quiz-option-list">
        ${item.options.map((option, index) => `
          <button class="quiz-option" data-quiz-option="${index}">
            ${option}
          </button>
        `).join("")}
      </div>

      <div class="quiz-feedback" id="quizFeedback">
        Escolha uma alternativa para ver a explicação.
      </div>
    `;

    const feedback = document.getElementById("quizFeedback");
    const optionButtons = quizRoot.querySelectorAll("[data-quiz-option]");
    const nextQuestionTop = document.getElementById("nextQuestionTop");
    locked = false;

    nextQuestionTop?.addEventListener("click", () => {
      quizIndex = (quizIndex + 1) % activeQuizzes.length;
      renderQuiz();
    });

    optionButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (locked) return;
        locked = true;

        const selected = Number(button.dataset.quizOption);
        const correct = item.answer_index;
        optionButtons.forEach((btn) => {
          const optionIndex = Number(btn.dataset.quizOption);
          if (optionIndex === correct) btn.classList.add("correct");
          if (optionIndex === selected && selected !== correct) btn.classList.add("wrong");
        });

        const hit = selected === correct;
        recordAnswer({ questionId: item.id, lessonSlug: item.lesson_slug, hit });
        feedback.textContent = item.explanation;

        setTimeout(() => {
          quizIndex = (quizIndex + 1) % activeQuizzes.length;
          renderQuiz();
        }, 1800);
      });
    });
  }

  function renderFlashcard() {
    if (!flashcardRoot || !allFlashcards.length) return;
    const item = allFlashcards[flashIndex];
    flashcardRoot.innerHTML = `
      <div class="flashcard-shell ${isFlipped ? "is-flipped" : ""}">
        <article class="flashcard-face front">
          <span>${item.lesson_label}</span>
          <h3>${item.front}</h3>
          <p>Toque em virar para ver o resumo.</p>
        </article>
        <article class="flashcard-face back">
          <span>Revisão</span>
          <h3>${item.front}</h3>
          <p>${item.back}</p>
        </article>
      </div>
    `;
  }

  prevFlashcardButton?.addEventListener("click", () => {
    flashIndex = flashIndex === 0 ? allFlashcards.length - 1 : flashIndex - 1;
    isFlipped = false;
    renderFlashcard();
  });

  nextFlashcardButton?.addEventListener("click", () => {
    flashIndex = (flashIndex + 1) % allFlashcards.length;
    isFlipped = false;
    renderFlashcard();
  });

  flipFlashcardButton?.addEventListener("click", () => {
    isFlipped = !isFlipped;
    renderFlashcard();
  });

  shuffleButton?.addEventListener("click", () => {
    activeQuizzes = shuffleArray(activeQuizzes);
    quizIndex = 0;
    renderQuiz();
  });

  populateFilter();
  renderQuiz();
  renderFlashcard();
}

function setupFinalExamPage() {
  const data = window.__FINAL_EXAM__;
  const root = document.getElementById("finalExamApp");
  if (!data || !root) return;

  const examQuestions = data.questions || [];
  let selectedQuestions = [...examQuestions];

  function renderStart() {
    root.innerHTML = `
      <div class="exam-start">
        <span class="eyebrow">Pronto para começar?</span>
        <h2>Faça a prova no seu tempo</h2>
        <p>As respostas ficam salvas localmente no navegador. Você pode refazer depois para tentar melhorar sua nota.</p>
        <button class="btn btn-primary" id="startFinalExam">Começar prova</button>
      </div>
    `;
    document.getElementById("startFinalExam")?.addEventListener("click", renderExam);
  }

  function renderExam() {
    selectedQuestions = shuffleArray(examQuestions).slice(0, SITE_META.final_exam_size || examQuestions.length);
    root.innerHTML = `
      <form id="finalExamForm" class="final-exam-form">
        <div class="exam-topbar">
          <div>
            <span class="eyebrow">Prova em andamento</span>
            <h2>${selectedQuestions.length} questões</h2>
          </div>
          <button type="button" class="btn btn-ghost btn-small" id="restartExamTop">Refazer seleção</button>
        </div>

        <div class="exam-question-list">
          ${selectedQuestions.map((item, index) => `
            <article class="exam-question-card">
              <div class="exam-question-head">
                <strong>Questão ${index + 1}</strong>
                <span>${item.lesson_label}</span>
              </div>
              <h3>${item.question}</h3>
              <div class="exam-options">
                ${item.options.map((option, optionIndex) => `
                  <label class="exam-option">
                    <input type="radio" name="exam-${item.id}" value="${optionIndex}">
                    <span>${option}</span>
                  </label>
                `).join("")}
              </div>
              <div class="exam-feedback" id="feedback-${item.id}"></div>
            </article>
          `).join("")}
        </div>

        <div class="exam-actions">
          <button type="submit" class="btn btn-primary">Corrigir prova</button>
        </div>
      </form>
    `;

    document.getElementById("restartExamTop")?.addEventListener("click", renderExam);
    document.getElementById("finalExamForm")?.addEventListener("submit", gradeExam);
  }

  function gradeExam(event) {
    event.preventDefault();
    let hits = 0;
    const weakLessons = {};

    selectedQuestions.forEach((item) => {
      const selected = document.querySelector(`input[name="exam-${item.id}"]:checked`);
      const feedback = document.getElementById(`feedback-${item.id}`);
      const selectedIndex = selected ? Number(selected.value) : -1;
      const hit = selectedIndex === item.answer_index;
      if (hit) {
        hits += 1;
      } else {
        weakLessons[item.lesson_slug] = (weakLessons[item.lesson_slug] || 0) + 1;
      }
      if (feedback) {
        feedback.textContent = item.explanation;
        feedback.classList.add("is-visible");
      }
      document.querySelectorAll(`input[name="exam-${item.id}"]`).forEach((input) => {
        input.disabled = true;
        const optionIndex = Number(input.value);
        const wrapper = input.closest(".exam-option");
        if (optionIndex === item.answer_index) wrapper?.classList.add("correct");
        if (optionIndex === selectedIndex && selectedIndex !== item.answer_index) wrapper?.classList.add("wrong");
      });
    });

    const score = selectedQuestions.length ? Math.round((hits / selectedQuestions.length) * 100) : 0;
    const finalStats = getFinalExamStats();
    finalStats.attempts += 1;
    finalStats.completed = true;
    finalStats.lastScore = score;
    finalStats.bestScore = Math.max(finalStats.bestScore || 0, score);
    finalStats.weakLessons = weakLessons;
    finalStats.lastDate = new Date().toISOString();
    saveFinalExamStats(finalStats);

    const weakLessonList = Object.entries(weakLessons)
      .sort((a, b) => b[1] - a[1])
      .map(([slug, count]) => {
        const lesson = LESSONS_BY_SLUG[slug];
        const label = lesson ? lesson.label : slug;
        return `<li><strong>${label}</strong><span>${count} erro(s)</span></li>`;
      })
      .join("");

    root.insertAdjacentHTML("beforeend", `
      <section class="exam-summary reveal is-visible">
        <div class="exam-summary-score">
          <div class="progress-circle small" style="--progress:${score};">
            <div class="progress-circle-inner">
              <strong>${score}%</strong>
              <span>nota</span>
            </div>
          </div>
          <div>
            <span class="eyebrow">Resultado</span>
            <h2>${score >= 80 ? "Ótimo desempenho" : score >= 60 ? "Bom caminho" : "Precisa reforçar a base"}</h2>
            <p>${score >= 80 ? "Você fechou muito bem os tópicos centrais do curso." : "Continue revisando os pontos abaixo e refaça a prova depois."}</p>
          </div>
        </div>

        <div class="exam-summary-grid">
          <article class="summary-panel">
            <strong>${hits}</strong>
            <span>acertos</span>
          </article>
          <article class="summary-panel">
            <strong>${selectedQuestions.length - hits}</strong>
            <span>erros</span>
          </article>
          <article class="summary-panel">
            <strong>${finalStats.bestScore}%</strong>
            <span>melhor nota</span>
          </article>
        </div>

        <div class="weakness-panel">
          <span class="eyebrow">O que revisar</span>
          <h3>Tópicos que mais pediram atenção</h3>
          ${weakLessonList ? `<ul class="weakness-list">${weakLessonList}</ul>` : `<p>Parabéns. Você não deixou fragilidades nessa rodada.</p>`}
        </div>

        <div class="exam-actions">
          <button type="button" class="btn btn-secondary" id="retakeExamBottom">Refazer prova</button>
          <a class="btn btn-primary" href="/praticar">Voltar para a prática</a>
        </div>
      </section>
    `);

    document.getElementById("retakeExamBottom")?.addEventListener("click", renderExam);
    renderDashboardMetrics();
  }

  renderStart();
}

function boot() {
  updateProgressBar();
  setupReveal();
  setupMenu();
  setupInlineFilter();
  renderDashboardMetrics();
  setupLessonControls();
  setupLessonExercises();
  setupPracticePage();
  setupFinalExamPage();
  window.addEventListener("scroll", updateProgressBar, { passive: true });
}

document.addEventListener("DOMContentLoaded", boot);
