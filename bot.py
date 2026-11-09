import os
import subprocess
import discord
from discord.ext import commands

# 設定 Discord 機器人的權限
intents = discord.Intents.default()
intents.message_content = True  # 必須開啟此權限以讀取訊息內容

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'機器人已成功登入：{bot.user}')

@bot.command(name='imap')
async def run_imapfilter(ctx):
    # 可以在這裡加入頻道限制（選填）：
    # if ctx.channel.id != 你的頻道ID: return

    await ctx.send("正在執行 `/usr/bin/imapfilter -v`，請稍候...")

    try:
        # 使用 subprocess 在主機背景執行指令
        # 為了安全與相容性，這裡直接呼叫絕對路徑
        result = subprocess.run(
            ['/usr/bin/imapfilter', '-v'],
            capture_output=True,
            text=True,
            timeout=30  # 設定 30 秒逾時，避免無限卡住
        )

        # 結合標準輸出與錯誤訊息
        output = result.stdout + result.stderr

        # 如果沒有任何輸出，給個提示
        if not output.strip():
            output = "指令執行完畢，沒有任何輸出訊息。"

        # Discord 單則訊息上限為 2000 字，做簡單的字數截斷保護
        if len(output) > 1900:
            output = output[:1900] + "\n...(輸出過長，已自動截斷)..."

        # 以 Discord 程式碼區塊語法回傳執行結果
        await ctx.send(f"```\n{output}\n```")

    except subprocess.TimeoutExpired:
        await ctx.send("執行逾時：imapfilter 執行超過 30 秒未回應。")
    except Exception as e:
        await ctx.send(f"執行發生錯誤：`{str(e)}`")

# 從系統環境變數中讀取 Token（配合 Docker 的 .env 設定）
TOKEN = os.getenv('DISCORD_TOKEN')

if not TOKEN:
    raise ValueError("錯誤：找不到 DISCORD_TOKEN 環境變數，請確認是否有正確設定！")

# 啟動機器人
bot.run(TOKEN)