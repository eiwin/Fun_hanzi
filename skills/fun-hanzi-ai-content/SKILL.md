---
name: fun-hanzi-ai-content
description: Generate Fun Hanzi weekly content packs: choose the next five new characters in frequency order, mix in weighted review characters based on mastery, and produce stories, words, sentences, image prompts, and video prompts for child-friendly Chinese learning.
---

# Fun Hanzi AI Content

Use this skill when working on the Fun Hanzi content pipeline: weekly pack planning, new/review character selection, story building, and image/video prompt generation.

## Inputs

Read these files first:

- `data/characters.json`
- `data/progress.json`
- `data/workflow_rules.json`
- `data/current_week.json` when adjusting an existing week

## Weekly selection rules

For HSK1 level content:

1. Pick new characters in frequency order.
2. Default to 5 new characters per new week.
3. Pick review characters from learned characters, biased toward:
   - lower mastery box
   - higher wrong count
   - longer time since last review
4. Keep a small amount of randomness inside the review pool.

Do not randomize the new-character order unless the user explicitly asks for it.

## Content generation rules

After selecting characters:

1. Build words using the chosen characters.
2. Build short sentences suitable for children.
3. Build a three-scene story using both new and review characters when possible.
4. Produce image prompts.
5. Produce video prompts.
6. Produce a fixed spoken line for each story scene.
7. Produce a separate pinyin reference for the learning page.

## Pinyin rules

- Use tone-marked pinyin, not numeric pinyin.
- Keep pinyin exact in prompt notes.
- For video generation, do not require the model to render pinyin subtitles unless the user explicitly asks for it.
- Prefer showing Hanzi in the video and letting the learning page display the exact pinyin.

## Output preference

When asked to generate content, prefer updating the existing app data contract:

- `current_week.json`
- `data/weeks/<week_id>.json`
- `generation_log.json`

When asked only to brainstorm or review, do not rewrite the week pack automatically.
