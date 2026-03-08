const state = {
  currentWeek: null,
  studyList: [],
  studyIndex: 0,
  answers: [],
  startedAt: 0,
};

const weekTitle = document.getElementById("weekTitle");
const weekBadge = document.getElementById("weekBadge");
const weekSummary = document.getElementById("weekSummary");
const newCharList = document.getElementById("newCharList");
const reviewCharList = document.getElementById("reviewCharList");
const wordList = document.getElementById("wordList");
const sentenceList = document.getElementById("sentenceList");
const sceneGrid = document.getElementById("sceneGrid");
const emptyWeekState = document.getElementById("emptyWeekState");

const studyMeta = document.getElementById("studyMeta");
const studyCard = document.getElementById("studyCard");
const studyDone = document.getElementById("studyDone");
const studyChar = document.getElementById("studyChar");
const studyPinyin = document.getElementById("studyPinyin");
const studyGuide = document.getElementById("studyGuide");
const studyMeaning = document.getElementById("studyMeaning");
const studyWords = document.getElementById("studyWords");
const studySentence = document.getElementById("studySentence");
const btnPlayChar = document.getElementById("btnPlayChar");
const btnKnown = document.getElementById("btnKnown");
const btnUnknown = document.getElementById("btnUnknown");

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Request failed.");
  }
  return response.json();
}

function renderChips(target, items) {
  target.innerHTML = items.length
    ? items.map((item) => `<span class="chip">${item}</span>`).join("")
    : '<span class="chip">暂无</span>';
}

function speakText(text) {
  if (!window.speechSynthesis || !text) {
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  utterance.rate = 0.82;
  utterance.pitch = 1.02;
  window.speechSynthesis.speak(utterance);
}

function playButton(text, label = "播放") {
  const escaped = text.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
  return `<button class="btn btn-audio btn-inline-audio" type="button" data-audio-text="${escaped}">${label}</button>`;
}

function attachAudioButtons(scope = document) {
  scope.querySelectorAll("[data-audio-text]").forEach((button) => {
    button.addEventListener("click", () => {
      speakText(button.dataset.audioText);
    });
  });
}

function renderWords(items = []) {
  wordList.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="audio-item">
              <span>${item.text}</span>
              ${playButton(item.audio_text || item.text, "听")}
            </div>
          `
        )
        .join("")
    : '<div class="audio-item"><span>暂无</span></div>';
}

function renderSentences(items = []) {
  sentenceList.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="audio-item">
              <span>${item.text}</span>
              ${playButton(item.audio_text || item.text, "听")}
            </div>
          `
        )
        .join("")
    : '<div class="audio-item"><span>暂无</span></div>';
}

function renderScenes(story = []) {
  if (!story.length) {
    sceneGrid.innerHTML = "";
    emptyWeekState.classList.remove("hidden");
    return;
  }

  emptyWeekState.classList.add("hidden");
  sceneGrid.innerHTML = story
    .map((scene) => {
      const visual = scene.image_path
        ? `<img src="${scene.image_path}" alt="${scene.title}" />`
        : `<div class="scene-placeholder">图片还没有准备好，不过故事已经在这里啦。</div>`;

      return `
        <article class="scene-card">
          <div class="scene-visual">${visual}</div>
          <div class="scene-body">
            <h3>${scene.title}</h3>
            <p class="scene-text">${scene.text}</p>
            <div class="token-list">${(scene.focus_chars || []).map((char) => `<span class="token">${char}</span>`).join("")}</div>
            <div class="scene-audio-row">${playButton(scene.audio_text || scene.text, "听故事")}</div>
          </div>
        </article>
      `;
    })
    .join("");
  attachAudioButtons(sceneGrid);
}

function buildStudyList() {
  state.studyList = state.currentWeek?.char_cards || [];
  state.studyIndex = 0;
  state.answers = [];
  state.startedAt = Date.now();
}

function renderStudyCard() {
  if (!state.studyList.length) {
    studyCard.classList.add("hidden");
    studyDone.classList.remove("hidden");
    studyDone.textContent = "本周还没有学习卡片，请让大人先准备内容。";
    studyMeta.textContent = "暂无学习内容";
    return;
  }

  if (state.studyIndex >= state.studyList.length) {
    studyCard.classList.add("hidden");
    studyDone.classList.remove("hidden");
    studyDone.textContent = `本轮完成：认识 ${state.answers.filter((item) => item.known).length} 个，不认识 ${state.answers.filter((item) => !item.known).length} 个。`;
    studyMeta.textContent = "今天这轮学习已完成";
    return;
  }

  const item = state.studyList[state.studyIndex];
  studyDone.classList.add("hidden");
  studyCard.classList.remove("hidden");
  studyMeta.textContent = `今日学习 ${state.studyIndex + 1}/${state.studyList.length}`;
  studyChar.textContent = item.char;
  studyPinyin.textContent = item.pinyin || "";
  studyGuide.textContent = item.pronunciation_guide || "";
  studyMeaning.textContent = item.meaning || "";
  studyWords.textContent = item.words?.length ? `词语：${item.words.join(" / ")}` : "";
  studySentence.textContent = item.sentence ? `句子：${item.sentence}` : "";
  btnPlayChar.dataset.audioText = item.audio_text || item.pronunciation_guide || item.char;
}

async function finishStudySession() {
  const durationSeconds = Math.round((Date.now() - state.startedAt) / 1000);
  await requestJson("/api/progress/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      answers: state.answers,
      known_count: state.answers.filter((item) => item.known).length,
      unknown_count: state.answers.filter((item) => !item.known).length,
      duration_seconds: durationSeconds,
    }),
  });
}

async function handleAnswer(known) {
  if (state.studyIndex >= state.studyList.length) {
    return;
  }

  const item = state.studyList[state.studyIndex];
  state.answers.push({
    char: item.char,
    known,
    at: new Date().toISOString(),
  });
  state.studyIndex += 1;
  renderStudyCard();

  if (state.studyIndex >= state.studyList.length) {
    try {
      await finishStudySession();
    } catch (error) {
      studyMeta.textContent = error.message;
    }
  }
}

function renderWeek(pack) {
  if (!pack?.week_id) {
    weekTitle.textContent = "还没有本周故事包";
    weekBadge.textContent = "Week";
    weekSummary.textContent = "请让大人先去内容准备页生成内容。";
    renderChips(newCharList, []);
    renderChips(reviewCharList, []);
    renderWords([]);
    renderSentences([]);
    renderScenes([]);
    buildStudyList();
    renderStudyCard();
    return;
  }

  weekTitle.textContent = pack.title;
  weekBadge.textContent = pack.week_id;
  weekSummary.textContent = pack.summary;
  renderChips(newCharList, pack.new_chars || []);
  renderChips(reviewCharList, pack.review_chars || []);
  renderWords(pack.words || []);
  renderSentences(pack.sentences || []);
  renderScenes(pack.story || []);
  buildStudyList();
  renderStudyCard();
  attachAudioButtons(document);
}

async function loadAll() {
  const currentWeek = await requestJson("/api/current-week");
  state.currentWeek = currentWeek;
  renderWeek(currentWeek);
}

btnKnown.addEventListener("click", () => handleAnswer(true));
btnUnknown.addEventListener("click", () => handleAnswer(false));
btnPlayChar.addEventListener("click", () => {
  if (btnPlayChar.dataset.audioText) {
    speakText(btnPlayChar.dataset.audioText);
  }
});

loadAll().catch((error) => {
  studyMeta.textContent = error.message;
});
