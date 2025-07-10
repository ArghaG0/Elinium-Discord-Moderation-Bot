import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import asyncio

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- Automod Blacklists ---
BAD_WORDS = [
    "motherfucker",
    "bitch",
    "dick",
    "slut",
    "mofo",
    "bitchass",
    "dickhead",
    "motherchod",
    "bkl",
    "vagina",
    "nigga",
    "nigger",
    "bokachoda",
    "behenchod",
    "chut",
    "chutiya",
    # Add more words (in lowercase) that you want to block
]

BLACKLISTED_LINKS = [
    "discord.gg",
    "instagram.com",
    "youtu.be",
    # Add more domain names or specific URLs (in lowercase) that you want to block
]
# --- END Automod Blacklists ---

# --- NEW: Helper function to parse duration strings (e.g., "5s", "10m", "1h", "3d") ---
def parse_duration(duration_str: str) -> datetime.timedelta:
    """Parses a duration string into a datetime.timedelta object."""
    seconds = 0
    duration_str = duration_str.lower() # Make it case-insensitive for units

    try:
        if duration_str.endswith('s'):
            seconds = int(duration_str[:-1])
        elif duration_str.endswith('m'):
            seconds = int(duration_str[:-1]) * 60
        elif duration_str.endswith('h'):
            seconds = int(duration_str[:-1]) * 3600
        elif duration_str.endswith('d'):
            seconds = int(duration_str[:-1]) * 86400
        else:
            raise ValueError("Invalid duration format. Use 'Xs', 'Xm', 'Xh', or 'Xd'.")
    except ValueError:
        raise ValueError("Invalid duration value. Please provide a number followed by s/m/h/d.")

    # Discord timeouts max out at 28 days (4 weeks)
    max_seconds = 28 * 24 * 3600
    if seconds > max_seconds:
        raise ValueError("Timeout duration cannot exceed 28 days (4 weeks).")
    if seconds <= 0:
        raise ValueError("Duration must be positive.")

    return datetime.timedelta(seconds=seconds)
# --- END Helper function ---   

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
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return
    
    # --- Automoderation Logic ---
    message_content_lower = message.content.lower()

    # Check for bad words
    for word in BAD_WORDS:
        if word in message_content_lower:
            try:
                await message.delete()
                # You can send a public warning or DM the user
                await message.channel.send(f'{message.author.mention}, that word is not allowed here!', delete_after=5)
                print(f"Deleted message from {message.author} containing forbidden word: '{word}' in '{message.content}'")
            except discord.Forbidden:
                print(f"ERROR: Bot does not have 'Manage Messages' permission to delete messages in {message.channel.name}")
                await message.channel.send("I need 'Manage Messages' permission to enforce word filters!", delete_after=10)
            return # Stop processing if a bad word is found and handled

    # Check for blacklisted links
    for link in BLACKLISTED_LINKS:
        if link in message_content_lower:
            try:
                await message.delete()
                await message.channel.send(f'{message.author.mention}, that link is not allowed here!', delete_after=5)
                print(f"Deleted message from {message.author} containing blacklisted link: '{link}' in '{message.content}'")
            except discord.Forbidden:
                print(f"ERROR: Bot does not have 'Manage Messages' permission to delete messages in {message.channel.name}")
                await message.channel.send("I need 'Manage Messages' permission to enforce link filters!", delete_after=10)
            return # Stop processing if a blacklisted link is found and handled
    # --- END Automoderation Logic ---

    # Check for direct 'hello'
    if message.content.lower() == 'hello':
        await message.channel.send(f'Hello, {message.author.mention}!')
        # Important: if the bot responds to 'hello', we might not want it to process commands
        # so adding 'return' here is an option if 'hello' should be exclusive.
        # For now, let's allow it to pass through to process_commands as well.

    # --- NEW: Check for exact 'eli' mention ---
    # We check if the message content, converted to lowercase, is exactly 'eli'
    if message.content.lower() == 'eli':
        await message.channel.send(f'Hello {message.author.mention}, how may I help you?')
        # If we respond here, we might want to prevent it from also trying to
        # process this as a command (which it wouldn't anyway if it's just 'eli' and your prefix is 'eli ').
        # Adding a 'return' here would stop further processing for just 'eli'.
        # Let's add 'return' for clear behavior.
        return # Stop processing if we responded to 'eli'

    # Process commands (like 'eli ping', 'eli info', etc.)
    await bot.process_commands(message)

# --- ping Command ---

@bot.command(name='ping')
async def ping(ctx):
    """Responds with 'Pong!' and the bot's latency."""
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')

# --- Detailed Server Info Command with Embed ---
@bot.command(name='info')
async def info(ctx):
    """Shows detailed information about the server."""
    guild = ctx.guild # Get the guild (server) object

    # Count members
    total_members = guild.member_count
    human_members = len([member for member in guild.members if not member.bot])
    bot_members = len([member for member in guild.members if member.bot])

    # Count channels
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    category_channels = len(guild.categories)

    # Creation date formatting
    created_at = guild.created_at.strftime("%A, %B %d, %Y at %H:%M:%S UTC")

    # Boost information
    boost_level = guild.premium_tier
    boost_count = guild.premium_subscription_count

    # Create the embed
    embed = discord.Embed(
        title=f"Information for {guild.name}",
        description=f"Welcome to {guild.name}!",
        color=0xD9A299 # Using the D9A299 from your palette
    )

    embed.set_thumbnail(url=guild.icon.url if guild.icon else None) # Set server icon if available
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Created On", value=created_at, inline=False) # False makes it take a full row

    embed.add_field(name="Members", value=f"Total: {total_members}\nHumans: {human_members}\nBots: {bot_members}", inline=True)
    embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {category_channels}", inline=True)

    embed.add_field(name="Boost Level", value=f"Tier {boost_level} ({boost_count} boosts)", inline=False)

    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None) # Set bot's name and icon

    await ctx.send(embed=embed)

# --- say Command ---
@bot.command(name='say')
async def say_command(ctx, *, message_to_say: str = None):
    """Makes the bot say something. Usage: eli say <your message> OR eli say (then follow the prompt)"""

    if message_to_say:
        # Normal way: User provided the message directly in the command
        #try:
        #    await ctx.message.delete() # Optional: delete the user's command message
       # except discord.Forbidden:
         #   print("Bot does not have permissions to delete messages for the 'say' command.")
        await ctx.send(message_to_say)
    else:
        # New way: User just typed 'eli say', so prompt them
        await ctx.send("What do you want me to say?")

        def check(m):
            # This 'check' function ensures we only listen for a message from:
            # 1. The same user who invoked the command (`ctx.author`).
            # 2. In the same channel where the command was invoked (`ctx.channel`).
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            # Wait for the next message that passes the 'check' function
            # and timeout after 60 seconds if no message is received.
            response_message = await bot.wait_for('message', check=check, timeout=60.0)

            # Once a valid message is received, make the bot say its content
            await ctx.send(response_message.content)

            # Optional: Delete the user's response message to keep the chat clean
           # try:
           #     await response_message.delete()
           # except discord.Forbidden:
           #     print("Bot does not have permissions to delete response messages for 'say' command.")

        except asyncio.TimeoutError:
            # If the user doesn't respond within 60 seconds
            await ctx.send("You took too long to tell me what to say! Please try `eli say <your message>` or `eli say` again.", delete_after=10)
        except Exception as e:
            # Catch any other unexpected errors during the wait_for process
            await ctx.send(f"An unexpected error occurred: {e}. Please try again.")

# --- Purge Command ---
@bot.command(name='purge')
@commands.has_permissions(manage_messages=True) # Requires bot and user to have manage_messages permission
async def purge(ctx, amount: int):
    """Deletes a specified number of messages. Usage: eli purge <amount>
    Requires 'Manage Messages' permission."""
    if amount <= 0:
        await ctx.send("Please provide a number greater than 0.")
        return

    # Delete the command message itself
    await ctx.message.delete()

    try:
        # Fetch and delete messages
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f'Successfully deleted {len(deleted)} messages.', delete_after=5) # ephemeral message
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages here. Please grant me 'Manage Messages'.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while deleting messages: {e}")

# --- Warn Command ---
@bot.command(name='warn')
@commands.has_permissions(kick_members=True) # User needs Kick Members permission to use this
async def warn_user(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """Warns a user and DMs them the reason. Usage: eli warn <@user> [reason]
    Requires 'Kick Members' permission."""
    if member == ctx.author:
        await ctx.send("You cannot warn yourself!")
        return
    if member == bot.user:
        await ctx.send("Why would you warn me? I'm trying my best! 🥺")
        return
    if ctx.author.top_role.position <= member.top_role.position and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You cannot warn someone with an equal or higher role than yourself!")
        return
    if member.id == ctx.guild.owner_id:
        await ctx.send("You cannot warn the server owner!")
        return
    # Note: For 'warn', bot hierarchy doesn't strictly matter for the action itself (no API call to Discord for warn),
    # but the checks are kept for consistency and to prevent a low-ranked bot role trying to "warn" a high-ranked user
    # which might seem odd or imply a capability it doesn't have for real moderation actions.
    if ctx.guild.me.top_role.position <= member.top_role.position:
        await ctx.send("My highest role is not high enough to warn this user. Please move my role higher in server settings.")
        return

    try:
        # Try to DM the user
        dm_message = f"You have been warned in **{ctx.guild.name}** for: {reason}"
        await member.send(dm_message)
        await ctx.send(f'{member.mention} has been warned for: {reason}')
        print(f"Warned {member.name} in {ctx.guild.name} for: {reason}")
    except discord.Forbidden:
        await ctx.send(f"Warned {member.mention} for: {reason}, but could not DM them (they may have DMs disabled).")
        print(f"Failed to DM {member.name} (Forbidden) during warn.")
    except Exception as e:
        await ctx.send(f"An error occurred while warning {member.mention}: {e}")
        print(f"Error warning {member.name}: {e}")

# --- Kick Command ---
@bot.command(name='kick')
@commands.has_permissions(kick_members=True) # User needs Kick Members permission to use this
async def kick_user(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """Kicks a member from the server. Usage: eli kick <@user> [reason]
    Requires 'Kick Members' permission."""
    if member == ctx.author:
        await ctx.send("You cannot kick yourself!")
        return
    if member == bot.user:
        await ctx.send("You can't kick me! I'm essential! 😠")
        return
    if ctx.author.top_role.position <= member.top_role.position and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You cannot kick someone with an equal or higher role than yourself!")
        return
    if member.id == ctx.guild.owner_id:
        await ctx.send("You cannot kick the server owner!")
        return
    # Check if bot has higher role than the member to be kicked
    if ctx.guild.me.top_role.position <= member.top_role.position:
        await ctx.send("My highest role is not high enough to kick this user. Please move my role higher in server settings.")
        return

    try:
        # Try to DM the user before kicking
        dm_message = f"You have been kicked from **{ctx.guild.name}** for: {reason}"
        await member.send(dm_message)
        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked for: {reason}')
        print(f"Kicked {member.name} from {ctx.guild.name} for: {reason}")
    except discord.Forbidden:
        # If DM fails (e.g., user has DMs disabled), still try to kick
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member.mention} for: {reason}, but could not DM them (they may have DMs disabled).")
        print(f"Kicked {member.name}, but failed to DM (Forbidden).")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to kick {member.mention}: {e}")
        print(f"Error kicking {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in kick: {e}")


# --- Ban Command ---
@bot.command(name='ban')
@commands.has_permissions(ban_members=True) # User needs Ban Members permission to use this
async def ban_user(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """Bans a member from the server. Usage: eli ban <@user> [reason]
    Requires 'Ban Members' permission."""
    if member == ctx.author:
        await ctx.send("You cannot ban yourself!")
        return
    if member == bot.user:
        await ctx.send("Banning me? That's not very friendly! 😅")
        return
    if ctx.author.top_role.position <= member.top_role.position and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You cannot ban someone with an equal or higher role than yourself!")
        return
    if member.id == ctx.guild.owner_id:
        await ctx.send("You cannot ban the server owner!")
        return
    # Check if bot has higher role than the member to be banned
    if ctx.guild.me.top_role.position <= member.top_role.position:
        await ctx.send("My highest role is not high enough to ban this user. Please move my role higher in server settings.")
        return

    try:
        # Try to DM the user before banning
        dm_message = f"You have been banned from **{ctx.guild.name}** for: {reason}"
        await member.send(dm_message)
        await member.ban(reason=reason)
        await ctx.send(f'{member.mention} has been banned for: {reason}')
        print(f"Banned {member.name} from {ctx.guild.name} for: {reason}")
    except discord.Forbidden:
        # If DM fails (e.g., user has DMs disabled), still try to ban
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member.mention} for: {reason}, but could not DM them (they may have DMs disabled).")
        print(f"Banned {member.name}, but failed to DM (Forbidden).")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to ban {member.mention}: {e}")
        print(f"Error banning {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in ban: {e}")


# --- Mute Command (using Discord's native Timeout) ---
@bot.command(name='mute')
@commands.has_permissions(moderate_members=True) # Requires 'Moderate Members' permission
async def mute_user(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided."):
    """Times out a member for a specified duration. Usage: eli mute <@user> <duration> [reason]
    Duration examples: 5s, 10m, 1h, 3d (max 28 days). Requires 'Moderate Members' permission."""

    if member == ctx.author:
        await ctx.send("You cannot timeout yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot be timed out! I'm already super chill. 😎")
        return
    if ctx.author.top_role.position <= member.top_role.position and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You cannot timeout someone with an equal or higher role than yourself!")
        return
    if member.id == ctx.guild.owner_id:
        await ctx.send("You cannot timeout the server owner!")
        return
    # Check if bot has higher role than the member to be timed out
    if ctx.guild.me.top_role.position <= member.top_role.position:
        await ctx.send("My highest role is not high enough to timeout this user. Please move my role higher in server settings.")
        return

    try:
        time_delta = parse_duration(duration) # Use the helper function
        # Calculate when the timeout will end
        # Discord uses UTC for timeouts, so ensure current time is UTC
        timeout_until = datetime.datetime.now(datetime.timezone.utc) + time_delta

        # Apply timeout
        await member.timeout(timeout_until, reason=reason)

        # Try to DM the user
        dm_message = f"You have been timed out in **{ctx.guild.name}** for **{duration}** (until {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')}) for: {reason}"
        await member.send(dm_message)
        await ctx.send(f'{member.mention} has been timed out for {duration} for: {reason}')
        print(f"Timed out {member.name} in {ctx.guild.name} for {duration} for: {reason}")

    except ValueError as ve:
        await ctx.send(f"Error: {ve}. Please use formats like `5s`, `10m`, `1h`, `3d`.")
    except discord.Forbidden:
        # If DM fails (e.g., user has DMs disabled), still try to timeout
        await ctx.send(f"Timed out {member.mention} for: {reason}, but could not DM them (they may have DMs disabled).")
        print(f"Timed out {member.name}, but failed to DM (Forbidden).")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to timeout {member.mention}: {e}")
        print(f"Error timing out {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in mute: {e}")


# --- Unmute Command (removes Discord's native Timeout) ---
@bot.command(name='unmute')
@commands.has_permissions(moderate_members=True) # Requires 'Moderate Members' permission
async def unmute_user(ctx, member: discord.Member, *, reason: str = "No reason provided."):
    """Removes timeout from a member. Usage: eli unmute <@user> [reason]
    Requires 'Moderate Members' permission."""

    if not member.is_timed_out():
        await ctx.send(f"{member.mention} is not currently timed out.")
        return

    try:
        await member.timeout(None, reason=reason) # Setting timeout to None removes it
        dm_message = f"Your timeout in **{ctx.guild.name}** has been removed. Reason: {reason}"
        await member.send(dm_message)
        await ctx.send(f'{member.mention}\'s timeout has been removed.')
        print(f"Removed timeout from {member.name} in {ctx.guild.name} for: {reason}")
    except discord.Forbidden:
        await ctx.send(f"Removed timeout from {member.mention}, but could not DM them (Forbidden).")
        print(f"Removed timeout from {member.name}, but failed to DM (Forbidden).")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while unmuting {member.mention}: {e}")
        print(f"Error unmuting {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in unmute: {e}")


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