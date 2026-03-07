const API = {
  rules: "/api/rules",
  characters: "/api/characters",
  progress: "/api/progress",
  currentWeek: "/api/current-week",
};

const state = {
  rules: null,
  characters: [],
  progress: { version: 1, items: {} },
  currentWeek: null,
  sessionList: [],
  index: 0,
  knownCount: 0,
  unknownCount: 0,
  sessionStartedAt: "",
  sessionAnswers: [],
  sessionFinalized: false,
};

const sessionInfo = document.getElementById("sessionInfo");
const feedback = document.getElementById("feedback");
const progressFill = document.getElementById("progressFill");
const card = document.getElementById("card");
const emptyState = document.getElementById("emptyState");
const storyTitle = document.getElementById("storyTitle");
const storySummary = document.getElementById("storySummary");
const focusChars = document.getElementById("focusChars");
const storyScenes = document.getElementById("storyScenes");
const weekBadge = document.getElementById("weekBadge");

const charText = document.getElementById("charText");
const pinyinText = document.getElementById("pinyinText");
const meaningText = document.getElementById("meaningText");
const wordText = document.getElementById("wordText");
const sentenceText = document.getElementById("sentenceText");

const btnKnown = document.getElementById("btnKnown");
const btnUnknown = document.getElementById("btnUnknown");

const cheers = [
  "太棒了！",
  "你真厉害！",
  "继续加油！",
  "好记性！",
  "做得好！",
];

const oops = [
  "没关系，再试试。",
  "慢慢来，一定会记住。",
  "下次就能对！",
];

function pickRandom(items) {
  return items[Math.floor(Math.random() * items.length)];
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function nowIso() {
  return new Date().toISOString();
}

function setSessionInfo() {
  const total = state.sessionList.length;
  const current = Math.min(state.index + 1, total);
  sessionInfo.textContent = `今日任务 ${current}/${total} · 认识 ${state.knownCount} · 不认识 ${state.unknownCount}`;
  progressFill.style.width = total === 0 ? "0%" : `${(state.index / total) * 100}%`;
}

function setCard(item) {
  charText.textContent = item.char;
  pinyinText.textContent = item.pinyin || "";
  meaningText.textContent = item.meaning || "";
  wordText.textContent = item.words && item.words.length ? `词语：${item.words.join(" / ")}` : "";
  sentenceText.textContent = item.sentence ? `句子：${item.sentence}` : "";
}

function renderCurrentWeek(pack) {
  if (!pack || !pack.weekId) {
    storyTitle.textContent = "还没有本周内容";
    storySummary.textContent = "先运行 node app/build-weekly-pack.js 生成本周故事包。";
    focusChars.innerHTML = "";
    storyScenes.innerHTML = "";
    weekBadge.textContent = "Week";
    return;
  }

  storyTitle.textContent = pack.title;
  storySummary.textContent = pack.summary;
  weekBadge.textContent = pack.weekId;

  const chips = [...(pack.focus?.newChars || []), ...(pack.focus?.reviewChars || [])]
    .map((char) => `<span class="char-chip">${char}</span>`)
    .join("");
  focusChars.innerHTML = chips;

  const scenes = (pack.story || [])
    .map(
      (scene) => `
        <article class="scene-card">
          <h3>${scene.title}</h3>
          <p>${scene.text}</p>
          <div class="scene-meta">字：${(scene.focusChars || []).join(" / ")}</div>
        </article>
      `
    )
    .join("");
  storyScenes.innerHTML = scenes;
}

function showCard() {
  if (state.sessionList.length === 0) {
    card.classList.add("hidden");
    emptyState.classList.remove("hidden");
    feedback.textContent = "可以先补充字库～";
    setSessionInfo();
    return;
  }

  if (state.index >= state.sessionList.length) {
    card.classList.add("hidden");
    emptyState.classList.remove("hidden");
    feedback.textContent = "今天完成啦！";
    finalizeSession();
    setSessionInfo();
    progressFill.style.width = "100%";
    return;
  }

  card.classList.remove("hidden");
  emptyState.classList.add("hidden");
  const item = state.sessionList[state.index];
  setCard(item);
  setSessionInfo();
}

function updateProgress(item, known) {
  const entry = state.progress.items[item.char] || {
    box: 0,
    lastSeen: "",
    correctStreak: 0,
    wrongCount: 0,
  };

  if (known) {
    entry.box = Math.min(entry.box + 1, 5);
    entry.correctStreak += 1;
  } else {
    entry.box = 1;
    entry.correctStreak = 0;
    entry.wrongCount += 1;
  }

  entry.lastSeen = today();
  state.progress.items[item.char] = entry;
}

function recordAnswer(item, known) {
  state.sessionAnswers.push({
    char: item.char,
    known,
    at: nowIso(),
  });
}

function finalizeSession() {
  if (state.sessionFinalized || state.sessionList.length === 0) {
    return;
  }

  const history = Array.isArray(state.progress.sessionHistory)
    ? state.progress.sessionHistory
    : [];

  history.unshift({
    startedAt: state.sessionStartedAt,
    finishedAt: nowIso(),
    weekId: state.currentWeek?.weekId || "",
    total: state.sessionList.length,
    knownCount: state.knownCount,
    unknownCount: state.unknownCount,
    answers: state.sessionAnswers,
  });

  state.progress.sessionHistory = history.slice(0, 20);
  state.sessionFinalized = true;
  saveProgress().catch(() => {
    feedback.textContent = "总结保存失败，请稍后再试。";
  });
}

async function saveProgress() {
  await fetch(API.progress, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.progress),
  });
}

function buildSessionList() {
  const rules = state.rules;
  const progressItems = state.progress.items;

  const reviews = state.characters.filter((item) => progressItems[item.char]);
  reviews.sort((a, b) => {
    const boxA = progressItems[a.char]?.box || 0;
    const boxB = progressItems[b.char]?.box || 0;
    return boxA - boxB;
  });

  const reviewCount = Math.min(rules.reviewPerSession, reviews.length);
  const reviewList = reviews.slice(0, reviewCount);

  const newItems = state.characters.filter((item) => !progressItems[item.char]);
  const newCount = Math.min(rules.newPerSession, newItems.length);
  const newList = newItems.slice(0, newCount);

  const list = [...reviewList, ...newList];
  state.sessionList = list.slice(0, rules.maxItemsPerSession);
  state.index = 0;
  state.knownCount = 0;
  state.unknownCount = 0;
  state.sessionStartedAt = nowIso();
  state.sessionAnswers = [];
  state.sessionFinalized = false;
}

async function loadAll() {
  const [rules, characters, progress, currentWeek] = await Promise.all([
    fetch(API.rules).then((r) => r.json()),
    fetch(API.characters).then((r) => r.json()),
    fetch(API.progress).then((r) => r.json()),
    fetch(API.currentWeek).then((r) => r.json()),
  ]);

  state.rules = rules;
  state.characters = characters.filter((item) => item.level === rules.level);
  state.progress = progress;
  state.currentWeek = currentWeek;
  renderCurrentWeek(currentWeek);
  buildSessionList();
  showCard();
}

btnKnown.addEventListener("click", async () => {
  const item = state.sessionList[state.index];
  if (!item) return;
  state.knownCount += 1;
  feedback.textContent = pickRandom(cheers);
  recordAnswer(item, true);
  updateProgress(item, true);
  state.index += 1;
  showCard();
  await saveProgress();
});

btnUnknown.addEventListener("click", async () => {
  const item = state.sessionList[state.index];
  if (!item) return;
  state.unknownCount += 1;
  feedback.textContent = pickRandom(oops);
  recordAnswer(item, false);
  updateProgress(item, false);
  state.index += 1;
  showCard();
  await saveProgress();
});

loadAll().catch(() => {
  sessionInfo.textContent = "加载失败：请先启动本地服务。";
  feedback.textContent = "例如：node app/server.js";
});
