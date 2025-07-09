import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define intents (important for modern Discord bots)
intents = discord.Intents.default()
intents.message_content = True # Enable message content intent if your bot reads messages
intents.members = True # Enable if your bot needs member info

# Initialize the bot with a command prefix and intents
bot = commands.Bot(command_prefix='eli ', intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    print(f'{bot.user} has connected to Discord!')
    # You can set the bot's status here
    # await bot.change_presence(activity=discord.Game(name="with Python"))

@bot.event
async def on_message(message):
    """Called every time a message is sent in any channel the bot can see."""
    if message.author == bot.user:
        return # Don't let the bot respond to its own messages

    if message.content.lower() == 'hello':
        await message.channel.send(f'Hello, {message.author.mention}!')

    # Process commands defined with @bot.command
    await bot.process_commands(message)

@bot.command(name='ping')
async def ping(ctx):
    """Responds with 'Pong!' and the bot's latency."""
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')

@bot.command(name='info')
async def info(ctx):
    """Gives information about the server."""
    await ctx.send(f'This server is named: {ctx.guild.name}\nIt has {len(ctx.guild.members)} members.')

# Run the bot
bot.run(TOKEN)