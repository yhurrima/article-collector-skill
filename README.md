# Article Collector Skill

一键收藏网页文章到飞书多维表格，并生成每日阅读汇总飞书文档。

本仓库根目录就是一个完整的 Codex skill。别人拿到这个 GitHub 仓库链接后，可以让自己的 Agent 从该仓库安装这个 skill；安装后会同时包含 `SKILL.md`、后端脚本、浏览器插件和测试文件。

安装示例:

```text
请从这个 GitHub 仓库安装 article-collector skill：<你的 GitHub 仓库链接>
```

如果使用 Codex 的 skill 安装脚本，仓库根目录作为安装路径:

```bash
python3 install-skill-from-github.py --repo <owner>/<repo> --path . --name article-collector
```

## 变更内容:
- 浏览器插件点击收藏后，直接 POST 当前页面 URL 到本地队列服务 `http://127.0.0.1:5679/queue`。
- 后端抓取正文后必须调用模型 API 生成结构化摘要，不能用网页文本拼接假摘要。
- 飞书表格只保留一个 `主要内容` 字段；`summaryLength` 决定写入内容的篇幅。
- 处理失败时写入 `处理状态=处理失败`，阅读汇总里显示“仅保存链接，正文处理失败”。
- 首次使用时，skill 会询问发送报告时间、阅读汇总篇幅、API 配置，并强烈推荐安装浏览器插件。

## 使用方式:

### 0. 安装依赖

```bash
./setup.sh
```

安装脚本会:

- 安装 Python 依赖。
- 检查 `lark-cli` 是否可用。
- 如果 `backend/.env` 不存在，从 `backend/.env.example` 创建占位配置。

然后编辑 `backend/.env`，填入自己的 API 和飞书配置。

### 前置依赖

首次使用前需要:

- 安装 `lark-cli`。
- 使用 `lark-cli` 登录飞书机器人应用。
- 确保机器人应用具备多维表格、云文档、即时消息相关权限。

如果用户没有现成的飞书多维表格，skill 应直接引导创建一个飞书多维表格和文章收藏表，并把链接发给用户:

```text
我会创建一个飞书多维表格，以后你收藏的文章都可以在这里查看：<飞书多维表格链接>
```

### 1. 配置用户偏好

用户设置文件:

```text
~/.article-collector/config.json
```

关键字段:

```json
{
  "onboardingComplete": true,
  "timezone": "Asia/Shanghai",
  "deliverySchedule": "same_day",
  "deliveryTime": "21:00",
  "summaryLength": "detailed",
  "processingMode": "api",
  "delivery": {
    "method": "feishu",
    "chatId": ""
  }
}
```

`summaryLength` 支持:

- `brief`: 简短，2-4 条，每条 20-40 字。
- `medium`: 中等，建议 4-6 条，每条 60-100 字。
- `detailed`: 详细，建议 4-6 条，每条 300-400 字；如果文章主体太短，回退中等模式要求。

### 2. 初始化决策顺序

首次使用时，skill 不应直接先问发送时间，应按以下顺序执行。

先检测当前环境是否支持定时唤醒 Agent:

- 检查是否存在已知持久化 Agent 平台命令，例如 `openclaw`。
- 检查是否存在平台环境变量，例如 `OPENCLAW_*`、`AGENT_*`。
- 如果检测到平台能力，还需要执行 cron/list/status 或 dry-run 验证。
- 如果检测不到，按普通本地 CLI 环境处理。

然后询问 API:

```text
你有可用的模型API做文章总结吗？
```

选项:

- 有 API: `我有API，稍后提供base url/auth token/ai model`
- 没有 API: `没有 api，用我正在使用的agent的原生能力`

有 API 时，用户提供通用 API 配置:

- `BASE_URL`
- `AUTH_TOKEN`
- `AI_MODEL`

当前后端实际读取:

- `AI_BASE_URL` 或 `ANTHROPIC_BASE_URL`
- `AI_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`
- `AI_MODEL`

示例启动:

```bash
./run.sh
```

注意:

- 不要把用户 token 硬编码进仓库。
- 如果 API 不可用，必须报错或标记处理失败，不能本地拼接摘要。
- Codex Plus 订阅不能直接给浏览器插件后台当 API 使用。
- 有 API 模式支持后台自动处理文章，也可以配置每天固定时间自动生成并发送阅读报告。

发送时间询问规则:

- 用户有 API：继续询问发送报告时间，可选当天 21:00、第二天 09:00、手动发送。
- 用户没有 API，但当前环境是已验证的持久化 Agent 平台：继续询问发送报告时间。
- 用户没有 API，且当前环境不是持久化 Agent 平台：不要询问定时发送时间，直接提示“没有 API 不支持定时发送阅读报告。建议你配置 API；如果暂时不配置，也可以用手动触发方式获取阅读报告，例如说‘处理今天收藏的文章并发送阅读汇总’。”并将 `deliverySchedule` 设为 `manual`。
- 发送时间不写死为 9 点。当天发送保存为 `deliverySchedule=same_day`，第二天发送保存为 `deliverySchedule=next_day`，具体时间保存为 `deliveryTime=HH:MM`，例如第二天 10:00 发送保存为 `deliverySchedule=next_day`、`deliveryTime=10:00`。

没有 API 时，使用只保存链接模式:

- 浏览器插件先把链接保存到飞书表格。
- 记录状态为 `待处理`。
- 即使用户配置没有正确写成 `processingMode=link_only`，只要运行环境没有可用模型 API key，浏览器插件收藏也会保存为 `待处理`，不会误标为 `处理失败`。
- 之后用户对 Agent 说“处理今天收藏的文章”。
- Agent 再批量抓取、总结、写回飞书表格。
- 脚本函数 `daily_summary.get_pending_articles(date_str)` 会读取当天 `待处理` 记录。
- 脚本函数 `daily_summary.update_pending_article_completed(record_id, article, url)` 会写回处理结果并更新为“完成”。
- 脚本函数 `daily_summary.mark_pending_article_failed(record_id, error_message)` 会写回失败状态并更新为“处理失败”。
- 成功处理时，写回 `摘要`、`主要内容`、`关键词` 等字段，并将 `处理状态` 更新为“完成”。
- 处理失败时，保留链接并将 `处理状态` 更新为“处理失败”。
- Agent 不能只在对话里给出总结而不更新多维表格。
- 默认不支持无人值守定时发送阅读报告，只支持用户手动触发，例如说“处理今天收藏的文章并发送阅读汇总”。

生成阅读汇总前，脚本会先检查指定日期文章的 `处理状态`:

- `完成`：直接使用飞书表格中已有的 `摘要` 和 `主要内容`。
- 非 `完成`：先用模型 API 重新处理原文链接，成功后写回飞书表格并更新为 `完成`。
- API 处理失败：写回 `处理状态=处理失败`，阅读汇总中显示“仅保存链接，正文处理失败”。
- 无 API + 非持久化本地环境：定时脚本不能调用 Agent 原生能力，因此不能自动补全，只能手动触发 Agent 处理。
- 写回单条记录使用 `lark-cli base +record-upsert --record-id <record_id>`，不要使用 `+record-batch-update`；当前环境下 batch update 可能触发 OpenAPI 限制。

对应配置:

```json
{
  "processingMode": "link_only"
}
```

### 定时能力边界

- 有 API 模式：可以由系统定时任务或平台定时任务运行脚本，脚本调用模型 API 处理文章并发送飞书阅读报告。
- macOS：支持 `launchd` 定时任务安装。
- OpenClaw 等持久化 Agent 平台：支持平台 cron 唤醒 Agent，但必须先验证平台能力。
- Windows：暂不支持系统定时任务安装。Windows 用户可以手动运行日报脚本，后续可扩展 Windows Task Scheduler。
- 无 API + 普通本地 CLI 环境：不支持无人值守定时自动总结，因为系统定时任务不能唤醒当前 Agent 会话调用原生 LLM 能力。
- 无 API + 持久化 Agent 平台：只有平台明确支持定时唤醒 Agent 时才可尝试自动处理。需要先检测平台命令或环境变量，并执行 cron/list/status 或 dry-run 验证。
- 无 API且检测不到可唤醒 Agent 平台：只能配置定时提醒，让用户打开 Agent 后手动触发处理和发送。

日报脚本支持动态日期参数:

```bash
python3 backend/daily_summary.py --today
python3 backend/daily_summary.py --yesterday
python3 backend/daily_summary.py --date 2026-05-02
```

后续定时任务安装器应按用户设置生成命令:

- `deliverySchedule=same_day`、`deliveryTime=HH:MM`：每天 `HH:MM` 运行 `python3 backend/daily_summary.py --today`。
- `deliverySchedule=next_day`、`deliveryTime=HH:MM`：每天 `HH:MM` 运行 `python3 backend/daily_summary.py --yesterday`。
- `deliverySchedule=manual`：不安装自动发送任务。

macOS 安装/卸载定时任务:

```bash
python3 backend/install_scheduler.py
python3 backend/uninstall_scheduler.py
```

安装器会读取 `~/.article-collector/config.json`。如果配置为 `manual`，或无 API 且不是持久化 Agent 平台，不会安装自动总结任务。

macOS 注意事项:

- 不要把项目放在 `~/Desktop`、`~/Documents`、`~/Downloads` 下安装 launchd 定时任务。
- 这些目录受 macOS 隐私权限保护，launchd 可能报 `Operation not permitted`，导致脚本无法读取。
- 推荐放在 `~/Projects/article-collector` 或 `~/.article-collector/app`。
- 安装器会检测这些受保护目录并拒绝安装。
- launchd 默认 `PATH` 很短，可能找不到 `lark-cli`；也可能使用系统 Python，导致缺少 `bs4` 等依赖。
- 安装器会把当前 Python 解释器的绝对路径写入 plist，并把当前 `PATH` 写入 `EnvironmentVariables`，避免定时任务和手动运行环境不一致。

OpenClaw 持久化平台应使用平台 cron。创建任务时必须指定明确的投递通道和目标，不要使用 `--channel last`:

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

创建后必须运行:

```bash
openclaw cron list
openclaw cron run <jobId>
```

### 3. 启动队列服务

```bash
./run.sh
```

服务地址:

```text
http://127.0.0.1:5679/queue
```

健康检查:

```bash
curl -sS -X OPTIONS http://127.0.0.1:5679/queue -i
```

### 4. 安装浏览器插件

插件目录:

```text
chrome-extension/
```

Chrome 安装步骤:

1. 打开 `chrome://extensions/`。
2. 打开右上角“开发者模式”。
3. 点击“加载未打包的程序”。
4. 选择当前项目下的 `chrome-extension/` 文件夹。
5. 打开任意文章页面，点击插件收藏。

不安装插件也可以在 Agent 对话框里发送:

```text
收藏这篇文章，这是文章链接：https://example.com/article
```

## 影响范围:

### 主要文件

```text
SKILL.md                    # skill 首次使用、设置管理和使用规则
backend/queue_server.py     # 浏览器插件 POST 入口
backend/auto_process.py     # 收藏处理、API 摘要、飞书写入
backend/extractor.py        # 网页抓取、正文清洗、API 调用
backend/daily_summary.py    # 每日汇总、失败文章重试、飞书文档生成
backend/user_settings.py    # 用户设置读取和保存
chrome-extension/           # Chrome 插件
tests/test_daily_summary.py # 回归测试
```

### 飞书表格字段

文章收藏表核心字段:

- 标题
- 原文链接
- 作者
- 来源
- 发布日期
- 分类
- 摘要
- 关键词
- 主要内容
- 保存日期
- 处理状态

历史上曾试过 `主要内容-简短`、`主要内容-中等`、`主要内容-详细` 三个字段；当前方案不再使用这些字段，新内容统一写入 `主要内容`。

## 验证方式:

### 单元测试

```bash
python3 -m unittest discover -s tests
```

### 语法检查

```bash
python3 -m py_compile backend/extractor.py backend/auto_process.py backend/daily_summary.py backend/config.py
```

### 插件链路测试

1. 启动 `queue_server.py`。
2. Chrome 安装 `chrome-extension/`。
3. 打开文章页面并点击插件。
4. 检查飞书表格:
   - 成功文章: `处理状态=完成`，`主要内容` 非空。
   - 失败文章: `处理状态=处理失败`，不生成假摘要。
5. 生成阅读汇总，检查飞书文档:
   - 序号不能二次编号。
   - 失败文章显示“仅保存链接，正文处理失败”。

## 已知坑点

- 部分网站在代理环境下抓取失败；当前实现会在默认抓取失败后关闭代理重试。
- 知乎专栏可能出现 `SSLError: UNEXPECTED_EOF_WHILE_READING`，即使关闭代理也可能失败。
- TechCrunch 视频/播客页正文较短，详细模式可能回退为中等模式，这是为了避免编造。
- 页面抓取可能混入作者简介、订阅入口、相关阅读；当前实现优先提取正文容器并清理常见页面噪音。
- 飞书文档中的 `主要内容` 如果已经带序号，生成文档时不能再包一层有序列表，否则会出现 `1. a.` 或二次编号。

<!-- AUTO-README-START -->

## Auto-generated Project Map

- Project: `2026-05-01-article-collector-skill`
- Scripts:
  - `run.sh`: 加载 .env
- Commands:
  - `bash run.sh`
  - `bash setup.sh`

This block is managed by `update-readme` and can be regenerated at any time.

<!-- AUTO-README-END -->
