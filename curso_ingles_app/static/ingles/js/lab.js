(() => {
  const element = (tag, className = "", text = "") => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  const speakEnglish = (text) => {
    if (!text || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.82;
    utterance.voice = window.speechSynthesis.getVoices()
      .find((voice) => voice.lang.toLowerCase().startsWith("en")) || null;
    window.speechSynthesis.speak(utterance);
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-speak]");
    if (button) speakEnglish(button.dataset.speak || "");
  });

  const preferences = document.querySelector("[data-preferences-root]");
  preferences?.querySelector("[data-preferences-save]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const status = preferences.querySelector("[data-preferences-status]");
    button.disabled = true;
    if (status) status.textContent = "Salvando seu perfil...";
    try {
      const response = await fetch(preferences.dataset.preferencesUrl, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          level: preferences.querySelector("[data-preference-level]")?.value || "A1",
          objective: preferences.querySelector("[data-preference-objective]")?.value || "",
          tutor_engine: preferences.querySelector("[data-preference-engine]")?.value || "integrated",
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível salvar o perfil.");
      if (status) status.textContent = "Perfil salvo. As próximas respostas usarão estas preferências.";
    } catch (error) {
      if (status) status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  const tutorRoot = document.querySelector("[data-tutor-root]");
  if (tutorRoot) {
    const form = tutorRoot.querySelector("[data-tutor-form]");
    const input = tutorRoot.querySelector("#tutor-message");
    const log = tutorRoot.querySelector("[data-tutor-log]");
    const status = tutorRoot.querySelector("[data-tutor-status]");
    const exerciseRoot = tutorRoot.querySelector("[data-tutor-exercise]");
    const exerciseContent = exerciseRoot?.querySelector("[data-exercise-content]");

    const scrollToLatest = () => {
      if (log) log.scrollTop = log.scrollHeight;
    };

    const appendUser = (message) => {
      const card = element("div", "tutor-message user");
      card.append(element("span", "", "VOCÊ"), element("p", "", message));
      log?.append(card);
      scrollToLatest();
    };

    const appendAssistant = (result) => {
      const card = element("div", "tutor-message assistant");
      card.append(
        element("span", "", `PROFESSOR · ${result.engine || "OFFLINE"}`),
        element("p", "", result.reply || "Resposta concluída."),
      );
      if (result.corrected_text) {
        const correction = element("div", "tutor-correction");
        correction.append(
          element("small", "", "FORMA SUGERIDA"),
          element("strong", "", result.corrected_text),
        );
        const speak = element("button", "", "Ouvir");
        speak.type = "button";
        speak.dataset.speak = result.corrected_text;
        correction.append(speak);
        card.append(correction);
      }
      const corrections = Array.isArray(result.corrections) ? result.corrections : [];
      if (corrections.length) {
        const list = element("ul");
        corrections.forEach((item) => {
          if (item?.explanation) list.append(element("li", "", item.explanation));
        });
        if (list.children.length) card.append(list);
      }
      if (result.notice) card.append(element("small", "tutor-notice", result.notice));
      log?.append(card);
      scrollToLatest();
    };

    const renderExercise = (exercise) => {
      if (!exerciseRoot || !exerciseContent || !exercise) return;
      exerciseRoot.dataset.exerciseId = String(exercise.id);
      const options = element("div", "tutor-options");
      (exercise.options || []).forEach((option) => {
        const button = element("button", "", option);
        button.type = "button";
        button.dataset.exerciseOption = option;
        options.append(button);
      });
      const feedback = element("small", "", "Escolha uma alternativa.");
      feedback.dataset.exerciseFeedback = "";
      exerciseContent.replaceChildren(
        element("h2", "", "Fixe sua correção"),
        element("p", "", exercise.prompt),
        options,
        feedback,
      );
    };

    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const message = input?.value.trim();
      if (!message) return;
      const submit = form.querySelector("button[type='submit']");
      appendUser(message);
      input.value = "";
      submit.disabled = true;
      submit.textContent = "Professor pensando...";
      if (status) status.textContent = "Processando no portal local...";
      try {
        const response = await fetch(tutorRoot.dataset.chatUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({message}),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível obter a correção.");
        appendAssistant(result);
        if (result.exercise) renderExercise(result.exercise);
        if (status) status.textContent = `Resposta salva para seu usuário · +${result.xp_earned || 0} XP`;
      } catch (error) {
        appendAssistant({engine: "AVISO", reply: error.message, corrections: []});
        if (status) status.textContent = "A mensagem não pôde ser concluída.";
      } finally {
        submit.disabled = false;
        submit.textContent = "Enviar ao professor";
        input?.focus();
      }
    });

    exerciseRoot?.addEventListener("click", async (event) => {
      const button = event.target.closest("[data-exercise-option]");
      if (!button) return;
      const exerciseId = exerciseRoot.dataset.exerciseId;
      if (!exerciseId) return;
      const buttons = [...exerciseRoot.querySelectorAll("[data-exercise-option]")];
      const feedback = exerciseRoot.querySelector("[data-exercise-feedback]");
      buttons.forEach((item) => { item.disabled = true; });
      try {
        const endpoint = tutorRoot.dataset.exerciseUrl.replace(/\/0$/, `/${exerciseId}`);
        const response = await fetch(endpoint, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({response: button.dataset.exerciseOption}),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível verificar.");
        button.classList.add(result.correct ? "correct" : "wrong");
        if (result.correct) {
          if (feedback) feedback.textContent = `Correto! ${result.explanation || ""} +${result.xp_earned || 0} XP`;
          window.setTimeout(() => {
            if (result.next_exercise) renderExercise(result.next_exercise);
            else if (exerciseContent) {
              exerciseRoot.dataset.exerciseId = "";
              exerciseContent.replaceChildren(
                element("h2", "", "Práticas concluídas"),
                element("p", "", "Escreva uma nova frase para gerar a próxima prática adaptativa."),
              );
            }
          }, 900);
        } else {
          if (feedback) feedback.textContent = `Ainda não. Resposta correta: ${result.answer}. ${result.explanation || ""}`;
          buttons.forEach((item) => {
            if (item.dataset.exerciseOption === result.answer) item.classList.add("correct");
            item.disabled = false;
          });
        }
      } catch (error) {
        if (feedback) feedback.textContent = error.message;
        buttons.forEach((item) => { item.disabled = false; });
      }
    });

    document.querySelectorAll("[data-tutor-prompt]").forEach((button) => {
      button.addEventListener("click", () => {
        if (!input) return;
        input.value = button.dataset.tutorPrompt || "";
        input.focus();
      });
    });

    const scenarioRoot = document.querySelector("[data-scenario-control]");
    const scenarioSelect = scenarioRoot?.querySelector("[data-scenario-select]");
    scenarioRoot?.querySelector("[data-scenario-start]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = "Preparando...";
      try {
        const response = await fetch(scenarioRoot.dataset.scenarioUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({scenario: scenarioSelect?.value || "free"}),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível iniciar o cenário.");
        const title = scenarioRoot.querySelector("[data-scenario-title]");
        const goal = scenarioRoot.querySelector("[data-scenario-goal]");
        if (title) title.textContent = result.title;
        if (goal) goal.textContent = result.goal;
        appendAssistant({engine: "SIMULAÇÃO OFFLINE", reply: result.opening, corrections: []});
        if (input) {
          input.value = "";
          input.placeholder = "Responda ao personagem em inglês...";
          input.focus();
        }
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        button.disabled = false;
        button.textContent = "Iniciar cenário";
      }
    });
    scrollToLatest();
  }

  const runtime = document.querySelector("[data-local-runtime]");
  if (runtime) {
    const startButton = runtime.querySelector("[data-runtime-start]");
    const stopButton = runtime.querySelector("[data-runtime-stop]");
    const status = runtime.querySelector("[data-runtime-status]");
    const detail = runtime.querySelector("[data-runtime-detail]");
    const modelSelect = runtime.querySelector("[data-local-model-select]");

    const renderRuntime = (result) => {
      if (status) {
        status.textContent = result.responding
          ? "IA pronta para conversar"
          : result.running
            ? "Iniciando o modelo..."
            : result.executable_ready && result.models?.length
              ? "Pronto para iniciar"
              : "Pacote opcional ausente";
      }
      if (detail) {
        if (result.responding) detail.textContent = `Servidor local respondendo${result.active_model ? ` · ${result.active_model}` : ""}.`;
        else if (result.running) detail.textContent = "O primeiro carregamento pode levar alguns segundos.";
        else if (result.models?.length) detail.textContent = `${result.models.length} modelo(s) GGUF encontrado(s).`;
      }
      if (startButton) startButton.disabled = Boolean(result.running) || !result.executable_ready || !result.models?.length;
      if (stopButton) stopButton.disabled = !result.managed;
    };

    const refreshRuntime = async () => {
      try {
        const response = await fetch(runtime.dataset.statusUrl);
        const result = await response.json();
        if (response.ok && result.ok) renderRuntime(result);
        return result;
      } catch {
        if (detail) detail.textContent = "Não foi possível verificar o servidor local.";
        return null;
      }
    };

    startButton?.addEventListener("click", async () => {
      startButton.disabled = true;
      if (status) status.textContent = "Iniciando o Qwen...";
      try {
        const response = await fetch(runtime.dataset.startUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({model: modelSelect?.value || ""}),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível iniciar a IA.");
        if (detail) detail.textContent = `Carregando ${result.model || "o modelo local"}...`;
        for (let attempt = 0; attempt < 20; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          const current = await refreshRuntime();
          if (current?.responding || !current?.running) break;
        }
      } catch (error) {
        if (status) status.textContent = "Falha ao iniciar";
        if (detail) detail.textContent = error.message;
        startButton.disabled = false;
      }
    });

    stopButton?.addEventListener("click", async () => {
      stopButton.disabled = true;
      if (status) status.textContent = "Encerrando...";
      try {
        const response = await fetch(runtime.dataset.stopUrl, {method: "POST"});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível desligar.");
      } catch (error) {
        if (detail) detail.textContent = error.message;
      }
      await refreshRuntime();
    });
  }

  const translator = document.querySelector("[data-translator-root]");
  if (translator) {
    const source = translator.querySelector("[data-translation-source]");
    const resultArea = translator.querySelector("[data-translation-result]");
    const status = translator.querySelector("[data-translation-status]");
    const translateButton = translator.querySelector("[data-translate]");
    let worker = null;
    let requestId = 0;

    const ensureWorker = () => {
      if (!window.Worker) throw new Error("Este navegador não suporta o tradutor neural.");
      if (worker) return worker;
      worker = new Worker(translator.dataset.workerUrl, {type: "module"});
      return worker;
    };

    translateButton?.addEventListener("click", async () => {
      const text = source?.value.trim();
      if (!text) {
        source?.focus();
        return;
      }
      translateButton.disabled = true;
      translateButton.textContent = "Preparando modelo...";
      if (status) status.textContent = "Consultando sua memória de correções...";
      try {
        const memoryResponse = await fetch(`${translator.dataset.memoryUrl}?text=${encodeURIComponent(text)}`);
        const memory = await memoryResponse.json();
        if (!memoryResponse.ok || !memory.ok) throw new Error(memory.error || "Falha ao consultar a memória.");
        const activeWorker = ensureWorker();
        requestId += 1;
        const currentId = requestId;
        const translated = await new Promise((resolve, reject) => {
          const onMessage = (event) => {
            const message = event.data || {};
            if (message.requestId && message.requestId !== currentId) return;
            if (message.type === "progress" || message.type === "status") {
              if (status) status.textContent = `${message.label || "Carregando IA offline"}${Number.isFinite(message.percent) ? ` · ${message.percent}%` : ""}`;
              return;
            }
            if (message.type === "result") {
              activeWorker.removeEventListener("message", onMessage);
              resolve(message);
            }
            if (message.type === "error") {
              activeWorker.removeEventListener("message", onMessage);
              reject(new Error(message.error || "A tradução não foi concluída."));
            }
          };
          activeWorker.addEventListener("message", onMessage);
          activeWorker.postMessage({
            type: "translate",
            requestId: currentId,
            text,
            quality: "balanced",
            memorySegments: memory.segments || [],
          });
        });
        if (resultArea) resultArea.value = translated.translation || "";
        if (status) status.textContent = `Tradução concluída no navegador · ${translated.usedMemory || 0} correção(ões) reutilizada(s).`;
      } catch (error) {
        if (status) status.textContent = `Não foi possível traduzir: ${error.message}`;
      } finally {
        translateButton.disabled = false;
        translateButton.textContent = "Traduzir offline";
      }
    });

    translator.querySelector("[data-translation-example]")?.addEventListener("click", () => {
      if (source) source.value = "Learning a language takes time and practice. I want to speak English with more confidence.";
    });

    translator.querySelector("[data-save-translation]")?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const original = source?.value.trim();
      const translation = resultArea?.value.trim();
      if (!original || !translation) {
        if (status) status.textContent = "Traduza um texto e ajuste o resultado antes de ensinar a correção.";
        return;
      }
      button.disabled = true;
      try {
        const response = await fetch(translator.dataset.memoryUrl, {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({source: original, translation}),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível salvar a correção.");
        if (status) status.textContent = result.message;
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  }

  const voiceRoot = document.querySelector("[data-pronunciation-root]");
  if (voiceRoot) {
    const target = voiceRoot.querySelector("[data-voice-target]");
    const recordButton = voiceRoot.querySelector("[data-record-voice]");
    const status = voiceRoot.querySelector("[data-voice-status]");
    const score = voiceRoot.querySelector("[data-voice-score]");
    const resultTarget = voiceRoot.querySelector("[data-result-target]");
    const transcript = voiceRoot.querySelector("[data-result-transcript]");
    const missing = voiceRoot.querySelector("[data-result-missing]");
    const extra = voiceRoot.querySelector("[data-result-extra]");
    const tip = voiceRoot.querySelector("[data-result-tip]");
    let audioContext = null;
    let stream = null;
    let audioSource = null;
    let processor = null;
    let chunks = [];
    let recording = false;
    let stopTimer = null;

    const mergeChunks = (values) => {
      const size = values.reduce((total, item) => total + item.length, 0);
      const merged = new Float32Array(size);
      let offset = 0;
      values.forEach((item) => {
        merged.set(item, offset);
        offset += item.length;
      });
      return merged;
    };

    const resample = (buffer, sourceRate, targetRate = 16000) => {
      if (sourceRate === targetRate) return buffer;
      const ratio = sourceRate / targetRate;
      const length = Math.max(1, Math.round(buffer.length / ratio));
      const output = new Float32Array(length);
      for (let index = 0; index < length; index += 1) {
        const start = Math.round(index * ratio);
        const end = Math.min(buffer.length, Math.round((index + 1) * ratio));
        let sum = 0;
        let count = 0;
        for (let cursor = start; cursor < end; cursor += 1) {
          sum += buffer[cursor];
          count += 1;
        }
        output[index] = count ? sum / count : 0;
      }
      return output;
    };

    const writeAscii = (view, offset, value) => {
      for (let index = 0; index < value.length; index += 1) view.setUint8(offset + index, value.charCodeAt(index));
    };

    const encodeWav = (samples, sampleRate = 16000) => {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);
      writeAscii(view, 0, "RIFF");
      view.setUint32(4, 36 + samples.length * 2, true);
      writeAscii(view, 8, "WAVE");
      writeAscii(view, 12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeAscii(view, 36, "data");
      view.setUint32(40, samples.length * 2, true);
      let offset = 44;
      samples.forEach((sample) => {
        const limited = Math.max(-1, Math.min(1, sample));
        view.setInt16(offset, limited < 0 ? limited * 0x8000 : limited * 0x7fff, true);
        offset += 2;
      });
      return new Blob([view], {type: "audio/wav"});
    };

    const renderVoiceResult = (result) => {
      if (score) score.textContent = `${result.score}%`;
      if (resultTarget) resultTarget.textContent = result.target;
      if (transcript) transcript.textContent = result.transcript || "Nenhuma palavra reconhecida.";
      if (missing) missing.textContent = result.missing?.length ? result.missing.join(", ") : "Nenhuma";
      if (extra) extra.textContent = result.extra?.length ? result.extra.join(", ") : "Nenhuma";
      if (tip) {
        tip.textContent = result.score >= 85
          ? `Ótima correspondência · +${result.xp_earned || 0} XP.`
          : result.score >= 60
            ? "Boa base. Ouça novamente e repita com mais calma."
            : "Pratique em trechos menores e observe as palavras não reconhecidas.";
      }
    };

    const uploadVoice = async (wav) => {
      const phrase = target?.value.trim();
      if (!phrase) throw new Error("Digite uma frase antes de gravar.");
      const body = new FormData();
      body.append("target", phrase);
      body.append("audio", wav, "pronunciation.wav");
      const response = await fetch(voiceRoot.dataset.analyzeUrl, {method: "POST", body});
      const result = await response.json();
      if (!response.ok || !result.ok) throw new Error(result.error || "Não foi possível analisar a gravação.");
      renderVoiceResult(result);
    };

    const finishRecording = async () => {
      if (!recording) return;
      recording = false;
      window.clearTimeout(stopTimer);
      processor?.disconnect();
      audioSource?.disconnect();
      stream?.getTracks().forEach((track) => track.stop());
      const sourceRate = audioContext?.sampleRate || 48000;
      await audioContext?.close();
      const wav = encodeWav(resample(mergeChunks(chunks), sourceRate));
      recordButton.textContent = "Analisando com Whisper...";
      recordButton.disabled = true;
      if (status) status.textContent = "Processando o áudio localmente...";
      try {
        await uploadVoice(wav);
        if (status) status.textContent = "Análise concluída e salva no seu histórico.";
      } catch (error) {
        if (status) status.textContent = error.message;
      } finally {
        recordButton.textContent = "Iniciar gravação";
        recordButton.disabled = false;
        chunks = [];
        audioContext = null;
        stream = null;
        audioSource = null;
        processor = null;
      }
    };

    const startRecording = async () => {
      if (!target?.value.trim()) return target?.focus();
      if (!navigator.mediaDevices?.getUserMedia) {
        if (status) status.textContent = "Este navegador não oferece acesso ao microfone.";
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}});
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioSource = audioContext.createMediaStreamSource(stream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        chunks = [];
        processor.onaudioprocess = (event) => {
          if (recording) chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
        };
        audioSource.connect(processor);
        processor.connect(audioContext.destination);
        recording = true;
        recordButton.textContent = "Parar e analisar";
        if (status) status.textContent = "Gravando... fale a frase e depois pressione Parar.";
        stopTimer = window.setTimeout(finishRecording, 20000);
      } catch (error) {
        if (status) status.textContent = `Não foi possível acessar o microfone: ${error.message}`;
      }
    };

    recordButton?.addEventListener("click", () => {
      if (recording) finishRecording();
      else startRecording();
    });
    voiceRoot.querySelector("[data-hear-target]")?.addEventListener("click", () => speakEnglish(target?.value.trim() || ""));
    document.querySelectorAll("[data-voice-phrase]").forEach((button) => {
      button.addEventListener("click", () => {
        if (target) target.value = button.dataset.voicePhrase || "";
      });
    });
  }
})();
