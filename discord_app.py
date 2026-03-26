import discord
from discord.ext import commands
import asyncio
import sys
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


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not message.content.startswith("!ask"):
        return

    user_input = message.content[len("!ask "):]

    msg = await message.channel.send("🤔Sage is thinking...")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, prompt_sage, user_input)

    answer = result["result"]
    sources = result["rag_context"]

    reply = answer

    if sources:
        reply += "\n\n📚 **rag_context:**\n" + sources
    else:
        reply += "\n\nP.S. No rag_context used"

    await msg.edit(content=reply)

    await bot.process_commands(message)


bot.run(TOKEN)