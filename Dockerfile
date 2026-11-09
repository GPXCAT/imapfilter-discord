FROM python:3.12-slim

WORKDIR /app

# 安裝 imapfilter 工具與依賴套件
RUN apt-get update && apt-get install -y imapfilter && rm -rf /var/lib/apt/lists/*

# 安裝 discord.py
RUN pip install --no-cache-dir discord.py

# 複製程式碼
COPY bot.py .

CMD ["python3", "bot.py"]