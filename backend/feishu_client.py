"""飞书 API 客户端 - 通过 lark-cli 封装所有飞书操作"""
import subprocess
import json


def _run_cli(*args):
    """执行 lark-cli 命令并返回 JSON 结果"""
    cmd = ["lark-cli"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"lark-cli error: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def add_record(base_token, table_id, fields):
    """写入一条记录到多维表格"""
    field_names = list(fields.keys())
    row = [fields[k] for k in field_names]
    data = json.dumps({"fields": field_names, "rows": [row]})
    return _run_cli("base", "+record-batch-create",
                     "--base-token", base_token,
                     "--table-id", table_id,
                     "--json", data)


def batch_add_records(base_token, table_id, records):
    """批量写入记录"""
    if not records:
        return {}
    field_names = list(records[0].keys())
    rows = [[r.get(k, "") for k in field_names] for r in records]
    data = json.dumps({"fields": field_names, "rows": rows})
    return _run_cli("base", "+record-batch-create",
                     "--base-token", base_token,
                     "--table-id", table_id,
                     "--json", data)


def list_records(base_token, table_id, limit=100):
    """列出多维表格记录"""
    return _run_cli("base", "+record-list",
                     "--base-token", base_token,
                     "--table-id", table_id,
                     "--limit", str(limit))


def search_records(base_token, table_id, keyword=None, search_fields=None):
    """搜索多维表格记录"""
    data = {}
    if keyword:
        data["keyword"] = keyword
    if search_fields:
        data["search_fields"] = search_fields
    args = ["base", "+record-search",
            "--base-token", base_token,
            "--table-id", table_id]
    if data:
        args += ["--json", json.dumps(data)]
    return _run_cli(*args)


def create_doc(title, markdown):
    """创建飞书文档"""
    return _run_cli("docs", "+create",
                     "--title", title,
                     "--markdown", markdown)


def send_text(chat_id, text):
    """以机器人身份发送文本消息"""
    return _run_cli("im", "+messages-send",
                     "--as", "bot",
                     "--chat-id", chat_id,
                     "--text", text)


def send_markdown(chat_id, text):
    """以机器人身份发送 Markdown 消息"""
    return _run_cli("im", "+messages-send",
                     "--as", "bot",
                     "--chat-id", chat_id,
                     "--markdown", text)
