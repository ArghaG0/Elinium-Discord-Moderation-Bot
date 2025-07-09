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

@bot.command(name='say')
async def say_command(ctx, *, message_to_say: str):
    """Makes the bot say something. Usage: eli say <your message>"""
    if message_to_say:
        await ctx.send(message_to_say)
    else:
        await ctx.send("What do you want me to say? Usage: `eli say <your message>`")

@bot.tree.command(name="badgecheck", description="Checks eligibility for Active Developer Badge")
async def badgecheck(interaction: discord.Interaction):
    await interaction.response.send_message("Running a slash command for the Active Developer Badge!")

# A crucial step for slash commands: sync them to Discord
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        # Sync commands globally or to specific guilds for testing
        # For immediate testing, syncing to a specific guild ID is faster
        # Replace YOUR_GUILD_ID with the ID of your test server
        # await bot.tree.sync(guild=discord.Object(id=YOUR_GUILD_ID)) # Uncomment for specific guild
        await bot.tree.sync() # Sync globally (can take up to an hour)
        print("Slash commands synced!")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

    # await bot.change_presence(activity=discord.Game(name="with Python"))

# Run the bot
bot.run(TOKEN)