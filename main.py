import discord
from discord.ext import commands
import os
import datetime
from dotenv import load_dotenv
from aiohttp import web

# --- NEW: Web Server Functions for Uptime Monitoring ---
async def handle_health_check(request):
    """Responds to health check pings to keep the service awake."""
    return web.Response(text="Bot is alive!")

async def web_server_start():
    """Starts a small web server to listen for uptime pings."""
    app = web.Application()
    app.router.add_get("/", handle_health_check) # Define a simple endpoint for pings

    runner = web.AppRunner(app)
    await runner.setup()

    # Render provides a PORT environment variable for Web Services.
    # We'll use 8080 as a fallback for local testing if PORT isn't set.
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# Load environment variables
load_dotenv()
TOKEN = os.environ.get('DISCORD_TOKEN')
BOT_OWNER_ID = os.environ.get('BOT_OWNER_ID') # Ensure this is set in your .env file

# Define your global emojis here. These will be accessible by all cogs via 'bot' object.
EMOJI_CROWN = "<:26985whitecrown:1392780685592231936>"
EMOJI_HEART = "<:32562pinkheart:1392780764835217408>"
EMOJI_SPARKLE = "<a:80524pinkstars:1392781611623514173>"
EMOJI_RIBBON = "<:22499bow:1392780501886177380>"
EMOJI_FLOWER = "<:CherryBlossom:1392784047234748417>"
EMOJI_STAR = "<a:Pinkstar:1392784692138217543>"
EMOJI_MANYBUTTERFLIES = "<a:65954pinkbutterflies:1392780618018066512>"
EMOJI_BUTTERFLY = "<a:95526butterflypink:1392781803093233765>"

# Set up intents for your bot (these are crucial for your bot's functionality)
intents = discord.Intents.default()
intents.members = True          # Required for fetching members, user info, kick/ban/mute
intents.message_content = True  # Required for reading messages (e.g., for automod, commands)
intents.presences = True        # Required for presence updates (e.g., user status/activities in userinfo)
intents.guilds = True           # Required for guild operations (e.g., serverinfo, getting guild members)

bot = commands.Bot(command_prefix='eli ', intents=intents)
bot.remove_command('help') # Remove the default help command, as you'll make your own

# --- GLOBAL VARIABLES / BOT ATTRIBUTES ---
# Store bot's start time for uptime calculation, directly as a bot attribute
bot.BOT_START_TIME_REF = datetime.datetime.now(datetime.timezone.utc)
# You can also store global emojis as bot attributes for easy access in cogs
bot.EMOJIS = {
    "CROWN": EMOJI_CROWN,
    "HEART": EMOJI_HEART,
    "SPARKLE": EMOJI_SPARKLE,
    "RIBBON": EMOJI_RIBBON,
    "FLOWER": EMOJI_FLOWER,
    "STAR": EMOJI_STAR,
    "MANYBUTTERFLIES": EMOJI_MANYBUTTERFLIES,
    "BUTTERFLY": EMOJI_BUTTERFLY,
}


# --- Bot Events ---
@bot.event
async def on_ready():
    """Event that fires when the bot successfully connects to Discord."""
    print(f'{bot.user} has connected to Discord!')
    
    # Load all Cogs when the bot is ready
    await load_extensions()
    
    # Sync slash commands globally
    try:
        # For immediate testing, syncing to a specific guild ID is faster:
        # await bot.tree.sync(guild=discord.Object(id=YOUR_TEST_GUILD_ID))
        await bot.tree.sync()
        print("Slash commands synced!")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

    # Set bot's activity/presence (optional)
    # await bot.change_presence(activity=discord.Game(name="with Python"))
    bot.loop.create_task(web_server_start()) # <-- ADD THIS LINE
    print("Bot is fully ready and web server is running!")


async def load_extensions():
    """This function dynamically loads all cog files from the 'cogs' directory."""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}') # Load as 'cogs.filename'
                print(f"Loaded extension: {filename}")
            except commands.ExtensionAlreadyLoaded:
                print(f"Extension already loaded: {filename}")
            except commands.ExtensionFailed as e:
                print(f"Failed to load extension {filename}: {e.original}")
            except Exception as e:
                print(f"An error occurred loading extension {filename}: {e}")
    print("All extensions loaded!")


# --- Help Command (This will display your commands) ---
@bot.command(name='cmds', aliases=['help', 'commands'])
async def list_commands(ctx):
    """Displays a list of all available commands."""

    embed = discord.Embed(
        title=f"{bot.EMOJIS['HEART']} Eli Bot Commands! {bot.EMOJIS['HEART']}",
        description=f"{bot.EMOJIS['SPARKLE']} Here's a list of commands you can use with Eli Bot. "
                    f"My prefix is `{bot.command_prefix}`. {bot.EMOJIS['SPARKLE']}",
        color=0xFFB6C1 # pinkish
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(
        text=f"Requested by {ctx.author.name}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    general_cmds = []
    moderation_cmds = []
    # Add other categories here if you make more cogs (e.g., fun_cmds = [])

    # Iterate through all commands known by the bot (including those in loaded cogs)
    for command in bot.commands:
        if command.hidden: # Skip hidden commands if you have any
            continue

        formatted_cmd_name = f"**`{bot.command_prefix}{command.name}`**"

        # Categorize based on which cog they belong to
        if command.cog_name == 'General':
            general_cmds.append(formatted_cmd_name)
        elif command.cog_name == 'Moderation':
            moderation_cmds.append(formatted_cmd_name)
        # Add 'elif command.cog_name == 'YourOtherCogName':' for other categories
        else: # For any commands not explicitly categorized (like badgecheck if it stays here)
            general_cmds.append(formatted_cmd_name)


    if general_cmds:
        embed.add_field(
            name=f"{bot.EMOJIS['FLOWER']} General Commands {bot.EMOJIS['FLOWER']}",
            value="\n".join(sorted(general_cmds)), # Sort for readability
            inline=False
        )

    if moderation_cmds:
        embed.add_field(
            name=f"{bot.EMOJIS['CROWN']} Moderation Commands {bot.EMOJIS['CROWN']}",
            value="\n".join(sorted(moderation_cmds)), # Sort for readability
            inline=False
        )

    # Add fields for other command categories here if you create them
    # if fun_cmds:
    #     embed.add_field(
    #         name=f"🎮 Fun Commands 🎮",
    #         value="\n".join(sorted(fun_cmds)),
    #         inline=False
    #     )

    await ctx.send(embed=embed)


# --- Slash Command for Active Developer Badge (Keep this here for now, or move to a general cog later) ---
@bot.tree.command(name="badgecheck", description="Checks eligibility for Active Developer Badge")
async def badgecheck(interaction: discord.Interaction):
    await interaction.response.send_message("Running a slash command for the Active Developer Badge!")


# Run the bot with your token
bot.run(TOKEN)