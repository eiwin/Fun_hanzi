const state = {
  currentWeek: null,
  weeks: [],
  selectedWeekId: "",
  status: null,
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
const progressCards = document.getElementById("progressCards");
const adminStatus = document.getElementById("adminStatus");
const worksheetCard = document.getElementById("worksheetCard");
const nextWeekCount = document.getElementById("nextWeekCount");
const aiEnabled = document.getElementById("aiEnabled");
const aiProvider = document.getElementById("aiProvider");
const aiPreset = document.getElementById("aiPreset");
const aiModel = document.getElementById("aiModel");
const aiApiKey = document.getElementById("aiApiKey");
const aiApiKeyEnv = document.getElementById("aiApiKeyEnv");
const aiBaseUrl = document.getElementById("aiBaseUrl");
const aiSiteUrl = document.getElementById("aiSiteUrl");
const aiAppName = document.getElementById("aiAppName");
const aiStatus = document.getElementById("aiStatus");
const btnPublishWeek = document.getElementById("btnPublishWeek");
const btnGenerateNextWeek = document.getElementById("btnGenerateNextWeek");
const btnRegeneratePrompts = document.getElementById("btnRegeneratePrompts");
const btnGenerateWorksheet = document.getElementById("btnGenerateWorksheet");
const btnSaveAiSettings = document.getElementById("btnSaveAiSettings");
const btnTestAi = document.getElementById("btnTestAi");

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

function renderAiSettings(payload) {
  const settings = payload?.settings || {};
  const presets = payload?.model_presets || [];
  aiEnabled.checked = !!settings.enabled;
  aiProvider.value = settings.provider || "openrouter";
  aiModel.value = settings.model || "openrouter/auto";
  aiApiKey.value = settings.api_key || "";
  aiApiKeyEnv.value = settings.api_key_env || "OPENROUTER_API_KEY";
  aiBaseUrl.value = settings.base_url || "https://openrouter.ai/api/v1";
  aiSiteUrl.value = settings.site_url || "http://127.0.0.1:8000";
  aiAppName.value = settings.app_name || "Fun Hanzi";
  aiPreset.innerHTML = [
    '<option value="">自定义</option>',
    ...presets.map((item) => `<option value="${item.value}">${item.label}</option>`),
  ].join("");
  aiPreset.value = presets.some((item) => item.value === aiModel.value) ? aiModel.value : "";
}

function collectAiSettings() {
  return {
    enabled: aiEnabled.checked,
    provider: aiProvider.value.trim() || "openrouter",
    model: aiModel.value.trim() || "openrouter/auto",
    api_key: aiApiKey.value.trim(),
    api_key_env: aiApiKeyEnv.value.trim() || "OPENROUTER_API_KEY",
    base_url: aiBaseUrl.value.trim() || "https://openrouter.ai/api/v1",
    site_url: aiSiteUrl.value.trim() || "http://127.0.0.1:8000",
    app_name: aiAppName.value.trim() || "Fun Hanzi",
  };
}

function setButtonBusy(button, busy) {
  button.disabled = busy;
}

function setButtonBusyLabel(button, busy, busyLabel) {
  if (!button.dataset.idleLabel) {
    button.dataset.idleLabel = button.textContent;
  }
  setButtonBusy(button, busy);
  button.textContent = busy ? busyLabel : button.dataset.idleLabel;
}

function showActionProgress(message) {
  adminStatus.innerHTML = `
    <div><strong>处理中：</strong>${message}</div>
    <div>这一步可能需要 10-60 秒，请稍等页面自动刷新。</div>
  `;
}

function confirmAction(message) {
  return window.confirm(message);
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

async function copyText(text, button) {
  if (!text) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    const original = button.textContent;
    button.textContent = "已复制";
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  } catch {
    adminStatus.textContent = "复制失败，请检查浏览器剪贴板权限。";
  }
}

function attachCopyButtons(scope = document) {
  scope.querySelectorAll("[data-copy-text]").forEach((button) => {
    button.addEventListener("click", () => {
      copyText(button.dataset.copyText, button);
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

function renderAdminStatus(log) {
  const last = log?.last_run;
  const libraryInfo = log?.library_info;
  const progress = log?.learning_progress;
  renderProgressCards(progress);
  if (!last) {
    adminStatus.innerHTML = `
      <div>还没有生成记录。</div>
      ${
        libraryInfo
          ? `<div><strong>基础字库：</strong>${libraryInfo.base} · ${libraryInfo.character_count} 字 · ${libraryInfo.word_count} 词</div>
             <div><strong>推进策略：</strong>${libraryInfo.strategy} · level ${libraryInfo.levels.join(" → ")}</div>`
          : ""
      }
    `;
    return;
  }
  adminStatus.innerHTML = `
    ${
      libraryInfo
        ? `<div><strong>基础字库：</strong>${libraryInfo.base} · ${libraryInfo.character_count} 字 · ${libraryInfo.word_count} 词</div>
           <div><strong>推进策略：</strong>${libraryInfo.strategy} · level ${libraryInfo.levels.join(" → ")}</div>`
        : ""
    }
    <div><strong>最近动作：</strong>${last.type}</div>
    <div><strong>时间：</strong>${last.ran_at || "未知"}</div>
    <div><strong>状态：</strong>${last.status}</div>
    <div><strong>生成方式：</strong>${last.generation_mode || "template"}</div>
    <div><strong>内容：</strong>${last.title || "暂无标题"}</div>
    ${last.published_at ? `<div><strong>发布时间：</strong>${last.published_at}</div>` : ""}
    ${last.error ? `<div><strong>错误：</strong>${last.error}</div>` : ""}
  `;
}

function renderProgressCards(progress) {
  if (!progressCards) {
    return;
  }

  const positionText =
    progress?.level_position_start && progress?.level_position_end
      ? `第 ${progress.level_position_start}${progress.level_position_end > progress.level_position_start ? `-${progress.level_position_end}` : ""}`
      : "-";

  const positionNote = progress?.level_total_chars
    ? `本级共 ${progress.level_total_chars} 个字`
    : "等待生成统计";

  progressCards.innerHTML = `
    <article class="progress-card">
      <div class="progress-label">当前程度</div>
      <div class="progress-value">${progress?.current_level_label || "HSK -"}</div>
      <div class="progress-note">当前周所属 level</div>
    </article>
    <article class="progress-card">
      <div class="progress-label">本周位置</div>
      <div class="progress-value">${positionText}</div>
      <div class="progress-note">${positionNote}</div>
    </article>
    <article class="progress-card">
      <div class="progress-label">累计学过</div>
      <div class="progress-value">${progress?.studied_char_count || 0}</div>
      <div class="progress-note">${progress?.tracked_item_count || 0} 个字已有跟踪记录</div>
    </article>
    <article class="progress-card">
      <div class="progress-label">累计掌握</div>
      <div class="progress-value">${progress?.mastered_char_count || 0}</div>
      <div class="progress-note">${progress?.session_count || 0} 次学习 · ${progress?.answer_count || 0} 次作答</div>
    </article>
  `;
}

function renderWorksheet(worksheet) {
  if (!worksheet?.file_path) {
    worksheetCard.textContent = "写字练习 PDF 还没有准备好。";
    return;
  }

  worksheetCard.innerHTML = `
    <div><strong>写字练习：</strong>${worksheet.page_size || "A4"} · ${worksheet.entries || 0} 个字</div>
    <div><a href="${worksheet.file_path}" target="_blank" rel="noreferrer">打开/下载 PDF</a></div>
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
          <div class="scene-visual">
            ${scene.video_path
              ? `
                <div class="scene-video-shell ${scene.image_path ? "has-cover" : ""}">
                  ${
                    scene.image_path
                      ? `<img class="scene-video-cover" src="${scene.image_path}" alt="${scene.title}" />`
                      : ""
                  }
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
            <div class="meta-label">目标字</div>
            <div class="token-list">${(scene.focus_chars || []).map((char) => `<span class="token">${char}</span>`).join("")}</div>
            <div class="meta-row">
              <div class="meta-label">图片 Prompt</div>
              <button class="btn btn-copy" type="button" data-copy-text="${(scene.image_prompt || "")
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">复制</button>
            </div>
            <div class="meta-box">${scene.image_prompt || "暂无"}</div>
            <div class="meta-row">
              <div class="meta-label">后期文字排版</div>
              <button class="btn btn-copy" type="button" data-copy-text="${(scene.image_text_layout || "")
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">复制</button>
            </div>
            <div class="meta-box">${scene.image_text_layout || "暂无"}</div>
            <div class="meta-row">
              <div class="meta-label">视频脚本</div>
              <button class="btn btn-copy" type="button" data-copy-text="${(scene.video_script || "")
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">复制</button>
            </div>
            <div class="meta-box">${scene.video_script || "暂无"}</div>
            <div class="scene-status">图片状态：${scene.image_status || "pending"} · 视频状态：${scene.video_status || "pending"}</div>
            <div class="scene-audio-row">
              <button class="btn btn-audio btn-inline-audio" type="button" data-audio-text="${(scene.audio_text || scene.text)
                .replaceAll("&", "&amp;")
                .replaceAll('"', "&quot;")
                .replaceAll("<", "&lt;")}">听故事</button>
            </div>
            <form class="upload-form upload-form-image">
              <div class="upload-row">
                <input type="file" name="file" accept="image/png,image/jpeg,image/webp" required />
                <button type="submit" class="btn btn-secondary">导入图片</button>
              </div>
            </form>
            <form class="upload-form upload-form-video">
              <div class="upload-row">
                <input type="file" name="file" accept="video/mp4,video/quicktime,video/webm,video/x-m4v" required />
                <button type="submit" class="btn btn-secondary">导入视频</button>
              </div>
            </form>
          </div>
        </article>
      `;
    })
    .join("");

  sceneGrid.querySelectorAll(".upload-form-image").forEach((form) => {
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

  sceneGrid.querySelectorAll(".upload-form-video").forEach((form) => {
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
        await fetch("/api/admin/import-video", { method: "POST", body: payload }).then(async (response) => {
          if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "视频导入失败。");
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
  attachCopyButtons(sceneGrid);
  attachVideoCards(sceneGrid);
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
    renderWorksheet(null);
    renderWeekPicker();
    return;
  }

  weekTitle.textContent = pack.title;
  weekBadge.textContent = pack.week_id;
  weekSummary.textContent = pack.summary;
  if (pack.published_at || pack.updated_at) {
    const meta = [];
    if (pack.published_at) {
      meta.push(`发布于 ${pack.published_at}`);
    }
    if (pack.updated_at) {
      meta.push(`更新于 ${pack.updated_at}`);
    }
    weekSummary.textContent += ` ${meta.join("；")}`;
  }
  renderChips(newCharList, pack.new_chars || []);
  renderChips(reviewCharList, pack.review_chars || []);
  renderTokens(wordList, pack.words || []);
  renderSentences(pack.sentences || []);
  renderScenes(pack.story || []);
  renderWorksheet(pack.worksheet);
  renderWeekPicker();
  attachAudioButtons(document);
  attachCopyButtons(document);
}

async function loadAll() {
  const fallbackWeek = await requestJson("/api/current-week");
  const [weeksPayload, aiPayload] = await Promise.all([
    requestJsonOrNull("/api/weeks"),
    requestJson("/api/admin/ai-settings"),
  ]);

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
  const status = await requestJson(`/api/admin/status${query}`);

  state.currentWeek = currentWeek;
  state.selectedWeekId = currentWeek.week_id || state.selectedWeekId;
  state.status = status;

  renderWeek(currentWeek);
  renderAdminStatus(status);
  renderAiSettings(aiPayload);
}

btnPublishWeek.addEventListener("click", async () => {
  if (
    !confirmAction(
      `将把 ${state.currentWeek?.week_id || "当前周"} 发布到学习页。这个操作不会重建 prompt，只会更新学习页使用的周包。确定继续吗？`
    )
  ) {
    return;
  }
  setButtonBusyLabel(btnPublishWeek, true, "正在发布...");
  showActionProgress(`正在发布 ${state.currentWeek?.week_id || "当前周"} 到学习页`);
  try {
    const query = state.currentWeek?.week_id ? `?week_id=${encodeURIComponent(state.currentWeek.week_id)}` : "";
    const published = await requestJson(`/api/admin/publish-week${query}`, { method: "POST" });
    state.selectedWeekId = published.week_id || state.selectedWeekId;
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnPublishWeek, false, "正在发布...");
  }
});

btnGenerateNextWeek.addEventListener("click", async () => {
  const count = Math.min(Math.max(Number.parseInt(nextWeekCount.value || "1", 10) || 1, 1), 8);
  if (
    !confirmAction(
      `将从 ${state.currentWeek?.week_id || "当前周"} 开始，连续创建 ${count} 周的新周包：系统会按汉字频率顺序挑选下一批新字，并结合掌握情况抽取旧字复习。确定继续吗？`
    )
  ) {
    return;
  }
  setButtonBusyLabel(btnGenerateNextWeek, true, "正在创建...");
  showActionProgress(`正在连续创建 ${count} 周的新内容`);
  try {
    const baseWeekId = state.currentWeek?.week_id || "";
    const query = new URLSearchParams({
      force: "true",
      week_offset: "1",
      count: String(count),
    });
    if (baseWeekId) {
      query.set("base_week_id", baseWeekId);
    }
    const nextWeek = await requestJson(`/api/admin/generate-week?${query.toString()}`, { method: "POST" });
    state.selectedWeekId = nextWeek.last_week_id || nextWeek.week_id || "";
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnGenerateNextWeek, false, "正在创建...");
  }
});

btnRegeneratePrompts.addEventListener("click", async () => {
  if (
    !confirmAction(
      `将重建 ${state.currentWeek?.week_id || "当前周"} 的图像和视频 prompt。这个操作可能覆盖你手动调整过的 prompt。确定继续吗？`
    )
  ) {
    return;
  }
  setButtonBusyLabel(btnRegeneratePrompts, true, "正在重建...");
  showActionProgress(`正在重建 ${state.currentWeek?.week_id || "当前周"} 的图像和视频 prompt`);
  try {
    const query = state.currentWeek?.week_id ? `?week_id=${encodeURIComponent(state.currentWeek.week_id)}` : "";
    await requestJson(`/api/admin/regenerate-prompts${query}`, { method: "POST" });
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnRegeneratePrompts, false, "正在重建...");
  }
});

btnGenerateWorksheet.addEventListener("click", async () => {
  if (
    !confirmAction(
      `将重建 ${state.currentWeek?.week_id || "当前周"} 的写字练习 PDF。确定继续吗？`
    )
  ) {
    return;
  }
  setButtonBusyLabel(btnGenerateWorksheet, true, "正在生成...");
  showActionProgress(`正在重建 ${state.currentWeek?.week_id || "当前周"} 的写字练习 PDF`);
  try {
    const query = state.currentWeek?.week_id ? `?week_id=${encodeURIComponent(state.currentWeek.week_id)}` : "";
    await requestJson(`/api/admin/generate-worksheet${query}`, { method: "POST" });
    await loadAll();
  } catch (error) {
    adminStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnGenerateWorksheet, false, "正在生成...");
  }
});

weekPicker.addEventListener("change", async () => {
  state.selectedWeekId = weekPicker.value;
  await loadAll();
});

aiPreset.addEventListener("change", () => {
  if (aiPreset.value) {
    aiModel.value = aiPreset.value;
  }
});

btnSaveAiSettings.addEventListener("click", async () => {
  setButtonBusyLabel(btnSaveAiSettings, true, "正在保存...");
  try {
    const payload = await requestJson("/api/admin/ai-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectAiSettings()),
    });
    renderAiSettings(payload);
    aiStatus.textContent = "AI 配置已保存。";
  } catch (error) {
    aiStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnSaveAiSettings, false, "正在保存...");
  }
});

btnTestAi.addEventListener("click", async () => {
  setButtonBusyLabel(btnTestAi, true, "正在测试...");
  try {
    await requestJson("/api/admin/ai-settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectAiSettings()),
    });
    const result = await requestJson("/api/admin/test-ai", { method: "POST" });
    aiStatus.textContent = `AI 连通成功：${result.model || ""} ${result.message || ""}`.trim();
  } catch (error) {
    aiStatus.textContent = error.message;
  } finally {
    setButtonBusyLabel(btnTestAi, false, "正在测试...");
  }
});

loadAll().catch((error) => {
  adminStatus.textContent = error.message;
});
