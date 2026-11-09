# Discord IMAPFilter Bot 🤖

一個透過 Discord 指令在 Ubuntu 主機上安全執行 `/usr/bin/imapfilter -v` 的自動化運維機器人（ChatOps），並採用 **Docker** 進行容器化部署，輕量且好維護。

---

## 🛠 專案架構與特色

* **指令觸發**：在 Discord 頻道輸入 `!imap` 即可觸發主機上的郵件過濾檢查。
* **安全隔離**：透過 Docker 運行，不污染主機系統環境，並支援環境變數（`.env`）安全管理 Token。
* **自動重啟**：設定 `restart: always`，重開機或容器崩潰時會自動恢復。

---

## 📂 專案檔案結構

專案目錄下應該包含以下四個檔案：

```text
├── bot.py             # Python 機器人核心程式碼
├── Dockerfile         # Docker 映像檔建置設定
├── docker-compose.yml # Docker 容器編排與服務設定
└── .env               # 存放 Discord Bot Token 的機敏設定檔（不上傳 Git）