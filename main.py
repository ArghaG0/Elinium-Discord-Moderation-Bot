import discord
from discord.ext import commands
import os
import datetime
import logging
import asyncpg
from config.config import ConfigError, load_config
from utils import init_db

log = logging.getLogger(__name__)
# Define your global emojis here. These will be accessible by all cogs via 'bot' object.
EMOJI_CROWN = "<:26985whitecrown:1392780685592231936>"
EMOJI_HEART = "<:32562pinkheart:1392780764835217408>"
EMOJI_SPARKLE = "<a:80524pinkstars:1392781611623514173>"
EMOJI_RIBBON = "<:22499bow:1392780501886177380>"
EMOJI_FLOWER = "<:CherryBlossom:1392784047234748417>"
EMOJI_STAR = "<a:Pinkstar:1392784692138217543>"
EMOJI_MANYBUTTERFLIES = "<a:65954pinkbutterflies:1392780618018066512>"
EMOJI_BUTTERFLY = "<a:95526butterflypink:1392781803093233765>"
EMOJI_ERROR = "\u274c"

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
    "ERROR": EMOJI_ERROR,
}


# --- Bot Events ---
@bot.event
async def setup_hook():
    """Event that fires before the bot connects to Discord."""
    # Initialize the database pool
    try:
        bot.db_pool = await asyncpg.create_pool(
            bot.config.database_url,
            min_size=1,
            max_size=10,
            command_timeout=60,
            # Serverless dbs can scale to zero, so set a longer connection timeout
            timeout=60.0 
        )
        log.info("Database connection pool established.")
        # Initialize schema
        await init_db(bot.db_pool)
        log.info("Database schema initialized.")
    except Exception:
        log.exception("Failed to initialize database.")
        # Exit if database connection fails as it's critical
        import sys
        sys.exit(1)

@bot.event
async def on_ready():
    """Event that fires when the bot successfully connects to Discord."""
    log.info("%s has connected to Discord!", bot.user)
    
    # Load all Cogs when the bot is ready
    await load_extensions()
    
    # Sync slash commands globally
    try:
        # For immediate testing, syncing to a specific guild ID is faster:
        # await bot.tree.sync(guild=discord.Object(id=YOUR_TEST_GUILD_ID))
        await bot.tree.sync()
        log.info("Slash commands synced!")
    except Exception:
        log.exception("Failed to sync slash commands.")

    # Set bot's activity/presence (optional)
    # await bot.change_presence(activity=discord.Game(name="with Python"))


async def load_extensions():
    """This function dynamically loads all cog files from the 'cogs' directory."""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}') # Load as 'cogs.filename'
                log.info("Loaded extension: %s", filename)
            except commands.ExtensionAlreadyLoaded:
                log.info("Extension already loaded: %s", filename)
            except commands.ExtensionFailed:
                log.exception("Failed to load extension: %s", filename)
            except Exception:
                log.exception("An error occurred loading extension: %s", filename)
    log.info("Extension loading finished.")


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


def setup_logging(level: int = logging.INFO) -> None:
    """Configure console logs once for the application and discord.py."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    """Validate configuration before opening any Discord or database connection."""
    setup_logging()
    try:
        config = load_config()
    except ConfigError as error:
        log.error("Configuration error: %s", error)
        raise SystemExit(1) from None
    logging.getLogger().setLevel(config.log_level)
    bot.config = config
    bot.run(config.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
