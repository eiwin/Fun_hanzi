const fs = require("node:fs/promises");
const path = require("node:path");

const dataDir = path.resolve(__dirname, "..", "data");

async function readJson(fileName) {
  const filePath = path.join(dataDir, fileName);
  const content = await fs.readFile(filePath, "utf8");
  return JSON.parse(content);
}

async function writeJson(fileName, data) {
  const filePath = path.join(dataDir, fileName);
  const content = JSON.stringify(data, null, 2);
  await fs.writeFile(filePath, content);
}

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function getWeekId(date) {
  const utc = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = utc.getUTCDay() || 7;
  utc.setUTCDate(utc.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((utc - yearStart) / 86400000) + 1) / 7);
  return `${utc.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

function uniq(items) {
  return [...new Set(items.filter(Boolean))];
}

function shuffle(items) {
  const list = [...items];
  for (let index = list.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [list[index], list[swapIndex]] = [list[swapIndex], list[index]];
  }
  return list;
}

function pickWords(items, maxCount) {
  const words = items.flatMap((item) => item.words || []);
  return uniq(words).slice(0, maxCount);
}

function pickSentences(items, maxCount) {
  const sentences = items.map((item) => item.sentence).filter(Boolean);
  return uniq(sentences).slice(0, maxCount);
}

function chooseWeeklyChars(characters, progress, workflowRules) {
  const items = progress.items || {};
  const levelChars = characters.filter((item) => item.level === workflowRules.level);

  const sortedReview = levelChars
    .filter((item) => items[item.char])
    .sort((a, b) => {
      const aProgress = items[a.char];
      const bProgress = items[b.char];
      const aScore = (aProgress.box || 0) * 10 - (aProgress.wrongCount || 0);
      const bScore = (bProgress.box || 0) * 10 - (bProgress.wrongCount || 0);
      return aScore - bScore;
    });

  const reviewPool = sortedReview.slice(0, Math.max(workflowRules.weeklyReviewCount * 2, workflowRules.weeklyReviewCount));
  const review = shuffle(reviewPool).slice(0, workflowRules.weeklyReviewCount);

  const fresh = shuffle(levelChars
    .filter((item) => !items[item.char])
  ).slice(0, workflowRules.weeklyNewCount);

  return {
    review,
    fresh,
    all: [...review, ...fresh],
  };
}

function buildScenes(selected, workflowRules, words, sentences) {
  const scenes = [];
  const sceneCount = Math.min(workflowRules.storySceneCount, Math.max(sentences.length, 1));
  const sceneNames = ["早晨出发", "课堂发现", "开心收尾"];

  for (let index = 0; index < sceneCount; index += 1) {
    const fallbackItem = selected[index % selected.length];
    const text = sentences[index] || fallbackItem.sentence || `${fallbackItem.char} 在故事里出现。`;
    const focusChars = selected
      .slice(index, index + 3)
      .map((item) => item.char);
    const focusWords = words.slice(index, index + 2);
    const sceneTitle = sceneNames[index] || `场景 ${index + 1}`;

    scenes.push({
      id: `scene-${index + 1}`,
      title: sceneTitle,
      text,
      focusChars,
      imagePrompt: `Create a ${workflowRules.imageStyle} scene for children. Scene: ${text}. Include focus characters ${focusChars.join(", ")} and words ${focusWords.join(", ")}.`,
      videoPrompt: `Create a ${workflowRules.videoStyle} clip. Scene: ${text}. Keep the motion simple, cheerful, and easy for children to follow.`,
    });
  }

  return scenes;
}

function buildPack(selected, workflowRules, now) {
  const words = pickWords(selected.all, workflowRules.wordTarget);
  const sentences = pickSentences(selected.all, workflowRules.sentenceTarget);
  const focusChars = selected.all.map((item) => item.char);
  const title = focusChars.length
    ? `${focusChars.slice(0, 4).join("")}冒险周`
    : "本周汉字冒险";
  const summary = selected.fresh.length
    ? `本周会认识新字 ${selected.fresh.map((item) => item.char).join("、")}，再随机复习 ${selected.review.map((item) => item.char).join("、") || "旧字"}。故事会围绕 ${words.slice(0, 3).join("、")} 展开。`
    : `本周没有加入新字，重点复习 ${selected.review.map((item) => item.char).join("、") || "旧字"}。故事会围绕 ${words.slice(0, 3).join("、")} 展开。`;

  return {
    weekId: getWeekId(now),
    generatedAt: formatDate(now),
    title,
    summary,
    focus: {
      newChars: selected.fresh.map((item) => item.char),
      reviewChars: selected.review.map((item) => item.char),
    },
    words,
    sentences,
    story: buildScenes(selected.all, workflowRules, words, sentences),
  };
}

async function main() {
  const [characters, progress, workflowRules] = await Promise.all([
    readJson("characters.json"),
    readJson("progress.json"),
    readJson("workflow_rules.json"),
  ]);

  const now = new Date();
  const selected = chooseWeeklyChars(characters, progress, workflowRules);
  if (selected.all.length === 0) {
    throw new Error("No characters available for the weekly pack.");
  }

  const pack = buildPack(selected, workflowRules, now);
  await writeJson("current_week.json", pack);

  const weeklyPacks = Array.isArray(progress.weeklyPacks) ? progress.weeklyPacks : [];
  const withoutCurrent = weeklyPacks.filter((item) => item.weekId !== pack.weekId);
  progress.weeklyPacks = [
    ...withoutCurrent,
    {
      weekId: pack.weekId,
      generatedAt: pack.generatedAt,
      title: pack.title,
      newChars: pack.focus.newChars,
      reviewChars: pack.focus.reviewChars,
    },
  ];

  await writeJson("progress.json", progress);
  console.log(`Generated weekly pack ${pack.weekId}: ${pack.title}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
