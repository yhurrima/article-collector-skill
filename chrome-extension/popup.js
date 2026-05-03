const QUEUE_URL = "http://127.0.0.1:5679/queue";

document.addEventListener("DOMContentLoaded", async () => {
  const urlBox = document.getElementById("urlBox");
  const saveBtn = document.getElementById("saveBtn");
  const status = document.getElementById("status");

  // 获取当前页面 URL
  let currentUrl = "";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentUrl = tab.url || "";
    urlBox.textContent = currentUrl;
  } catch {
    urlBox.textContent = "无法获取当前页面";
    saveBtn.disabled = true;
    return;
  }

  // 启动时检测队列服务是否在线
  let serverOnline = false;
  try {
    const resp = await fetch(QUEUE_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    // 服务在线会返回 JSON（即使参数为空也会返回 400 而不是网络错误）
    serverOnline = true;
  } catch {
    // 服务未启动
  }

  if (!serverOnline) {
    status.className = "status error";
    status.style.display = "block";
    status.textContent = "队列服务未启动，请让 Agent 启动服务（说「启动文章收藏服务」）";
    saveBtn.disabled = true;
    return;
  }

  // 服务在线，绑定点击事件
  saveBtn.addEventListener("click", async () => {
    if (!currentUrl) return;

    saveBtn.disabled = true;
    saveBtn.textContent = "发送中...";
    status.style.display = "none";

    try {
      const resp = await fetch(QUEUE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: currentUrl }),
      });

      const data = await resp.json();

      if (data.ok) {
        status.className = "status success";
        status.textContent = "✓ 已发送！";
      } else {
        throw new Error(data.error || "发送失败");
      }
    } catch (err) {
      status.className = "status error";
      status.textContent = "✗ " + err.message;
    }

    status.style.display = "block";
    saveBtn.disabled = false;
    saveBtn.textContent = "收藏到飞书";
  });
});
