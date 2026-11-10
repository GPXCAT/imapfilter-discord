import asyncio
import io
import os
from datetime import datetime

import discord
from discord.ext import commands, tasks

from imap_summary import format_summary, has_problem

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
# 共用：執行 imapfilter（非同步，不會卡住機器人）
# =========================================================
IMAPFILTER_CMD = ['/usr/bin/imapfilter', '-v']


async def run_imapfilter(timeout):
    proc = await asyncio.create_subprocess_exec(
        *IMAPFILTER_CMD,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # 合併輸出，保留原本順序
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return out.decode('utf-8', errors='replace'), proc.returncode


def log_file(raw):
    name = f"imapfilter-{datetime.now():%Y%m%d-%H%M%S}.log"
    return discord.File(io.BytesIO(raw.encode('utf-8')), filename=name)


# =========================================================
# 定時任務：自動背景執行
# =========================================================
@tasks.loop(minutes=10)
async def scheduled_imapfilter():
    print("正在執行定時的 imapfilter 檢查...")

    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if not channel:
        print(f"警告：找不到 ID 為 {NOTIFICATION_CHANNEL_ID} 的頻道！")
        return

    try:
        raw, code = await run_imapfilter(timeout=60)
        summary = format_summary(raw, code, '🕒 定時自動執行報告')
        # 有問題時才附上完整紀錄，平常只送摘要
        if has_problem(raw, code):
            await channel.send(summary, file=log_file(raw))
        else:
            await channel.send(summary)
    except asyncio.TimeoutError:
        await channel.send("⚠️ **定時執行逾時**：imapfilter 超過 60 秒未回應。")
    except Exception as e:
        print(f"定時執行發生錯誤：{e}")

@scheduled_imapfilter.before_loop
async def before_scheduled_imapfilter():
    await bot.wait_until_ready()


# =========================================================
# 手動觸發指令：在 Discord 輸入 !imap
# =========================================================
@bot.command(name='imap')
async def imap_command(ctx):
    await ctx.send("正在手動執行 `/usr/bin/imapfilter -v`...")

    try:
        raw, code = await run_imapfilter(timeout=30)
        summary = format_summary(raw, code, '手動執行結果')
        await ctx.send(summary, file=log_file(raw))  # 手動執行一律附完整紀錄
    except asyncio.TimeoutError:
        await ctx.send("執行逾時：imapfilter 執行超過 30 秒未回應。")
    except Exception as e:
        await ctx.send(f"執行發生錯誤：`{e}`")


# 取得 Token 並啟動機器人
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("錯誤：找不到 DISCORD_TOKEN 環境變數，請確認是否有正確設定！")

bot.run(TOKEN)