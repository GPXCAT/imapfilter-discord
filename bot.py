import os
import subprocess
import discord
from discord.ext import commands, tasks

# 設定 Discord 機器人的權限
intents = discord.Intents.default()
intents.message_content = True  # 必須開啟此權限以讀取訊息內容

bot = commands.Bot(command_prefix='!', intents=intents)

# ---------------------------------------------------------
# 讀取環境變數設定
# ---------------------------------------------------------
# 1. 接收定時通知的頻道 ID (若未填寫則預設為 0)
try:
    NOTIFICATION_CHANNEL_ID = int(os.getenv('NOTIFICATION_CHANNEL_ID', '0'))
except ValueError:
    NOTIFICATION_CHANNEL_ID = 0

# 2. 定時執行間隔（單位：分鐘），預設為 10 分鐘
try:
    INTERVAL_MINUTES = int(os.getenv('INTERVAL_MINUTES', '10'))
except ValueError:
    INTERVAL_MINUTES = 10

# 3. 定時任務開關 (true 代表啟用定時通知，false 代表關閉)
ENABLE_SCHEDULED = os.getenv('ENABLE_SCHEDULED', 'false').lower() == 'true'


@bot.event
async def on_ready():
    print(f'機器人已成功登入：{bot.user}')

    # 檢查是否要啟動定時任務
    if ENABLE_SCHEDULED and NOTIFICATION_CHANNEL_ID != 0:
        scheduled_imapfilter.change_interval(minutes=INTERVAL_MINUTES)
        if not scheduled_imapfilter.is_running():
            scheduled_imapfilter.start()
        print(f'✅ 定時任務已啟動：每 {INTERVAL_MINUTES} 分鐘執行一次，目標頻道 ID: {NOTIFICATION_CHANNEL_ID}')
    else:
        print('ℹ️ 定時任務未啟用（可能是 ENABLE_SCHEDULED 設為 false，或未正確設定 NOTIFICATION_CHANNEL_ID）')


# =========================================================
# 定時任務：自動背景執行
# =========================================================
@tasks.loop(minutes=10)
async def scheduled_imapfilter():
    print("正在執行定時的 imapfilter 檢查...")

    try:
        # 在主機背景執行指令
        result = subprocess.run(
            ['/usr/bin/imapfilter', '-v'],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr

        if not output.strip():
            output = "執行完畢，無輸出訊息。"

        # 限制字數防止超過 Discord 2000 字極限
        if len(output) > 1900:
            output = output[:1900] + "\n...(輸出過長，已自動截斷)..."

        # 尋找指定頻道並發送報告
        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if channel:
            await channel.send(f"🕒 **【定時自動執行報告】** `/usr/bin/imapfilter -v`\n```\n{output}\n```")
        else:
            print(f"警告：找不到 ID 為 {NOTIFICATION_CHANNEL_ID} 的頻道！")

    except Exception as e:
        print(f"定時執行發生錯誤：{str(e)}")

@scheduled_imapfilter.before_loop
async def before_scheduled_imapfilter():
    await bot.wait_until_ready()


# =========================================================
# 手動觸發指令：在 Discord 輸入 !imap
# =========================================================
@bot.command(name='imap')
async def run_imapfilter(ctx):
    await ctx.send("正在手動執行 `/usr/bin/imapfilter -v`...")

    try:
        result = subprocess.run(
            ['/usr/bin/imapfilter', '-v'],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout + result.stderr
        if not output.strip():
            output = "指令執行完畢，沒有任何輸出訊息。"

        if len(output) > 1900:
            output = output[:1900] + "\n...(輸出過長，已自動截斷)..."

        await ctx.send(f"```\n{output}\n```")

    except subprocess.TimeoutExpired:
        await ctx.send("執行逾時：imapfilter 執行超過 30 秒未回應。")
    except Exception as e:
        await ctx.send(f"執行發生錯誤：`{str(e)}`")


# 取得 Token 並啟動機器人
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("錯誤：找不到 DISCORD_TOKEN 環境變數，請確認是否有正確設定！")

bot.run(TOKEN)