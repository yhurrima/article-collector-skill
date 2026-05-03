document.addEventListener("DOMContentLoaded", async () => {
  const urlBox = document.getElementById("urlBox");
  const saveBtn = document.getElementById("saveBtn");
  const status = document.getElementById("status");

  let currentUrl = "";
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentUrl = tab.url || "";
    urlBox.textContent = currentUrl;
  } catch {
    urlBox.textContent = "无法获取当前页面";
    saveBtn.disabled = true;
  }

  saveBtn.addEventListener("click", async () => {
    if (!currentUrl) return;

    saveBtn.disabled = true;
    saveBtn.textContent = "发送中...";
    status.style.display = "none";

    try {
      const resp = await fetch("http://127.0.0.1:5679/queue", {
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
