# Fun Hanzi

一个本地运行的中文启蒙学习系统，面向 9-13 岁学习者，采用 `Python 工作流 + 本地 Web 展示` 的结构。

系统目标：
- 以 `HSK 1-4` 为基础字库，按顺序推进新字
- 每周生成一份学习周包，包含新字、复习字、词、句、故事场景
- 支持图片、视频、音频、写字练习 PDF
- 学习记录、周包历史、素材清单全部保存在本地

## 1. 当前能力

- 学习页和后台页分离
  - 学习页给孩子用
  - 后台页给家长/老师用
- 周包生成
  - 支持“重建当前周”
  - 支持“开始下一周”
  - 支持连续生成未来多周
- 周包归档
  - 每周内容保存到 `data/weeks/<week_id>.json`
  - 当前学习页使用的周包保存到 `data/current_week.json`
- 学习记录
  - 记录认识/不认识
  - 记录 session history
  - 记录每个字的掌握情况
- 媒体管理
  - 手工导入图片
  - 手工导入视频
  - 学习页默认先显示图片，点击后才播放视频
- Prompt 管理
  - 支持重建图片 / 视频 prompt
  - 图片 prompt 采用“无文字插画 + 后期文字排版模板”的方式
- 拼音显示
  - 学习页显示教学型拼音
  - 例如：`你，第三声，nǐ`
  - 句子、词语、故事台词都带拼音展示
- 音频
  - 当前使用浏览器语音做本地试听
  - 字、词、句、故事都可试听
- 写字练习
  - 可生成 A4 写字练习 PDF
  - 用于打印练习

## 2. 技术结构

- 后端：`FastAPI`
- 定时任务：`APScheduler`
- 前端：原生 `HTML + CSS + JS`
- 数据：本地 `JSON`
- AI：可选 `OpenRouter`
- PDF：`reportlab`

主要目录：

```text
backend/              FastAPI、周包生成、选字、prompt、素材、PDF
frontend/             学习页与后台页
data/                 字库、进度、周包、日志、素材索引
data/weeks/           历史周包
data/assets/          图片、视频、PDF 等素材
scripts/              导入字库、频率表等脚本
skills/               项目内 AI skill 草案
hskhsk.com-main/      本地 HSK 源数据
```

## 3. 页面入口

- 本机学习页：`http://127.0.0.1:8000/learn`
- 本机后台页：`http://127.0.0.1:8000/admin`
- 局域网学习页：`http://你的局域网IP:8000/learn`
- 局域网后台页：`http://你的局域网IP:8000/admin`

学习页用于：
- 看本周故事包
- 学字、词、句
- 听音频
- 查看图片 / 点击播放视频

后台页用于：
- 生成当前周 / 下一周
- 切换历史周包
- 发布某一周到学习页
- 重建 prompt
- 导入图片 / 视频
- 下载写字练习 PDF
- 配置 OpenRouter 模型和 API key

### 3.1 局域网访问

现在默认会绑定到 `0.0.0.0`，所以同一局域网内的设备可以直接访问。

启动：

```bash
python3 -m backend
```

查看本机局域网 IP：

```bash
ipconfig getifaddr en0
```

如果你用的是有线网口，也可能需要：

```bash
ipconfig getifaddr en1
```

拿到 IP 后，例如是 `192.168.1.23`，则其他设备可以访问：

```text
http://192.168.1.23:8000/learn
http://192.168.1.23:8000/admin
```

如果 macOS 弹出防火墙提示，需要允许 Python 接受传入连接。

如果你只想恢复成“仅本机访问”，可以这样启动：

```bash
FUN_HANZI_HOST=127.0.0.1 python3 -m backend
```

## 4. 数据文件

核心数据文件：

- `data/characters.json`
  - 主字库
  - 目前已切换为 `HSK 1-4` 基础字库
- `data/hsk_word_bank.json`
  - HSK 词库
- `data/hsk_characters_l1_l4.json`
  - HSK 1-4 单字顺序表
- `data/progress.json`
  - 学习进度
  - session history
  - 每个字的掌握记录
- `data/current_week.json`
  - 当前发布给学习页的周包
- `data/weeks/<week_id>.json`
  - 历史周包归档
- `data/workflow_rules.json`
  - 每周新字数、复习字数、故事场景数、风格规则等
- `data/assets_manifest.json`
  - 图片 / 视频素材索引
- `data/generation_log.json`
  - 最近生成日志
- `data/ai_settings.json`
  - OpenRouter 配置

## 5. 周包工作流

### 5.1 基础规则

- 字库主线：`HSK 1 -> 2 -> 3 -> 4`
- 每周默认：
  - `5` 个新字
  - `3` 个复习字
  - `3` 个故事场景
- 复习字由掌握情况、错误次数、最近学习记录加权抽取

### 5.2 生成逻辑

一份周包包含：
- 标题
- 摘要
- 新字
- 复习字
- 字卡
- 词
- 句
- 故事场景
- 图片 prompt
- 视频 prompt
- 视频脚本
- 音频任务
- 写字练习 PDF 信息

### 5.3 当前按钮语义

后台页里常用操作：

- `发布到学习页`
  - 把选中的周包写入 `data/current_week.json`
  - 不重写内容
- `开始下一周内容`
  - 生成新的下一周周包
  - 历史周包保留
- `重建图像/视频 Prompt`
  - 重写当前选中周包的图片 / 视频 prompt
  - 如果启用 AI，优先走 AI；失败时回退本地模板
- `重建写字练习 PDF`
  - 只重建该周 PDF

## 6. 图片与视频策略

### 6.1 图片

图片采用“两段式”策略：

1. AI 只生成插画
2. 汉字与拼音后期排版

也就是说，图片 prompt 会明确要求：
- 图片里不要直接生成汉字、拼音、字母或文字
- 预留空白区域给后期文字排版

系统会额外生成一份：
- `后期文字排版模板`

后台页可以直接复制：
- 图片 prompt
- 后期文字排版模板

### 6.2 视频

视频 prompt 当前强调：
- 真实生活场景
- 9-13 岁学习者语境
- 微剧情结构
- 避免幼儿园式表演

学习页的视频行为：
- 如果有图片和视频，先显示图片
- 只有点击后才播放视频
- 图片作为视频封面

## 7. 拼音策略

系统现在不完全依赖单字默认读音，而是支持词级别覆盖规则。  
例如：
- `教室 -> jiào shì`
- `打电话 -> dǎ diàn huà`
- `地点 -> dì diǎn`

这样可以避免多音字在学习页、prompt、视频脚本、排版模板里反复出错。

## 8. AI 配置

如果要让周包内容生成 / prompt 重建调用 OpenRouter：

### 方式 A：后台填写

在后台页 `http://127.0.0.1:8000/admin`：
- 启用 AI
- 选择模型
- 填 API key
- 保存配置
- 测试连通性

### 方式 B：环境变量

推荐方式：

```bash
export OPENROUTER_API_KEY="your_key_here"
```

可选模型包括：
- `openrouter/auto`
- `openai/gpt-4o-mini`
- `minimax/minimax-m2.5`
- `moonshotai/kimi-k2`

注意：
- ChatGPT 订阅本身不能直接当 API key 使用
- 程序调用模型需要独立 API key

## 9. 本地运行

### 9.1 依赖安装

建议使用虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 9.2 启动

```bash
source .venv/bin/activate
python3 -m backend
```

然后打开：

```text
http://127.0.0.1:8000/learn
http://127.0.0.1:8000/admin
```

### 9.3 如果 macOS 上 Python 启动失败

某些机器首次运行可能需要先接受 Xcode license：

```bash
sudo xcodebuild -license
```

## 10. 常见操作

### 10.1 创建未来新周

后台页点击：
- `开始下一周内容`

也可以连续创建多周。

### 10.2 查看历史周包

后台页和学习页都可以切换历史周包。  
历史文件位置：

```text
data/weeks/
```

### 10.3 手工导入图片

后台页对应场景：
- 先复制图片 prompt
- 用外部工具出图
- 上传图片

### 10.4 手工导入视频

后台页对应场景：
- 上传视频文件
- 学习页会自动显示封面图
- 点击后才播放

### 10.5 重建 prompt

适合以下情况：
- 想让图片风格更统一
- 想让视频更有故事性
- 调整年龄段和语气
- 修复提示词不够详细的问题

## 11. 当前系统约定

目前项目有这些明确约定：

- 学习对象：`9-13 岁`
- 内容风格：更成熟，不走幼儿园路线
- 图片：不在图中直接生成文字
- 视频：真实生活微剧情
- 拼音：尽量词级正确，不只靠单字默认读音
- 当前基础字库：`HSK 1-4`

## 12. 已完成的重要实现

- HSK 1-4 字库导入
- HSK 词库导入
- HanziCraft 高频表本地存档
- 周包历史归档
- 学习页 / 后台页拆分
- 浏览器音频试听
- 手工图片 / 视频导入
- 写字练习 PDF
- OpenRouter 模型选择与连通测试
- 图片 prompt 与文字排版分离
- 多音字词覆盖机制

## 13. 后续可继续做

- 把更多多音字词加入覆盖表
- 继续批量优化后续周包
- 增强音频为真实 TTS 落盘
- 接更稳定的 AI 内容生成链路
- 增加学习历史查看页
- 增加“草稿周包”和“正式周包”机制
