---
name: article-collector
description: 文章收藏夹 - 一键收藏网页文章到飞书多维表格，自动生成每日/每周汇总
trigger: 用户想要收藏网页文章、查看收藏列表、生成阅读汇总时使用此 skill
---

# Article Collector Skill

## 核心能力
将网页文章智能收藏到飞书多维表格，每日自动生成汇总文档并由机器人推送。

## 首次使用
当用户第一次使用本 skill，或 `~/.article-collector/config.json` 不存在，或配置中 `onboardingComplete=false` 时，不要直接执行收藏或发送汇总；必须先完成初始化询问。

### 前置依赖检查
初始化前先检查:
- 是否已安装 `lark-cli`。
- 是否已通过 `lark-cli` 登录飞书机器人应用，并具备多维表格、云文档、即时消息相关权限。

如果没有安装 `lark-cli`，告诉用户需要先安装飞书 CLI，并在安装后重新运行初始化。

如果没有登录机器人应用，告诉用户需要使用 `lark-cli` 完成飞书机器人应用登录/授权，确保机器人可以:
- 创建和读写飞书多维表格。
- 创建飞书文档。
- 以机器人身份发送飞书消息。

### 飞书多维表格检查
初始化前检查 `backend/.env` 中是否已配置 `FEISHU_BASE_APP_TOKEN`：

- **已配置（老用户）**：查询多维表格链接并告诉用户："你正在使用的飞书多维表格：<多维表格链接>"
- **未配置（新用户）**：直接帮用户创建一个飞书多维表格，创建文章收藏表所需字段，然后将 `FEISHU_BASE_APP_TOKEN`、`FEISHU_ARTICLES_TABLE_ID`、`FEISHU_WEEKLY_TABLE_ID`、`FEISHU_IM_CHAT_ID` 写入 `backend/.env`。创建完成后告诉用户："我会创建一个飞书多维表格，以后你收藏的文章都可以在这里查看：<飞书多维表格链接>"

初始化时按以下顺序询问和判断（不要跳过或调换顺序，不要先问发送时间）：

1. 运行环境能力检测
- 先判断当前环境是否是支持定时唤醒 Agent 的持久化平台（如 OpenClaw）。
- 检测方式：是否存在 `openclaw` 命令、是否存在 `OPENCLAW_*` 或 `AGENT_*` 环境变量；如果检测到平台能力，还要执行平台 cron/list/status 或 dry-run 验证。
- 记录结果：`isPersistentPlatform = true/false`。如果检测不到可唤醒 Agent 平台，记录为普通本地 CLI 环境。

2. API 配置
- 询问用户：”你有可用的模型API做文章总结吗？”
- 选项 1：”我有API，稍后提供base url/auth token/ai model”。如果用户选择有 API，一次性要求用户提供以下三个值（不要逐个提问）：
  - `BASE_URL`、`AUTH_TOKEN`、`AI_MODEL`
- API 配置不限定 Anthropic 命名；用户只需要提供可用的 `BASE_URL`、`AUTH_TOKEN`、`AI_MODEL`。
- 当前后端可将通用配置映射为实际运行环境，例如 `BASE_URL` → `ANTHROPIC_BASE_URL` 或 `AI_BASE_URL`，`AUTH_TOKEN` → `ANTHROPIC_AUTH_TOKEN` 或 `AI_API_KEY`。
- 选择有 API 时，支持浏览器插件后台自动处理文章，也支持配置每天固定时间自动生成并发送阅读报告。
- 选项 2：”没有 api，用我正在使用的agent的原生能力”。如果用户选择没有 API，推送阅读汇总前，由 Agent 读取飞书多维表格里收藏的文章并总结。不支持定时自动发送。
- 说明：自动后台摘要需要模型 API；没有 API 时，不能用网页文本拼接假摘要，也不能让浏览器插件后台直接调用 Codex Plus 订阅能力。
- 防御规则：如果运行环境没有可用模型 API key，即使用户配置没有正确写成 `processingMode=link_only`，浏览器插件收藏也必须保存为 `处理状态=待处理`，不要误写成 `处理失败`。

3. 发送报告时间
- 如果用户有 API，或用户没有 API 但 `isPersistentPlatform=true`，询问发送时间：
  - 当天晚上 9 点：当天收藏，当天 21:00 发送阅读汇总，也可以接受用户指定的其他时间，例如当天 22:30。
  - 第二天早上 9 点：当天收藏，第二天 09:00 发送阅读汇总，也可以接受用户指定的其他时间，例如第二天早上 10:00。
  - 不定时：只在用户说”发送我今天的阅读汇总”时发送。
- 如果用户没有 API 且 `isPersistentPlatform=false`（非持久化平台），**不要询问定时选项**。直接告诉用户：”没有 API 不支持定时发送阅读报告。建议你配置 API；如果暂时不配置，也可以用手动触发方式获取阅读报告，例如说‘处理今天收藏的文章并发送阅读汇总’。” 并将 `deliverySchedule` 设为 `manual`。
- 保存动态时间时使用 `deliverySchedule=same_day` 或 `deliverySchedule=next_day`，并将用户指定时间保存到 `deliveryTime=HH:MM`。旧配置 `same_day_21`、`next_day_09` 仅作为兼容读取。

4. 阅读汇总篇幅
- 简短：只保留简要信息，适合快速扫读。
- 中等：保留主要观点和关键细节，适合日常阅读汇总。
- 详细：保留背景、观点、必要解释和可追溯原始资料细节，适合沉淀阅读笔记。

无 API 模式使用只保存链接模式。Agent 批量处理待处理文章后必须写回飞书表格:
- 先调用 `daily_summary.get_pending_articles(date_str)` 读取当天 `处理状态=待处理` 的记录，拿到 `record_id` 和 `原文链接`。
- 对每篇文章，Agent 负责抓取/阅读链接并生成结构化结果。
- 成功处理时，写回 `标题`、`作者`、`来源`、`发布日期`、`分类`、`摘要`、`关键词`、`主要内容`，并将 `处理状态` 更新为“完成”。
- 成功写回时调用 `daily_summary.update_pending_article_completed(record_id, article, url)`。
- 处理失败时，保留 `原文链接`，记录失败原因，并将 `处理状态` 更新为“处理失败”。
- 失败写回时调用 `daily_summary.mark_pending_article_failed(record_id, error_message)`。
- 不能只在对话里给出总结而不更新多维表格。

生成阅读汇总前必须检查指定日期所有文章的 `处理状态`：
- `完成`：直接使用飞书表格中已有内容生成飞书文档。
- 非 `完成`：先处理原文链接，成功后写回 `摘要`、`主要内容`、`关键词` 等字段，并更新为 `完成`；失败则写回 `处理状态=处理失败`。
- 写回单条记录时使用 `lark-cli base +record-upsert --record-id <record_id>`。不要使用 `+record-batch-update`，当前环境可能触发 `OpenAPIBatchUpdateRecords limited`。
- 有 API 定时模式下，由脚本调用模型 API 自动补全。
- 无 API + 非持久化本地环境下，脚本不能调用 Agent 原生能力，不能自动补全；必须提示用户手动触发 Agent 处理。
- 无 API + 持久化 Agent 平台下，平台定时唤醒 Agent 后，可以由 Agent 补全并写回飞书表格。

**强制步骤：询问浏览器插件安装**

初始化完成后，必须询问用户是否安装浏览器插件。询问时必须强调强烈推荐安装，说明核心优势：

> **强烈推荐安装浏览器插件** — 浏览网页时一键收藏，无需复制粘贴链接，体验远优于手动发送链接。安装后点击插件图标即可自动抓取、总结、写入飞书。

使用 `AskUserQuestion` 询问，选项：
- “安装插件 (强烈推荐)” — 说明：浏览网页时点击插件即可一键收藏，自动完成抓取和总结
- “不安装” — 说明：直接在对话框发送链接收藏

如果用户选择安装，Agent 必须按以下步骤操作：

**第一步：启动队列服务**
Agent 必须先在后台启动队列服务，确保用户加载插件后能立即使用：
```bash
# 在项目目录下后台启动
cd ~/.claude/skills/article-collector && ./run.sh
```
使用 `Bash` 工具的 `run_in_background` 参数启动，不要阻塞对话。启动后等待 2 秒确认服务在 `http://127.0.0.1:5679/queue` 可访问。

**第二步：引导用户加载浏览器插件**
告诉用户通过 Chrome 开发者模式加载未打包的程序：
1. 打开 Chrome，进入 `chrome://extensions/`。
2. 打开右上角”开发者模式”。
3. 点击”加载未打包的程序”。
4. 按 `Cmd+Shift+G`，粘贴路径：`~/.claude/skills/article-collector/chrome-extension/`。
5. 确认扩展出现后，打开任意文章页面，点击插件即可收藏。

不要让用户手动运行任何命令。队列服务由 Agent 在后台自动启动。

如果不安装浏览器插件，告诉用户可以直接在 Agent 的对话框里发送”收藏这篇文章，这是文章链接：<url>”，Agent 会按相同流程处理。

初始化完成后，保存设置到 `~/.article-collector/config.json`，并将 `onboardingComplete` 设为 `true`。

必须提醒用户（使用方式）：
- 浏览网页时点击插件 → 链接自动保存到飞书多维表格（从 `backend/.env` 读取 `FEISHU_BASE_APP_TOKEN`，拼接链接 `https://my.feishu.cn/base/<FEISHU_BASE_APP_TOKEN>` 并展示给用户）
- 如果你不用浏览器插件，也可以直接对我说：”帮我收藏这个文章，这是链接”
- 想看汇总时说：”发送我今天的阅读汇总”
- 想看统计时说：”我想看我的阅读统计”
- 随时可以修改设置，例如：”改成详细模式”、”改成每天晚上9点发送”

所有设置之后都可以通过对话随时修改，例如：
- “改成每天早上 9 点发送”
- “改成详细模式”
- “让总结短一点”
- “显示我当前的设置”

## 定时能力判断
设置定时发送前，先根据处理模式和运行环境判断能力边界：

- **有 API 模式**：可以用系统定时任务或平台定时任务运行脚本，由脚本调用模型 API 处理文章并发送飞书阅读报告。
- **macOS + 有 API 模式**：可以运行 `python3 backend/install_scheduler.py` 安装 launchd 定时任务；卸载用 `python3 backend/uninstall_scheduler.py`。
- macOS 安装前必须检查项目路径。不要在 `~/Desktop`、`~/Documents`、`~/Downloads` 下安装 launchd 定时任务；这些目录可能触发 macOS 隐私权限限制，导致 `Operation not permitted`。推荐用户把项目放到 `~/Projects/article-collector` 或 `~/.article-collector/app`。
- macOS launchd 安装时必须使用当前 Python 解释器绝对路径，并写入当前 `PATH`。不要让 launchd 默认使用系统 Python；否则可能缺少 `bs4` 等依赖，或找不到 `/usr/local/bin/lark-cli`。
- **Windows**：暂不支持系统定时任务安装。不要承诺 Windows 用户可以自动安装定时发送；只能手动运行 `daily_summary.py --today/--yesterday`，或等待后续 Windows Task Scheduler 支持。
- **无 API + 普通本地 CLI 环境**：不能无人值守定时自动总结，因为系统定时任务只能运行脚本，不能唤醒当前 Agent 会话调用原生 LLM 能力。此模式只支持用户手动触发处理和发送。
- **无 API + 持久化 Agent 平台**：只有平台明确支持定时唤醒 Agent 时才可尝试自动处理。应先检测已知平台命令或环境变量，例如 `openclaw`、`OPENCLAW_*`、`AGENT_*`，再执行平台 cron/list/status 或 dry-run 测试。
- **无 API且检测不到可唤醒 Agent 平台**：可以配置定时提醒，由脚本在指定时间向用户发送飞书消息，提醒用户打开 Agent 并发送“处理昨天收藏的文章并发送阅读汇总”。

### OpenClaw 定时任务
如果检测到 OpenClaw，使用平台 cron，而不是 macOS launchd：

```bash
openclaw cron add \
  --name "Article Collector Daily Summary" \
  --cron "<cron expression>" \
  --tz "<user IANA timezone>" \
  --session isolated \
  --message "Run the article-collector skill: process pending articles if needed, generate the configured reading summary, create the Feishu doc, and send the Feishu message." \
  --announce \
  --channel <channel name> \
  --to "<target ID>" \
  --exact
```

必须指定 `--channel` 和 `--to`，不要使用 `--channel last`。创建后必须用 `openclaw cron list` 和 `openclaw cron run <jobId>` 验证用户能收到消息。

## 设置管理
当用户要求修改设置时，更新 `~/.article-collector/config.json`：
- 用户说“改成简短/中等/详细模式”时，更新 `summaryLength` 为 `brief` / `medium` / `detailed`。
- 用户说“当天晚上 9 点发送”时，更新 `deliverySchedule=same_day`、`deliveryTime=21:00`。
- 用户说“第二天早上 9 点发送”时，更新 `deliverySchedule=next_day`、`deliveryTime=09:00`。
- 用户指定其他时间时，按用户指定值更新 `deliveryTime=HH:MM`，例如“第二天早上 10 点发送”保存为 `deliverySchedule=next_day`、`deliveryTime=10:00`。
- 用户说“不定时”或“我手动叫你发送”时，更新 `deliverySchedule=manual`。
- 用户说“显示我当前的设置”时，读取并展示当前发送报告时间、阅读汇总篇幅、时区和推送方式。

## 流程
```
用户发链接 → 抓取网页 → AI 提取结构化信息 → 写入飞书多维表格
                                                       ↓
                                              机器人发送收藏确认
                                                       ↓
                                            定时任务(每日汇总)
                                                       ↓
                                    读取表格 → 生成飞书文档 → 机器人推送(概览+文档链接)
```

## 命令

### /save [url]
收藏文章。用法：
- `/save <url>` — 直接收藏指定链接
- 浏览器插件点击收藏时，会 POST 当前页面 URL 到本地 `http://127.0.0.1:5679/queue`，由 `backend/queue_server.py` 自动触发处理。

收藏处理步骤：

1. **抓取内容**: 用 requests + BeautifulSoup 获取网页正文
   - 国内网站、微信公众号: 直接 requests 抓取
   - Reddit: 用 old.reddit.com 抓取
   - WebFetch 不可用时: fallback 到 Python requests
2. **AI 解析**: 从正文中提取结构化信息：
   - title: 优化后的标题
   - author: 作者
   - source: 来源平台/网站名
   - publish_date: 发布日期 (YYYY-MM-DD)
   - category: 分类 (技术/产品/设计/商业/AI/其他)
   - summary: 一句话摘要 (30字以内)
   - main_points: 主要内容 (3-5条，每条20-40字的完整句子)
   - tags: 2-3个标签
3. **写入飞书**: 用 lark-cli 写入多维表格
4. **确认推送**: 机器人发送收藏确认消息

写入命令（从 `backend/config.py` 读取 FEISHU_BASE_APP_TOKEN 和 FEISHU_ARTICLES_TABLE_ID）：
```bash
lark-cli base +record-batch-create \
  --base-token $FEISHU_BASE_APP_TOKEN \
  --table-id $FEISHU_ARTICLES_TABLE_ID \
  --json '{"fields":["标题","原文链接","作者","来源","发布日期","分类","摘要","关键词","主要内容","保存日期"],"rows":[["标题值","链接值","作者值","来源值","日期值","分类值","摘要值","标签1, 标签2","要点1\n要点2\n要点3","今天日期"]]}'
```

IM 推送命令（从 config.py 读取 FEISHU_IM_CHAT_ID），使用 `--markdown` 格式以支持换行和富文本。

**重要：`--markdown` 参数中不能使用 `\n` 表示换行，`\n` 会被当作字面量。必须使用 heredoc 传递多行内容：**
```bash
lark-cli im +messages-send --as bot --chat-id $FEISHU_IM_CHAT_ID --markdown "$(cat <<'MARKDOWN'
**已收藏: {标题}**

{摘要}
MARKDOWN
)"
```
如果消息内容是动态拼接的，用 Python 脚本发送：
```bash
python3 -c "
import subprocess, sys
msg = '**已收藏: {标题}**\n\n{摘要}'
subprocess.run(['lark-cli', 'im', '+messages-send', '--as', 'bot', '--chat-id', sys.argv[1], '--markdown', msg], check=True)
" "$FEISHU_IM_CHAT_ID"
```

### /daily-summary
生成今日阅读汇总：

1. **读取今天的文章**（从 config.py 读取 FEISHU_BASE_APP_TOKEN 和 FEISHU_ARTICLES_TABLE_ID）:
```bash
lark-cli base +record-list --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --limit 200
```
过滤出"保存日期"等于今天的记录。

2. **生成飞书文档** (结构):
   - 今日概览: 关注领域 + 每篇文章摘要
   - 文章详情: 标题 + 摘要 + 主要内容(有序列表) + 来源链接
3. **创建飞书文档**:
```bash
lark-cli docs +create --title "YYYY-MM-DD 阅读汇总" --markdown "文档内容"
```
4. **机器人推送 IM** (Markdown 格式):
   - 今日概览: 关注领域 + 重点内容
   - 今日文章列表: 每个标题可点击跳转原文
   - 文档链接: 查看完整汇总

### /weekly-summary
每周统计，推送仪表盘链接：

1. 读取本周所有文章
2. 统计：总阅读量、分类分布、高频标签、主要来源
3. 推送仪表盘链接 + 本周概览文字

仪表盘: 在飞书中打开多维表格后点击"仪表盘"标签页即可查看

### /reading-stats
当用户说”我想看我的阅读统计”、”打开阅读统计”或”查看阅读仪表盘”时，创建或复用名为”阅读统计”的飞书多维表格仪表盘，通过飞书 IM 推送摘要统计 + 仪表盘链接给用户。

支持时间筛选：用户可以说”看最近一周的阅读统计”或”4月份的阅读统计”，Agent 根据用户指定的时间范围传入 `--start-date` 和 `--end-date`。不指定时间时默认最近 30 天。

执行方式：
```bash
python3 backend/reading_stats_dashboard.py
python3 backend/reading_stats_dashboard.py --start-date 2026-04-01 --end-date 2026-04-30
```

仪表盘要求：
- 名称固定为”阅读统计”。
- 数据源使用文章收藏表。
- 基于 `保存日期` 支持用户在飞书仪表盘中筛选时间范围。
- 组件布局（按顺序）：
  1. 收藏文章总数（statistics 类型）：统计全部文章数量。
  2. 分类分布（pie 类型）：按 `分类` 统计文章数量。
  3. 来源分布（column 类型）：按 `来源` 统计文章数量，并按数量降序展示。
  4. 每日收藏文章量（line 类型）：按 `保存日期` 统计每日收藏数量，并按日期升序展示。

IM 推送内容：
- 时间范围内的总收藏篇数。
- 分类分布（各分类篇数）。
- 来源 Top 5。
- 仪表盘链接（点击可跳转到飞书多维表格仪表盘）。

处理规则：
- 如果“阅读统计”仪表盘已存在，复用现有仪表盘，不重复创建。
- 如果缺少图表组件，只补齐缺失的”收藏文章总数”、”分类分布”、”来源分布”、”每日收藏文章量”组件。
- 创建或补齐组件后，返回 `dashboard_url` 给用户。
- 如果缺少 `FEISHU_BASE_APP_TOKEN` 或 `FEISHU_ARTICLES_TABLE_ID`，明确提示用户先完成飞书配置。

### /list-articles
列出最近收藏的文章（从 config.py 读取 FEISHU_BASE_APP_TOKEN 和 FEISHU_ARTICLES_TABLE_ID）：
```bash
lark-cli base +record-list --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --limit 20
```

## 飞书配置
所有飞书相关 token 从 `backend/config.py`（环境变量）读取，首次使用时由 onboarding 引导用户配置。配置项：
- FEISHU_BASE_APP_TOKEN — 多维表格 App Token
- FEISHU_ARTICLES_TABLE_ID — 文章收藏表 ID
- FEISHU_WEEKLY_TABLE_ID — 每周统计表 ID
- FEISHU_IM_CHAT_ID — 机器人推送的群聊 ID

## 多维表格字段
文章收藏表:
- 标题 (text)
- 原文链接 (text)
- 作者 (text)
- 来源 (text)
- 发布日期 (text)
- 分类 (select: 技术/产品/设计/商业/AI/其他)
- 摘要 (text)
- 关键词 (text)
- 主要内容 (text)
- 保存日期 (text)
- 处理状态 (select: 待处理/完成/处理失败)

### 创建 select 字段的正确方式
`+field-create` 不支持内联选项，必须分两步：先创建字段，再用 `+field-update` 添加选项。

```bash
# 第一步：创建字段（不带选项）
lark-cli base +field-create --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --json '{"name":"分类","type":"single_select"}'
lark-cli base +field-create --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --json '{"name":"处理状态","type":"single_select"}'

# 第二步：用 +field-update 添加选项（注意：options 在顶层，不是 property.options）
lark-cli base +field-update --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --field-id "分类" --json '{"name":"分类","type":"single_select","options":[{"name":"技术"},{"name":"产品"},{"name":"设计"},{"name":"商业"},{"name":"AI"},{"name":"其他"}]}'
lark-cli base +field-update --base-token $FEISHU_BASE_APP_TOKEN --table-id $FEISHU_ARTICLES_TABLE_ID --field-id "处理状态" --json '{"name":"处理状态","type":"single_select","options":[{"name":"待处理"},{"name":"完成"},{"name":"处理失败"}]}'
```

## 浏览器插件 (可选)
chrome-extension/ 文件夹提供了浏览器插件。

使用方式：
1. 在项目根目录运行 `./run.sh` 启动队列服务（端口 5679）。
2. Chrome 开发者模式加载 chrome-extension/ 文件夹
3. 点击插件 → 自动将当前页面 URL 发送到 `http://127.0.0.1:5679/queue`
4. 后端自动抓取、调用 API 摘要、写入飞书表格并发送确认消息

不装插件也可以直接用 `/save <url>` 收藏。
