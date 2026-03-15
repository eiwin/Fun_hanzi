const state = {
  currentWeek: null,
  weeks: [],
  selectedWeekId: "",
  studyList: [],
  studyIndex: 0,
  answers: [],
  startedAt: 0,
};

const weekTitle = document.getElementById("weekTitle");
const weekBadge = document.getElementById("weekBadge");
const weekPicker = document.getElementById("weekPicker");
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
const studyWordPinyin = document.getElementById("studyWordPinyin");
const studySentence = document.getElementById("studySentence");
const studySentencePinyin = document.getElementById("studySentencePinyin");
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

async function requestJsonOrNull(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Request failed.");
  }
  return response.json();
}

function renderWeekPicker() {
  const weeks = state.weeks || [];
  weekPicker.innerHTML = weeks.length
    ? weeks
        .map(
          (week, index) =>
            `<option value="${week.week_id}" ${week.week_id === state.selectedWeekId ? "selected" : ""}>${index === 0 ? "当前周" : week.week_id} · ${week.title || "未命名周包"}</option>`
        )
        .join("")
    : '<option value="">暂无周包</option>';
}

function renderChips(target, items) {
  target.innerHTML = items.length
    ? items.map((item) => `<span class="chip">${item}</span>`).join("")
    : '<span class="chip">暂无</span>';
}

function renderAnnotatedChips(target, items, pinyinMap = {}) {
  target.innerHTML = items.length
    ? items
        .map((item) => {
          const pinyin = pinyinMap[item];
          return `
            <span class="chip chip-annotated">
              <span class="chip-main">${item}</span>
              ${pinyin ? `<span class="chip-sub">${pinyin}</span>` : ""}
            </span>
          `;
        })
        .join("")
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

function renderPronunciationHint(item) {
  if (item?.pinyin_text) {
    return `<div class="pronunciation-line">${item.pinyin_text}</div>`;
  }
  if (item?.pronunciation_labels?.length) {
    return `<div class="pronunciation-tags">${item.pronunciation_labels
      .map((label) => `<span class="mini-pron">${label}</span>`)
      .join("")}</div>`;
  }
  return "";
}

function attachAudioButtons(scope = document) {
  scope.querySelectorAll("[data-audio-text]").forEach((button) => {
    button.addEventListener("click", () => {
      speakText(button.dataset.audioText);
    });
  });
}

function attachVideoCards(scope = document) {
  scope.querySelectorAll(".scene-video-shell").forEach((shell) => {
    const video = shell.querySelector("video");
    const button = shell.querySelector(".scene-play-button");
    if (!video || !button) {
      return;
    }

    button.addEventListener("click", async () => {
      video.controls = true;
      shell.classList.add("is-playing");
      try {
        await video.play();
      } catch {
        shell.classList.remove("is-playing");
      }
    });

    video.addEventListener("pause", () => {
      if (video.currentTime === 0 || video.ended) {
        shell.classList.remove("is-playing");
        video.controls = false;
      }
    });

    video.addEventListener("ended", () => {
      shell.classList.remove("is-playing");
      video.controls = false;
      video.currentTime = 0;
    });

    shell.querySelector(".scene-video-cover")?.addEventListener("click", () => {
      button.click();
    });
  });
}

function renderWords(items = []) {
  wordList.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="audio-item">
              <div class="audio-copy">
                <span class="audio-main">${item.text}</span>
                ${renderPronunciationHint(item)}
              </div>
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
              <div class="audio-copy">
                <span class="audio-main">${item.text}</span>
                ${renderPronunciationHint(item)}
              </div>
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
          <div class="scene-visual">
            ${scene.video_path
              ? `
                <div class="scene-video-shell ${scene.image_path ? "has-cover" : ""}">
                  ${scene.image_path ? `<img class="scene-video-cover" src="${scene.image_path}" alt="${scene.title}" />` : ""}
                  <video
                    class="scene-video"
                    preload="metadata"
                    playsinline
                    src="${scene.video_path}"
                    ${scene.image_path ? `poster="${scene.image_path}"` : ""}
                  ></video>
                  <button class="scene-play-button" type="button">播放视频</button>
                </div>
              `
              : visual}
          </div>
          <div class="scene-body">
            <h3>${scene.title}</h3>
            <p class="scene-text">${scene.text}</p>
            ${renderPronunciationHint(scene)}
            <div class="token-list">${(scene.focus_chars || []).map((char) => `<span class="token">${char}</span>`).join("")}</div>
            ${(scene.dialogue_line || scene.dialogue_pinyin)
              ? `
                <div class="scene-dialogue-card">
                  <div class="mini-label">固定台词</div>
                  <div class="scene-dialogue-hanzi">${scene.dialogue_line || scene.text}</div>
                  ${
                    scene.dialogue_pinyin
                      ? `<div class="scene-dialogue-pinyin">${scene.dialogue_pinyin}</div>`
                      : ""
                  }
                </div>
              `
              : ""}
            <div class="scene-audio-row">${playButton(scene.audio_text || scene.text, "听故事")}</div>
          </div>
        </article>
      `;
    })
    .join("");
  attachAudioButtons(sceneGrid);
  attachVideoCards(sceneGrid);
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
  studyWordPinyin.textContent = item.word_pronunciation_hints?.length
    ? `词语拼音提示：${item.word_pronunciation_hints.join(" / ")}`
    : "";
  studySentence.textContent = item.sentence ? `句子：${item.sentence}` : "";
  studySentencePinyin.textContent = item.sentence_pinyin
    ? `句子拼音提示：${item.sentence_pinyin}`
    : item.sentence_pronunciation_labels?.length
      ? `句子拼音提示：${item.sentence_pronunciation_labels.join(" / ")}`
      : "";
  btnPlayChar.dataset.audioText = item.audio_text || item.pronunciation_guide || item.char;
}

async function finishStudySession() {
  const durationSeconds = Math.round((Date.now() - state.startedAt) / 1000);
  await requestJson("/api/progress/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      week_id: state.currentWeek?.week_id || "",
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
    renderWeekPicker();
    return;
  }

  weekTitle.textContent = pack.title;
  weekBadge.textContent = pack.week_id;
  weekSummary.textContent = pack.summary;
  const pinyinMap = Object.fromEntries((pack.char_cards || []).map((item) => [item.char, item.pinyin || ""]));
  renderAnnotatedChips(newCharList, pack.new_chars || [], pinyinMap);
  renderAnnotatedChips(reviewCharList, pack.review_chars || [], pinyinMap);
  renderWords(pack.words || []);
  renderSentences(pack.sentences || []);
  renderScenes(pack.story || []);
  buildStudyList();
  renderStudyCard();
  renderWeekPicker();
  attachAudioButtons(document);
}

async function loadAll() {
  const weeksPayload = await requestJsonOrNull("/api/weeks");
  const fallbackWeek = await requestJson("/api/current-week");
  state.weeks = weeksPayload?.weeks?.length
    ? weeksPayload.weeks
    : fallbackWeek?.week_id
      ? [
          {
            week_id: fallbackWeek.week_id,
            generated_at: fallbackWeek.generated_at,
            title: fallbackWeek.title,
            summary: fallbackWeek.summary,
            new_chars: fallbackWeek.new_chars || [],
            review_chars: fallbackWeek.review_chars || [],
            status: fallbackWeek.status || "ready",
          },
        ]
      : [];
  if (!state.selectedWeekId && state.weeks.length) {
    state.selectedWeekId = state.weeks[0].week_id;
  }
  const query = state.selectedWeekId ? `?week_id=${encodeURIComponent(state.selectedWeekId)}` : "";
  const currentWeek = query ? (await requestJsonOrNull(`/api/current-week${query}`)) || fallbackWeek : fallbackWeek;
  state.currentWeek = currentWeek;
  state.selectedWeekId = currentWeek.week_id || state.selectedWeekId;
  renderWeek(currentWeek);
}

btnKnown.addEventListener("click", () => handleAnswer(true));
btnUnknown.addEventListener("click", () => handleAnswer(false));
weekPicker.addEventListener("change", async () => {
  state.selectedWeekId = weekPicker.value;
  await loadAll();
});
btnPlayChar.addEventListener("click", () => {
  if (btnPlayChar.dataset.audioText) {
    speakText(btnPlayChar.dataset.audioText);
  }
});

loadAll().catch((error) => {
  studyMeta.textContent = error.message;
});
