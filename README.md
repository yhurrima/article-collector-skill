# Article Collector

刷到好文章但没时间读？让这个工具帮你「收藏即阅读」。

浏览器插件一键收藏，文章自动存入飞书多维表格；AI 帮你提取摘要和要点，定时通过飞书消息推送阅读汇总，生成可追溯的飞书文档。还支持阅读统计仪表盘，一眼看清你的阅读习惯和关注方向。

让你的收藏不再吃灰。

## 功能亮点

- **浏览器插件一键收藏** — 浏览网页时点击插件，文章自动存入飞书多维表格，标题、作者、来源、分类全部自动填充，不用打断阅读节奏
- **AI 帮你读完再告诉你重点内容** — 自动提取摘要和主要观点，帮你快速判断一篇文章是否值得深读
- **定时飞书消息推送** — 每天定时收到飞书消息，包含今日收藏的文章概览和汇总文档，适合通勤或睡前快速回顾
- **将收藏文章沉淀成飞书文档** — 不是一次性阅读，将一键收藏变成可回看的阅读资料。
- **阅读统计仪表盘** — 分类饼图、来源柱状图、每日收藏趋势，一眼看清你的阅读习惯和关注方向


## 快速开始

1. 在你的 Agent 中安装 skill
2. 对 Agent 说"帮我设置文章收藏"
3. Agent 会引导你完成配置 — 无需手动编辑配置文件

Agent 会询问:
- 是否有可用的模型 API（用于文章摘要）
- 每天什么时间推送阅读汇总
- 阅读汇总的篇幅（简短 / 中等 / 详细）

首次使用时，Agent 会自动创建飞书多维表格并告诉你:

> 我会创建一个飞书多维表格，以后你收藏的文章都可以在这里查看：<飞书多维表格链接>

## 安装

### Claude Code

```bash
git clone https://github.com/yhurrima/article-collector-skill.git ~/.claude/skills/article-collector
cd ~/.claude/skills/article-collector && ./setup.sh
```

### OpenClaw

```bash
git clone https://github.com/yhurrima/article-collector-skill.git ~/skills/article-collector
cd ~/skills/article-collector && ./setup.sh
```

### 手动安装

```bash
git clone https://github.com/yhurrima/article-collector-skill.git /path/to/article-collector
cd /path/to/article-collector
pip3 install -r requirements.txt
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入配置
./run.sh
```

安装脚本会:
- 安装 Python 依赖
- 检查 `lark-cli` 是否可用
- 从 `backend/.env.example` 创建配置文件
- 询问是否启用队列服务开机自启（macOS launchd）

## 使用方式

### 收藏文章

**浏览器插件（推荐）:** 安装插件后，浏览任意文章页面，点击插件图标即可收藏。

**对话方式:** 直接对 Agent 说:

```
收藏这篇文章，这是文章链接：https://example.com/article
```


### 查看阅读汇总

**自动推送:** 设置好定时推送后，每天会自动生成飞书文档并推送消息，不用手动操作。

**手动触发:** 随时对 Agent 说:

```
发送我今天的阅读汇总
```

Agent 会生成飞书文档并推送消息，包含:
- 今日关注领域和收藏篇数
- 每篇文章的摘要和主要观点
- 原文链接

### 查看阅读统计

对 Agent 说:

```
我想看我的阅读统计
看最近一周的阅读统计
4月份的阅读统计
```

Agent 会通过飞书 IM 推送统计摘要和仪表盘链接，仪表盘包含:
1. 收藏文章总数
2. 分类饼图
3. 来源柱状图
4. 每日收藏文章量折线图

支持时间筛选，在飞书仪表盘中可以按 `保存日期` 筛选任意时间段。

### 修改设置

所有设置都可以通过对话随时修改:

- "改成每天早上 9 点发送"
- "改成详细模式"
- "让总结短一点"
- "显示我当前的设置"

## 前置依赖

- Python 3.10+
- [lark-cli](https://github.com/nicholasxuu/lark-cli)（飞书命令行工具）
- 飞书机器人应用（具备多维表格、云文档、即时消息权限）
- 模型 API（可选，用于 AI 自动摘要；没有 API 时可以用 Agent 原生能力手动处理）
- IM 推送: 在 `backend/.env` 中设置 `FEISHU_IM_USER_ID`（私信）或 `FEISHU_IM_CHAT_ID`（群聊）

## 工作流程

```
用户点击插件 / 发送链接
        ↓
  抓取网页正文 → AI 提取结构化信息
        ↓
  写入飞书多维表格 → 机器人发送收藏确认
        ↓
  定时任务（每日）→ 读取当日文章 → 生成飞书文档 → 机器人推送汇总
```

## 浏览器插件

`chrome-extension/` 目录提供了 Chrome 浏览器插件。

安装步骤:
1. 打开 `chrome://extensions/`
2. 打开右上角"开发者模式"
3. 点击"加载未打包的程序"
4. 选择项目下的 `chrome-extension/` 文件夹
5. 打开文章页面，点击插件收藏

不装插件也可以直接用对话方式收藏。

## License

MIT

<!-- AUTO-README-START -->

## Auto-generated Project Map

- Project: `article-collector`
- Scripts:
  - `run.sh`: 加载 .env
  - `setup.sh`: Python 3.12+ (PEP 668) 不允许直接 pip install，用 --user 或 --break-system-packages
- Commands:
  - `bash run.sh`
  - `bash setup.sh`

This block is managed by `update-readme` and can be regenerated at any time.

<!-- AUTO-README-END -->
