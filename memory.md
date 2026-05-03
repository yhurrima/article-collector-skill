# memory.md

- 日期: 2026-05-03
- 任务: 文章收藏 skill 的 API 摘要、浏览器插件、飞书写入和首次使用流程整理
- 结论: 摘要必须走模型 API；飞书表格只使用一个 `主要内容` 字段；用户通过 `summaryLength` 选择简短、中等、详细；首次使用必须询问报告时间、摘要篇幅、API 配置，并强烈推荐安装浏览器插件。
- 原因: 浏览器插件后台不能直接调用 Codex Plus 订阅能力；没有 API 时无法稳定自动摘要。多字段 `主要内容-简短/中等/详细` 会增加表格复杂度，且收藏时只需要按当前用户偏好生成一个最终结果。
- 影响: 后端处理失败时不能本地拼接假摘要，必须写 `处理状态=处理失败`；阅读汇总里显示“仅保存链接，正文处理失败”。后续新文章按当前 `summaryLength` 写入 `主要内容`。
- 后续注意: 用户提供 API 时，询问通用 `BASE_URL`、`AUTH_TOKEN`、`AI_MODEL`，不要限定 `ANTHROPIC_*` 命名；实际运行时可映射到 `ANTHROPIC_BASE_URL`、`ANTHROPIC_AUTH_TOKEN`、`AI_MODEL` 或 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`。

- 日期: 2026-05-03
- 任务: 网页抓取失败和页面噪音处理
- 结论: 默认抓取失败后，需要关闭系统代理重试；正文提取应优先选择 `article`、`main` 等正文容器，并移除作者简介、订阅入口、相关阅读、广告、评论等噪音。
- 原因: 本地环境存在 `HTTP_PROXY`、`HTTPS_PROXY`，部分网站在代理下会 SSL 失败。TechCrunch 等页面会把播客订阅、作者简介、相关链接混入整页文本。
- 影响: `extractor.fetch_article()` 先用当前环境抓取，失败后用 `requests.Session(trust_env=False)` 无代理重试；摘要 prompt 明确要求只总结文章主体内容。
- 后续注意: 知乎专栏仍可能出现 `SSLError: UNEXPECTED_EOF_WHILE_READING`，这类失败应保留为 `处理失败`，不要伪造摘要。

- 日期: 2026-05-03
- 任务: 阅读汇总飞书文档格式修复
- 结论: `主要内容` 已经是编号文本时，飞书文档不能再嵌套有序列表。
- 原因: 嵌套有序列表会导致飞书文档出现 `1.` 空行和 `a.` 子项，格式错误。
- 影响: 文档生成时直接渲染 `主要内容` 行，避免二次编号。
- 后续注意: 修改 `daily_summary.py` 时必须保留相关测试，防止序号格式回退。

- 日期: 2026-05-03
- 任务: 详细模式篇幅定义
- 结论: 详细模式建议 4-6 条，每条 300-400 字；如果文章主体很短，不足以支撑详细内容，应自动回退中等模式要求。
- 原因: 短文章或视频页主体资料不足，强行写长会导致模型编造或引入页面周边信息。
- 影响: `extractor.py` 的 detailed prompt 明确要求包含可追溯原始资料细节，并禁止泛泛概括。
- 后续注意: 如果用户要求更长摘要，需要先确认是否允许基于背景知识扩展；默认只基于原文。

- 日期: 2026-05-03
- 任务: 浏览器插件安装体验
- 结论: 首次使用时强烈推荐安装浏览器插件，但也必须保留无插件使用方式。
- 原因: 插件能降低收藏成本；但 Chrome 扩展安装需要用户通过开发者模式加载 `chrome-extension/`，部分 macOS 环境下 Agent 不能代替用户点击 Chrome UI。
- 影响: skill 首次使用话术会询问是否安装插件，并说明 `chrome://extensions/`、开发者模式、加载未打包程序的步骤。
- 后续注意: 若要 Agent 代操作 Chrome，需 macOS 授权辅助功能/自动化权限；否则只能打开页面和目录，不能替用户点击。

- 日期: 2026-05-03
- 任务: 无 API 模式下的定时能力边界
- 结论: 有 API 模式可以由定时任务运行脚本并调用模型 API 自动总结；无 API + 普通本地 CLI 环境不能无人值守定时自动总结，只能手动触发或定时提醒用户打开 Agent。只有部署在明确支持定时唤醒 Agent 的持久化平台时，才可以尝试无 API 定时自动处理。
- 原因: 系统 crontab/launchd 只能运行脚本，不能唤醒当前 Codex/Claude/Cursor 会话并调用其原生 LLM 能力。Agent 原生能力由交互会话或平台托管，不是本地 Python 脚本可直接调用的函数。
- 影响: 首次 API 配置话术必须提醒用户，如果选择“没有 API”，默认不支持定时发送阅读报告；如检测不到可唤醒 Agent 平台，只能提供“定时提醒 + 手动打开 Agent”的方案。
- 后续注意: 如果未来适配 OpenClaw 等持久化 Agent 平台，需要先检测平台命令或环境变量，再执行 cron/list/status 或 dry-run 验证，不能只凭环境猜测就承诺自动定时总结。

- 日期: 2026-05-03
- 任务: 首次初始化询问顺序
- 结论: 首次使用时先检测是否是支持定时唤醒 Agent 的持久化平台，再询问用户是否有 API；只有“有 API”或“无 API 但已确认是持久化 Agent 平台”时，才继续询问定时发送时间。无 API且非持久化平台时，直接提示不支持定时发送，并将发送方式设为手动。
- 原因: 是否能定时发送取决于“脚本是否能调用模型 API”或“平台是否能唤醒 Agent”。如果先问发送时间，会让无 API 本地用户误以为可以无人值守定时总结。
- 影响: onboarding 话术必须按“平台能力检测 → API 配置 → 条件性询问发送时间 → 摘要篇幅”的顺序执行。
- 后续注意: 如果用户没有 API且不是持久化 Agent 平台，推荐配置 API；否则只能手动触发“处理今天收藏的文章并发送阅读汇总”。

- 日期: 2026-05-03
- 任务: 动态发送时间与日报日期参数
- 结论: 发送时间不能写死为 21:00 或 09:00；设置应使用 `deliverySchedule=same_day|next_day|manual` 加 `deliveryTime=HH:MM`。日报脚本支持 `--today`、`--yesterday`、`--date YYYY-MM-DD`，第二天发送阅读报告时应读取前一天收藏内容。
- 原因: 用户可能指定第二天 10:00 等任意合法时间；把时间编码进 `deliverySchedule` 会限制扩展并增加兼容成本。
- 影响: 旧配置 `same_day_21`、`next_day_09` 只作为兼容读取；新配置统一写 `same_day`、`next_day` 和动态 `deliveryTime`。
- 后续注意: 下一阶段实现定时任务安装器时，`same_day + HH:MM` 对应 `daily_summary.py --today`，`next_day + HH:MM` 对应 `daily_summary.py --yesterday`。

- 日期: 2026-05-03
- 任务: macOS 与持久化平台定时任务支持
- 结论: 本项目先支持 macOS `launchd` 安装器和 OpenClaw 这类持久化 Agent 平台的 cron 规则；Windows 暂不支持系统定时任务安装。
- 原因: macOS 是当前开发和测试环境，可以真实验证 `launchd`；OpenClaw 具备平台级唤醒 Agent 能力；Windows Task Scheduler 需要 Windows 环境做端到端验证，当前不能承诺。
- 影响: macOS 用户可运行 `python3 backend/install_scheduler.py` 和 `python3 backend/uninstall_scheduler.py`；Windows 用户只能手动运行日报脚本或等待后续 Task Scheduler 支持。
- 后续注意: OpenClaw 创建 cron 时必须指定 `--channel` 和 `--to`，不要用 `--channel last`；创建后必须 `openclaw cron run <jobId>` 验证真实投递。

- 日期: 2026-05-03
- 任务: macOS launchd 定时任务实测
- 结论: launchd 能按时触发任务，但如果项目位于 `~/Desktop` 等 macOS 受保护目录，Python 会报 `Operation not permitted`，无法读取 `daily_summary.py`。
- 原因: macOS TCC 隐私权限会限制后台 launchd 进程访问 Desktop/Documents/Downloads 等目录，即使用户当前终端可以访问。
- 影响: `install_scheduler.py` 必须检测受保护目录并拒绝安装；README 和 skill 必须提示用户把项目放到 `~/Projects/article-collector` 或 `~/.article-collector/app`。
- 后续注意: 如果用户坚持放在 Desktop，需要自行给相关进程完整磁盘访问权限，但开源默认流程不应依赖这个权限。

- 日期: 2026-05-03
- 任务: macOS launchd Python 与 PATH 实测
- 结论: launchd 定时任务必须使用当前 Python 解释器绝对路径，并显式写入当前 `PATH`。否则可能使用系统 Python，导致缺少 `bs4` 等依赖；也可能因默认 `PATH=/usr/bin:/bin:/usr/sbin:/sbin` 找不到 `lark-cli`。
- 原因: launchd 的运行环境和交互式终端不同，不会自动继承 shell 初始化文件、Homebrew 路径或当前 Python 环境。
- 影响: `install_scheduler.py` 使用 `sys.executable` 生成任务命令，并把当前 `PATH` 写入 plist 的 `EnvironmentVariables`。
- 后续注意: 如果用户换了 Python 环境或移动项目目录，需要重新运行 `python3 backend/install_scheduler.py` 生成新的 plist。

- 日期: 2026-05-03
- 任务: 阅读汇总前的处理状态补全规则
- 结论: 生成阅读汇总前，必须先检查指定日期所有文章的 `处理状态`。`完成` 直接使用；非 `完成` 先尝试处理原文链接，成功后写回飞书表格并标记 `完成`，失败则写回 `处理失败`，然后再生成飞书文档和 IM。
- 原因: 浏览器插件或之前的处理可能只保存链接、处理失败或留下待处理记录；如果直接拼接表格内容，阅读汇总会漏内容或显示空内容。
- 影响: `daily_summary.py` 使用 `complete_incomplete_articles()` 替代只重试失败文章的逻辑；定时 API 模式可以在汇总前自动补全非完成文章。
- 后续注意: 无 API + 非持久化本地环境仍不能由脚本调用 Agent 原生能力自动补全；只能手动触发 Agent 或使用持久化 Agent 平台。

- 日期: 2026-05-03
- 任务: 浏览器插件无 API 收藏状态修复
- 结论: 浏览器插件链路在没有可用模型 API key 时，必须把文章保存为 `处理状态=待处理`，而不是 `处理失败`。
- 原因: 新用户可能选择了无 API 模式，但配置尚未正确写入 `processingMode=link_only`，或后台服务读取到旧配置；这时误走 API 流程会把正常待处理文章标成失败。
- 影响: `auto_process.process()` 现在在 `processingMode=link_only` 或 `AI_API_KEY` 为空时，直接调用 `write_link_only_to_feishu()`，不抓取、不调用 AI、不写失败状态。
- 后续注意: 如果用户明确配置了 API 但 API 调用失败，仍应写 `处理失败`，不能改为待处理。

- 日期: 2026-05-03
- 任务: 飞书表格记录写回接口修复
- 结论: 更新单条飞书多维表格记录时使用 `lark-cli base +record-upsert --record-id <record_id>`，不要使用 `+record-batch-update`。
- 原因: 当前环境下 `+record-batch-update` 返回 `OpenAPIBatchUpdateRecords limited`；bot 身份尝试 batch update 又返回 403。`record-upsert --record-id` 已实测可以写回待处理记录。
- 影响: `daily_summary.update_record_fields()` 已改为 `record-upsert`；待处理文章可以补全后写回 `处理状态=完成`，失败链接可写回 `处理失败`。
- 后续注意: 如果后续要批量更新多条记录，应循环调用单条 upsert，除非确认目标环境的 batch update OpenAPI 已可用。
