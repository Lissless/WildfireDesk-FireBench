import discord
from discord.ext import commands
import asyncio
import sys
import io
from wildfire_desk import setup_sage, prompt_sage
TOKEN = "MTQ4NjEwNDk1MjQyMTA4OTQyMw.G_xckB.K9ez86UEetKqYkKzODiYv5NqFirbYP336gZeCY"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is on!")
    if not setup_sage():
        print("Init failed.")
        sys.exit(1)
async def send_long_message(channel, base_msg, answer, sources=None):
    SHORT_LIMIT = 1800
    SPLIT_LIMIT = 4000

    # 拼接完整内容（用于判断）
    full_text = answer
    if sources:
        full_text += "\n\n📚 rag_context:\n" + sources
    else:
        full_text += "\n\nP.S. No rag_context used"

    length = len(full_text)

    # ✅ 1️⃣ 短消息
    if length <= SHORT_LIMIT:
        await base_msg.edit(content=full_text)

    # ✅ 2️⃣ 中等长度 → 分段发送
    elif length <= SPLIT_LIMIT:
        chunks = []

        # 按 1800 切块（避免触发 2000 限制）
        for i in range(0, len(full_text), SHORT_LIMIT):
            chunks.append(full_text[i:i+SHORT_LIMIT])

        await base_msg.edit(content=chunks[0])

        for chunk in chunks[1:]:
            await channel.send(chunk)

    # ✅ 3️⃣ 超长 → 发文件
    else:
        file = discord.File(
            fp=io.StringIO(full_text),
            filename="response.txt"
        )

        await base_msg.edit(content="📄 Response too long, sent as file:")
        await channel.send(file=file)
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command `{ctx.message.content}` does not exist.")
        return

    print(f"Error: {error}")
    await ctx.send("⚠️ try again.")
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not message.content.startswith("! "):
        return
    if message.attachments:
        attachment = message.attachments[0]  # 先只处理第一个文件

        filename = attachment.filename.lower()

        # ❌ 不是 PDF
        if not filename.endswith(".pdf"):
            await message.channel.send("❌ Only PDF files are supported.")
            return

        # ✅ 是 PDF
        await message.channel.send("📄 PDF received, processing...")

        # 下载文件到内存
        file_bytes = await attachment.read()

        # 👉 这里可以接你的后端
        # 示例：调用处理函数
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_pdf, file_bytes)

        await message.channel.send(f"✅ Done:\n{result}")

        return  # ⚠️ 防止继续进入下面的文本逻辑
    user_input = message.content[2:] 

    msg = await message.channel.send("🤔 Sage is thinking...")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, prompt_sage, user_input)

    answer = result["result"]
    sources = result["rag_context"]
    
    reply = answer

    if sources:
        reply += "\n\n📚 **rag_context:**\n" + sources
    else:
        reply += "\n\nP.S. No rag_context used"
    await send_long_message(message.channel, msg, reply, sources)


bot.run(TOKEN)