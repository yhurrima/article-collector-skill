"""内容抓取 + AI 解析 (支持多种引擎)"""
import json
import requests
from bs4 import BeautifulSoup
from config import AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL


LENGTH_INSTRUCTIONS = {
    "brief": "简短篇幅：保持旧“主要内容”的长度，提炼 2-4 条核心要点，每条 20-40 字。",
    "medium": "中等篇幅：比简短篇幅更完整，保留更多上下文、关键细节和重要转折，建议 4-6 条，每条 60-100 字。",
    "detailed": "详细篇幅：建议 4-6 条，每条 300-400 字。每条都要包含可追溯的原始资料细节，例如关键人物、公司、事件、时间、数据、引用观点、因果关系、上下文背景和文章中的具体信息。不要泛泛概括，不要只写结论；要写成可直接放入阅读笔记的详细资料卡片。如果文章主体内容非常短，不足以支撑 4-6 条、每条 300-400 字，不要编造，自动回退为中等篇幅要求。",
}


EXTRACT_PROMPT_TEMPLATE = """请从以下文章内容中提取结构化信息。

文章标题: {title}
文章链接: {url}

文章内容:
{text}

请用 JSON 格式返回，包含以下字段:
{{
  "title": "文章标题（如果原文标题不好，可以优化）",
  "author": "作者（未知则为空字符串）",
  "source": "来源平台/网站名",
  "publish_date": "发布日期 YYYY-MM-DD 格式（未知则为空字符串）",
  "category": "分类，只能是以下之一: 技术/产品/设计/商业/AI/其他",
  "summary": "一句话摘要（30字以内，精炼概括核心观点）",
  "main_points": ["主要内容点1", "主要内容点2", "主要内容点3"],
  "tags": ["标签1", "标签2"],
  "quality_score": 评分1-5，基于内容深度和实用性
}}

要求：
- 不要强行把所有文章拆成背景、观点、论据；只按文章本身适合的结构总结。
- 只总结文章主体内容。不要把作者简介、网站导航、订阅方式、相关阅读、广告、版权信息、标签列表、页面推荐内容当作文章内容。
- main_points 是最终写入飞书表格“主要内容”字段的内容。
- {length_instruction}

只返回 JSON，不要其他内容。"""


ARTICLE_SELECTORS = [
    "article",
    "main article",
    "main",
    '[data-module="ArticleBody"]',
    '[data-testid="article-body"]',
    '[class*="article-body"]',
    '[class*="post-content"]',
    '[class*="entry-content"]',
]


NOISE_SELECTORS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "iframe",
    "form",
    "[role='navigation']",
    "[role='complementary']",
    "[aria-label*='breadcrumb']",
    "[aria-label*='share']",
    "[class*='author-bio']",
    "[class*='bio']",
    "[class*='newsletter']",
    "[class*='subscribe']",
    "[class*='related']",
    "[class*='recommend']",
    "[class*='advert']",
    "[class*='promo']",
    "[class*='share']",
    "[class*='social']",
    "[class*='comment']",
    "[id*='newsletter']",
    "[id*='subscribe']",
    "[id*='related']",
    "[id*='comment']",
]


def format_points(points):
    return "\n".join(f"{i+1}. {point}" for i, point in enumerate(points or []))


def normalize_extracted_article(article):
    """Normalize model output while keeping a single main_points field."""
    article = dict(article)
    if isinstance(article.get("main_points"), str):
        article["main_points"] = [p for p in article["main_points"].split("\n") if p.strip()]
    article.setdefault("main_points", [])
    return article


def build_extract_prompt(title, url, text, summary_length="brief"):
    length_instruction = LENGTH_INSTRUCTIONS.get(summary_length, LENGTH_INSTRUCTIONS["brief"])
    return EXTRACT_PROMPT_TEMPLATE.format(
        title=title,
        url=url,
        text=text,
        length_instruction=length_instruction,
    )


def clean_article_text_from_html(html):
    """Extract likely article body text and remove common page chrome."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    for selector in NOISE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    body = None
    for selector in ARTICLE_SELECTORS:
        body = soup.select_one(selector)
        if body:
            break
    if body is None:
        body = soup.body or soup

    text = body.get_text(separator="\n", strip=True)
    if len(text) > 15000:
        text = text[:15000] + "\n...(内容截断)"

    return {"title": title, "text": text}


def fetch_article(url):
    """抓取网页内容，返回纯文本"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    article = clean_article_text_from_html(resp.text)
    article["url"] = url
    return article


def _call_anthropic(prompt):
    from anthropic import Anthropic
    client = Anthropic(api_key=AI_API_KEY, base_url=AI_BASE_URL or None)
    response = client.messages.create(
        model=AI_MODEL or "claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}]
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    raise Exception("No text block in response")


def _call_openai_compatible(prompt):
    url = (AI_BASE_URL or "https://api.openai.com/v1") + "/chat/completions"
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": AI_MODEL or "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_local(prompt):
    url = (AI_BASE_URL or "http://localhost:11434") + "/api/chat"
    data = {
        "model": AI_MODEL or "llama3",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    resp = requests.post(url, json=data, timeout=60)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_ai(prompt):
    engines = {
        "anthropic": _call_anthropic,
        "openai": _call_openai_compatible,
        "local": _call_local,
    }
    engine = engines.get(AI_PROVIDER, _call_openai_compatible)
    return engine(prompt)


def extract_with_ai(article_data, summary_length="brief"):
    """用 AI 从文章内容中提取结构化信息"""
    prompt = build_extract_prompt(article_data["title"], article_data["url"], article_data["text"], summary_length)
    result_text = _call_ai(prompt).strip()
    if result_text.startswith("```"):
        result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
    return normalize_extracted_article(json.loads(result_text))


def process_url(url, summary_length="brief"):
    """完整流程: 抓取 → 解析 → 返回结构化数据"""
    article = fetch_article(url)
    structured = extract_with_ai(article, summary_length=summary_length)
    structured["url"] = url
    return structured
