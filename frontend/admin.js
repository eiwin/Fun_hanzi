const state = {
  currentWeek: null,
  status: null,
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
const adminStatus = document.getElementById("adminStatus");
const btnGenerateWeek = document.getElementById("btnGenerateWeek");
const btnRegeneratePrompts = document.getElementById("btnRegeneratePrompts");

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || "Request failed.");
  }
  return response.json();
}

function setButtonBusy(button, busy) {
  button.disabled = busy;
}

function renderChips(target, items) {
  target.innerHTML = items.length
    ? items.map((item) => `<span class="chip">${item}</span>`).join("")
    : '<span class="chip">暂无</span>';
}

function renderTokens(target, items) {
  target.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="audio-item">
              <span>${item.text}</span>
              <button class="btn btn-audio btn-inline-audio" type="button" data-audio-text="${(item.audio_text || item.text)
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">听</button>
            </div>
          `
        )
        .join("")
    : '<div class="audio-item"><span>暂无</span></div>';
}

function renderSentences(items) {
  sentenceList.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <div class="audio-item">
              <span>${item.text}</span>
              <button class="btn btn-audio btn-inline-audio" type="button" data-audio-text="${(item.audio_text || item.text)
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">听</button>
            </div>
          `
        )
        .join("")
    : '<div class="audio-item"><span>暂无</span></div>';
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

function attachAudioButtons(scope = document) {
  scope.querySelectorAll("[data-audio-text]").forEach((button) => {
    button.addEventListener("click", () => {
      speakText(button.dataset.audioText);
    });
  });
}

function renderAdminStatus(log) {
  const last = log?.last_run;
  if (!last) {
    adminStatus.textContent = "还没有生成记录。";
    return;
  }
  adminStatus.innerHTML = `
    <div><strong>最近动作：</strong>${last.type}</div>
    <div><strong>时间：</strong>${last.ran_at || "未知"}</div>
    <div><strong>状态：</strong>${last.status}</div>
    <div><strong>内容：</strong>${last.title || "暂无标题"}</div>
    ${last.error ? `<div><strong>错误：</strong>${last.error}</div>` : ""}
  `;
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
        : `<div class="scene-placeholder">待导入图片<br />可以先用 ChatGPT 按 prompt 生成，再上传到这里。</div>`;

      return `
        <article class="scene-card" data-scene-id="${scene.id}">
          <div class="scene-visual">${visual}</div>
          <div class="scene-body">
            <h3>${scene.title}</h3>
            <p class="scene-text">${scene.text}</p>
            <div class="meta-label">目标字</div>
            <div class="token-list">${(scene.focus_chars || []).map((char) => `<span class="token">${char}</span>`).join("")}</div>
            <div class="meta-label">图片 Prompt</div>
            <div class="meta-box">${scene.image_prompt || "暂无"}</div>
            <div class="meta-label">视频脚本</div>
            <div class="meta-box">${scene.video_script || "暂无"}</div>
            <div class="scene-status">图片状态：${scene.image_status || "pending"}</div>
            <div class="scene-audio-row">
              <button class="btn btn-audio btn-inline-audio" type="button" data-audio-text="${(scene.audio_text || scene.text)
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">听故事</button>
            </div>
            <form class="upload-form">
              <div class="upload-row">
                <input type="file" name="file" accept="image/png,image/jpeg,image/webp" required />
                <button type="submit" class="btn btn-secondary">导入图片</button>
              </div>
            </form>
          </div>
        </article>
      `;
    })
    .join("");

  sceneGrid.querySelectorAll(".upload-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const card = event.currentTarget.closest(".scene-card");
      const sceneId = card.dataset.sceneId;
      const fileInput = form.querySelector('input[type="file"]');
      const file = fileInput.files?.[0];
      if (!file || !state.currentWeek?.week_id) {
        return;
      }

      const submitButton = form.querySelector("button");
      setButtonBusy(submitButton, true);
      const payload = new FormData();
      payload.append("week_id", state.currentWeek.week_id);
      payload.append("scene_id", sceneId);
      payload.append("file", file);

      try {
        await fetch("/api/admin/import-image", { method: "POST", body: payload }).then(async (response) => {
          if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "图片导入失败。");
          }
        });
        await loadAll();
      } catch (error) {
        adminStatus.textContent = error.message;
      } finally {
        setButtonBusy(submitButton, false);
        form.reset();
      }
    });
  });
  attachAudioButtons(sceneGrid);
}

function renderWeek(pack) {
  if (!pack?.week_id) {
    weekTitle.textContent = "还没有本周故事包";
    weekBadge.textContent = "Week";
    weekSummary.textContent = "点击右侧按钮即可生成本周内容。";
    renderChips(newCharList, []);
    renderChips(reviewCharList, []);
    renderTokens(wordList, []);
    renderSentences([]);
    renderScenes([]);
    return;
  }

  weekTitle.textContent = pack.title;
  weekBadge.textContent = pack.week_id;
  weekSummary.textContent = pack.summary;
  renderChips(newCharList, pack.new_chars || []);
  renderChips(reviewCharList, pack.review_chars || []);
  renderTokens(wordList, pack.words || []);
  renderSentences(pack.sentences || []);
  renderScenes(pack.story || []);
  attachAudioButtons(document);
}

async function loadAll() {
  const [currentWeek, status] = await Promise.all([
    requestJson("/api/current-week"),
    requestJson("/api/admin/status"),
  ]);

  state.currentWeek = currentWeek;
  state.status = status;

  renderWeek(currentWeek);
  renderAdminStatus(status);
}

btnGenerateWeek.addEventListener("click", async () => {
  setButtonBusy(btnGenerateWeek, true);
  try {
    await requestJson("/api/admin/generate-week?force=true", { method: "POST" });
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusy(btnGenerateWeek, false);
  }
});

btnRegeneratePrompts.addEventListener("click", async () => {
  setButtonBusy(btnRegeneratePrompts, true);
  try {
    await requestJson("/api/admin/regenerate-prompts", { method: "POST" });
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusy(btnRegeneratePrompts, false);
  }
});

loadAll().catch((error) => {
  adminStatus.textContent = error.message;
});
