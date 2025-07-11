import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import asyncio
import json

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- Automod Blacklists ---
BAD_WORDS = [
    "motherfucker","cock","pussy",
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

WARNINGS_FILE = 'warnings.json'
MODLOG_SETTINGS_FILE = 'modlog_settings.json'

# --- Emojis for Embed Decorations ---
EMOJI_SPARKLE = "<a:80524pinkstars:1392781611623514173>"
EMOJI_HEART = "<:32562pinkheart:1392780764835217408>"
EMOJI_RIBBON = "<:22499bow:1392780501886177380>"
EMOJI_STAR = "<a:Pinkstar:1392784692138217543>"
EMOJI_FLOWER = "<:CherryBlossom:1392784047234748417>"
EMOJI_CROWN = "<:26985whitecrown:1392780685592231936>"
EMOJI_MANYBUTTERFLIES = "<a:65954pinkbutterflies:1392780618018066512>"
EMOJI_BUTTERFLY = "<a:95526butterflypink:1392781803093233765>"
# --- END Emojis ---

def load_modlog_settings():
    """Loads modlog channel IDs from a JSON file."""
    if os.path.exists(MODLOG_SETTINGS_FILE):
        with open(MODLOG_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_modlog_settings(settings):
    """Saves modlog channel IDs to a JSON file."""
    with open(MODLOG_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

# --- Send Modlog Embed Helper Function ---
async def send_modlog_embed(bot_instance, guild, action_type, target_user, moderator, reason, **kwargs):
    """
    Sends a formatted moderation log embed to the designated modlog channel.

    Args:
        bot_instance: The bot instance (use `bot` variable from your main file).
        guild (discord.Guild): The guild where the action occurred.
        action_type (str): Type of moderation action (e.g., "Warn", "Ban", "Purge").
        target_user (discord.User or discord.Member): The user affected by the action.
        moderator (discord.Member): The moderator who took the action.
        reason (str): The reason for the action.
        **kwargs: Additional details like 'duration' for mute or 'message_count' for purge.
    """
    modlog_settings = load_modlog_settings()
    channel_id = modlog_settings.get(str(guild.id))

    if not channel_id:
        print(f"Modlog channel not set for guild {guild.name} ({guild.id}). Skipping modlog entry.")
        return

    modlog_channel = guild.get_channel(int(channel_id))
    if not modlog_channel:
        print(f"Modlog channel (ID: {channel_id}) not found in guild {guild.name}. Skipping modlog entry.")
        # Optionally, remove invalid channel ID from settings here
        # del modlog_settings[str(guild.id)]
        # save_modlog_settings(modlog_settings)
        return

    # Check bot's permissions to send messages in the modlog channel
    if not modlog_channel.permissions_for(guild.me).send_messages:
        print(f"Bot does not have permissions to send messages in modlog channel {modlog_channel.name} ({modlog_channel.id}). Skipping modlog entry.")
        # Optionally, send a message to the ctx.channel if bot lacks modlog send permissions
        # await ctx.send(f"Warning: I don't have permission to send messages in the configured modlog channel ({modlog_channel.mention}).")
        return

    # Define colors for different action types
    color_map = {
        "Warn": 0xFFB6C1,  # Orange
        "Mute": 0xFFB6C1,  # Dark Orange
        "Unmute": 0xFFB6C1, # Lime Green
        "Kick": 0xFFB6C1,  # Orange Red
        "Ban": 0xFFB6C1,   # Crimson Red
        "Unban": 0xFFB6C1, # Forest Green
        "Purge": 0xFFB6C1  # Royal Blue
    }
    embed_color = color_map.get(action_type, 0x808080) # Default grey if action type not mapped

    embed = discord.Embed(
        title=f"{EMOJI_CROWN} Modlog: {action_type} {EMOJI_CROWN}",
        color=embed_color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    embed.add_field(name=f"{EMOJI_RIBBON} User", value=target_user.mention, inline=False)
    embed.add_field(name=f"{EMOJI_HEART} User ID", value=target_user.id, inline=True)
    # Check if target_user has a discriminator (true for discord.User and discord.Member)
    if hasattr(target_user, 'discriminator') and target_user.discriminator != '0': # Discord changed to no discriminator for new users
        embed.add_field(name=f"{EMOJI_STAR} Username", value=str(target_user), inline=True)
    else: # For new Discord usernames without discriminator
        embed.add_field(name=f"{EMOJI_STAR} Username", value=target_user.name, inline=True)


    embed.add_field(name=f"{EMOJI_FLOWER} Moderator", value=moderator.mention, inline=False)
    embed.add_field(name=f"{EMOJI_SPARKLE} Reason", value=reason if reason else "No reason provided.", inline=False)

    # Add extra details based on action type
    if action_type == "Mute" and 'duration' in kwargs:
        embed.add_field(name=f"🕰️ Duration", value=kwargs['duration'], inline=False)
    elif action_type == "Purge" and 'message_count' in kwargs:
        embed.add_field(name=f"🗑️ Messages Deleted", value=kwargs['message_count'], inline=False)

    embed.set_footer(text=f"Server: {guild.name}", icon_url=guild.icon.url if guild.icon else None)

    try:
        await modlog_channel.send(embed=embed)
    except discord.HTTPException as e:
        print(f"Failed to send modlog embed to channel {modlog_channel.name} ({modlog_channel.id}) in guild {guild.name}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while sending modlog for guild {guild.name}: {e}")

# --- END Modlog Helper Function ---

# --- Helper function to parse duration strings (e.g., "5s", "10m", "1h", "3d") ---
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

# --- Helper functions for warnings persistence ---
def load_warnings():
    """Loads warning data from the JSON file."""
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                # Ensure guild IDs are strings (JSON keys are always strings)
                return {guild_id: data[guild_id] for guild_id in data}
            except json.JSONDecodeError:
                print(f"Warning: {WARNINGS_FILE} is corrupted or empty. Starting fresh.")
                return {}
    return {} # Return empty dict if file doesn't exist

def save_warnings(data):
    """Saves warning data to the JSON file."""
    with open(WARNINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4) # indent=4 makes the JSON file human-readable
# --- END Helper functions ---

# --- Helper for unban command to find banned user ---
async def get_banned_user(guild, user_input):
    """Fetches a banned user by ID or username#discriminator."""
    bans = [entry async for entry in guild.bans()] # Fetch all bans
    
    # Try to find by ID
    if user_input.isdigit():
        for ban_entry in bans:
            if str(ban_entry.user.id) == user_input:
                return ban_entry.user
    # Try to find by username#discriminator (case-insensitive)
    else:
        for ban_entry in bans:
            if str(ban_entry.user).lower() == user_input.lower():
                return ban_entry.user
    return None # User not found in ban list
# --- END Helper for unban ---

# Define intents (important for modern Discord bots)
intents = discord.Intents.default()
intents.message_content = True # Enable message content intent if your bot reads messages
intents.members = True # Enable if your bot needs member info

# Initialize the bot with a command prefix and intents
bot = commands.Bot(command_prefix='eli ', intents=intents)
bot.remove_command('help')

BOT_START_TIME = datetime.datetime.now(datetime.timezone.utc)

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

    # --- Check for exact 'eli' mention ---
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

# --- botinfo Command ---
@bot.command(name='botinfo') 
async def bot_info(ctx):
    """Displays information and statistics about the bot."""

    # Calculate uptime
    current_time = datetime.datetime.now(datetime.timezone.utc)
    uptime_delta = current_time - BOT_START_TIME

    # Format uptime nicely
    days, remainder = divmod(int(uptime_delta.total_seconds()), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    uptime_string_parts = []
    if days:
        uptime_string_parts.append(f"{days}d")
    if hours:
        uptime_string_parts.append(f"{hours}h")
    if minutes:
        uptime_string_parts.append(f"{minutes}m")
    if seconds or not uptime_string_parts: # Show seconds if less than a minute, or if 0
        uptime_string_parts.append(f"{seconds}s")
    
    uptime_str = " ".join(uptime_string_parts)


    embed = discord.Embed(
        title=f"{EMOJI_CROWN} My Information {EMOJI_CROWN}",
        description=f"{EMOJI_HEART} All about your friendly moderation bot! {EMOJI_HEART}",
        color=0xFFB6C1 # Pinkish color
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

    # General Info
    embed.add_field(name=f"Name {EMOJI_RIBBON}", value=bot.user.name, inline=True)
    embed.add_field(name=f"ID {EMOJI_STAR}", value=bot.user.id, inline=True)
    embed.add_field(name=f"Prefix {EMOJI_FLOWER}", value=f"`{bot.command_prefix}`", inline=True)

    # Stats
    embed.add_field(name=f"Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name=f"Users Served", value=len(bot.users), inline=True)
    embed.add_field(name=f"Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name=f"Uptime", value=uptime_str, inline=False)
    
    # Other Info
    embed.add_field(name=f"Library", value=f"discord.py v{discord.__version__}", inline=True)
    embed.add_field(name=f"Owner {EMOJI_CROWN}", value=f"<@{os.getenv('BOT_OWNER_ID') or 'Not Set'}>", inline=True)
    embed.add_field(name=f"Created On", value=bot.user.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)


    await ctx.send(embed=embed)

# --- userinfo Command ---
@bot.command(name='userinfo', aliases=['whois']) # 'uinfo' alias removed
async def user_info(ctx, member: discord.Member = None):
    """Displays detailed information about a user.
    Usage: eli userinfo [member_mention_or_id]"""

    if member is None:
        member = ctx.author # If no member is specified, get info about the command invoker

    embed = discord.Embed(
        title=f"{EMOJI_FLOWER} User Info: {member.display_name} {EMOJI_FLOWER}",
        color=0xFFB6C1, # Consistent pink color
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

    # General User Information (applies to any Discord User, even if not in current guild)
    embed.add_field(name=f"{EMOJI_RIBBON} User", value=member.mention, inline=False)
    
    # Handle discriminator for older vs. new usernames
    if hasattr(member, 'discriminator') and member.discriminator != '0':
        embed.add_field(name=f"{EMOJI_SPARKLE} Username", value=f"{member.name}#{member.discriminator}", inline=True)
    else:
        embed.add_field(name=f"{EMOJI_SPARKLE} Username", value=member.name, inline=True)
        
    embed.add_field(name=f"{EMOJI_STAR} User ID", value=member.id, inline=True)
    embed.add_field(name=f"{EMOJI_RIBBON} Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)

    # Guild-Specific Information (only applies if the member is in the current guild)
    if isinstance(member, discord.Member): # Check if it's a Member object (means they are in the guild)
        embed.add_field(name=f"{EMOJI_STAR} Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        
        # Roles
        # Filter out @everyone role and sort roles by position
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles.reverse() # Display highest role first
        embed.add_field(name=f"{EMOJI_RIBBON} Roles ({len(roles)})", value="\n".join(roles) if roles else "No roles (except @everyone)", inline=False)
        embed.add_field(name=f"{EMOJI_CROWN} Top Role", value=member.top_role.mention, inline=True)

        # Status
        status_map = {
            discord.Status.online: "Online",
            discord.Status.idle: "Idle",
            discord.Status.dnd: "Do Not Disturb",
            discord.Status.offline: "Offline"
        }
        embed.add_field(name=f"{EMOJI_HEART} Status", value=status_map.get(member.status, "Unknown"), inline=True)

        # Activities
        activities = []
        for activity in member.activities:
            if isinstance(activity, discord.Game):
                activities.append(f"Playing **{activity.name}**")
            elif isinstance(activity, discord.Streaming):
                activities.append(f"Streaming **{activity.name}** on {activity.platform}")
            elif isinstance(activity, discord.Activity): # General custom status or other types
                activities.append(f"{activity.name}")
            elif isinstance(activity, discord.CustomActivity):
                 activities.append(f"Custom Status: {activity.name}")


        if activities:
            embed.add_field(name=f"{EMOJI_BUTTERFLY} Activities", value="\n".join(activities), inline=False)
        else:
            embed.add_field(name=f"{EMOJI_BUTTERFLY} Activities", value="No current activity.", inline=False)
            
    else: # If the member is not in the guild (e.g., from an ID that's not a current member)
        embed.add_field(name="Note", value="This user is not currently in this server.", inline=False)

    await ctx.send(embed=embed)

@user_info.error
async def user_info_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(f"{EMOJI_SPARKLE} Could not find that member. Please make sure you spelled the name correctly or provided a valid ID/mention. {EMOJI_SPARKLE}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{EMOJI_SPARKLE} Invalid argument. Please mention a member or provide their ID. Usage: `eli userinfo [member_mention_or_id]` {EMOJI_SPARKLE}")
    else:
        await ctx.send(f"{EMOJI_HEART} An error occurred: {error} {EMOJI_HEART}")
        print(f"Error in user_info: {error}")

# --- Detailed Server Info Command with Embed ---
@bot.command(name='serverinfo', aliases=['guildinfo', 'server'])
async def server_info(ctx):
    """Displays information about the current server."""
    guild = ctx.guild # Get the guild (server) object

    embed = discord.Embed(
        title=f"{EMOJI_CROWN} {guild.name} Server Info! {EMOJI_CROWN}", # Crown emojis for server
        description=f"{EMOJI_HEART} All the lovely details about this cozy place! {EMOJI_HEART}", # Hearts for description
        color=0xFFB6C1 # A warm, inviting color for server info
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None) # Server icon
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

    # General Server Info
    embed.add_field(name=f"Server ID {EMOJI_RIBBON}", value=guild.id, inline=True)
    embed.add_field(name=f"Owner {EMOJI_FLOWER}", value=guild.owner.mention, inline=True)
    embed.add_field(name=f"Created On {EMOJI_SPARKLE}", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)

    # Members & Channels
    embed.add_field(name=f"Members {EMOJI_HEART}", value=guild.member_count, inline=True)
    embed.add_field(name=f"Channels {EMOJI_STAR}", value=len(guild.channels), inline=True)
    embed.add_field(name=f"Roles {EMOJI_RIBBON}", value=len(guild.roles), inline=True)

    # Features and Boosts
    embed.add_field(name=f"Boost Level {EMOJI_CROWN}", value=guild.premium_tier, inline=True)
    embed.add_field(name=f"Boosts {EMOJI_SPARKLE}", value=guild.premium_subscription_count, inline=True)
    # Convert Discord's VerificationLevel enum to a readable string
    verification_level_map = {
        discord.VerificationLevel.none: "None",
        discord.VerificationLevel.low: "Low (Email)",
        discord.VerificationLevel.medium: "Medium (5 Mins)",
        discord.VerificationLevel.high: "High (10 Mins)",
        discord.VerificationLevel.highest: "Highest (Phone)"
    }
    embed.add_field(name=f"<:lock_IDS:1392785385675034774> Verification Level", value=verification_level_map.get(guild.verification_level, "Unknown"), inline=True)


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
@commands.has_permissions(manage_messages=True)
async def purge_messages(ctx, amount: int):
    """Deletes a specified number of messages. Usage: eli purge <amount>
    Requires 'Manage Messages' permission."""
    if amount <= 0:
        await ctx.send(f"{EMOJI_SPARKLE} Please specify a positive number of messages to delete. {EMOJI_SPARKLE}")
        return

    try:
        deleted = await ctx.channel.purge(limit=amount + 1) # +1 to also delete the purge command itself
        deleted_count = len(deleted) - 1 # Exclude the command message itself
        if deleted_count < 0: deleted_count = 0 # Ensure not negative if only command was deleted

        embed = discord.Embed(
            title=f"{EMOJI_RIBBON} Messages Purged! {EMOJI_RIBBON}",
            description=f"{EMOJI_SPARKLE} Successfully deleted {deleted_count} messages in {ctx.channel.mention}.",
            color=0xFFB6C1 # Royal Blue
        )
        embed.set_footer(text=f"Purged by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed, delete_after=5) # Send confirmation, delete after 5 seconds

        print(f"Purged {deleted_count} messages in {ctx.channel.name} by {ctx.author.name}.")

        # --- NEW: Call modlog function for purge ---
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Purge",
            ctx.author, # The purger is the target in this context
            ctx.author, # The purger is also the moderator
            f"Purged {deleted_count} messages.",
            message_count=deleted_count # Pass message count as extra detail
        )
        # --- END NEW ---

    except discord.Forbidden:
        await ctx.send(f"{EMOJI_CROWN} I don't have permission to manage messages in this channel. Please grant me 'Manage Messages'. {EMOJI_CROWN}")
        print(f"Bot lacks permissions to purge messages in {ctx.channel.name}.")
    except Exception as e:
        await ctx.send(f"{EMOJI_HEART} An unexpected error occurred: {e} {EMOJI_HEART}")
        print(f"Error purging messages: {e}")

@purge_messages.error
async def purge_messages_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"{EMOJI_CROWN} You don't have permission to purge messages. You need the 'Manage Messages' permission. {EMOJI_CROWN}")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{EMOJI_SPARKLE} Please specify the number of messages to delete. Usage: `eli purge <amount>` {EMOJI_SPARKLE}")
    else:
        await ctx.send(f"{EMOJI_HEART} An error occurred: {error} {EMOJI_HEART}")
        print(f"Error in purge: {error}")

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
        dm_embed = discord.Embed(
            title=f"{EMOJI_HEART} You have been Warned! {EMOJI_HEART}",
            description=(
                f"In **{ctx.guild.name}**:\n"
                f"{EMOJI_SPARKLE} **Reason:** {reason}\n"
                f"{EMOJI_RIBBON} **Moderator:** {ctx.author.mention}"
            ),
            color=0xFFB6C1 # Light Pink
        )
        dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
        await member.send(embed=dm_embed) # Changed to embed
        await ctx.send(f'{member.mention} has been warned for: {reason}')
        print(f"Warned {member.name} in {ctx.guild.name} for: {reason}")

        # --- Saves the warning persistently ---
        warnings_data = load_warnings()
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)
        moderator_id = str(ctx.author.id)
        # Store timestamp in ISO format for easy parsing and sorting
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if guild_id not in warnings_data:
            warnings_data[guild_id] = {}
        if member_id not in warnings_data[guild_id]:
            warnings_data[guild_id][member_id] = []

        warnings_data[guild_id][member_id].append({
            "reason": reason,
            "moderator_id": moderator_id,
            "timestamp": timestamp
        })
        save_warnings(warnings_data)
        # --- Save warning | End ---

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Warn",
            member,
            ctx.author,
            reason
        )

    except discord.Forbidden:
        await ctx.send(f"Warned {member.mention} for: {reason}, but could not DM them (they may have DMs disabled).")
        print(f"Failed to DM {member.name} (Forbidden) during warn.")
        # Still save warning even if DM fails
        warnings_data = load_warnings()
        guild_id = str(ctx.guild.id)
        member_id = str(member.id)
        moderator_id = str(ctx.author.id)
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if guild_id not in warnings_data:
            warnings_data[guild_id] = {}
        if member_id not in warnings_data[guild_id]:
            warnings_data[guild_id][member_id] = []
        warnings_data[guild_id][member_id].append({
            "reason": reason,
            "moderator_id": moderator_id,
            "timestamp": timestamp
        })
        save_warnings(warnings_data)
    except Exception as e:
        await ctx.send(f"An error occurred while warning {member.mention}: {e}")
        print(f"Error warning {member.name}: {e}")

# --- Warnings Command ---
@bot.command(name='warnings')
@commands.has_permissions(kick_members=True)
async def show_warnings(ctx, member: discord.Member):
    """Shows a list of warnings for a user. Usage: eli warnings <@user>
    Requires 'Kick Members' permission."""

    warnings_data = load_warnings()
    guild_id = str(ctx.guild.id)
    member_id = str(member.id)

    # Embed for no warnings found
    if guild_id not in warnings_data or member_id not in warnings_data[guild_id]:
        embed = discord.Embed(
            title=f"{EMOJI_HEART} Warnings for {member.display_name} {EMOJI_HEART}", # Using global EMOJI_HEART
            description=f"{EMOJI_SPARKLE} No warnings found for {member.mention}! {EMOJI_SPARKLE}", # Using global EMOJI_SPARKLE
            color=0xFFB6C1
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        await ctx.send(embed=embed)
        return

    user_warnings = warnings_data[guild_id][member_id]

    # Redundant check, but safe. Can be removed if the above 'if' handles all no-warning cases.
    if not user_warnings:
        embed = discord.Embed(
            title=f"{EMOJI_HEART} Warnings for {member.display_name} {EMOJI_HEART}", # Using global EMOJI_HEART
            description=f"{EMOJI_SPARKLE} No warnings found for {member.mention}! {EMOJI_SPARKLE}", # Using global EMOJI_SPARKLE
            color=0xFFB6C1
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        await ctx.send(embed=embed)
        return

    # Embed for warnings found
    embed = discord.Embed(
        title=f"{EMOJI_MANYBUTTERFLIES} Warnings for {member.display_name} ({len(user_warnings)} total) {EMOJI_MANYBUTTERFLIES}", # Using global EMOJI_RIBBON
        color=0xFFB6C1
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)


    for i, warning in enumerate(user_warnings, 1):
        reason = warning.get("reason", "No reason provided.")
        moderator_id = warning.get("moderator_id")
        timestamp_str = warning.get("timestamp")

        moderator_name = "Unknown Moderator"
        if moderator_id:
            try:
                mod_member = ctx.guild.get_member(int(moderator_id))
                if mod_member:
                    moderator_name = mod_member.display_name
                else:
                    mod_user = await bot.fetch_user(int(moderator_id))
                    if mod_user:
                        moderator_name = mod_user.name
            except Exception:
                pass

        formatted_timestamp = "N/A"
        if timestamp_str:
            try:
                dt_object = datetime.datetime.fromisoformat(timestamp_str)
                formatted_timestamp = dt_object.strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                pass

        embed.add_field(
            name=f"{EMOJI_BUTTERFLY} Warning #{i}", # Using global EMOJI_SPARKLE
            value=(
                f"**Reason:** {reason}\n"
                f"**Moderator:** {moderator_name}\n"
                f"**Date:** {formatted_timestamp}"
            ),
            inline=False
        )

    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    await ctx.send(embed=embed)

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
        # Try to DM the user with an embed BEFORE kicking
        try:
            dm_embed = discord.Embed(
                title=f"{EMOJI_HEART} You have been Kicked! {EMOJI_HEART}",
                description=(
                    f"From **{ctx.guild.name}**:\n"
                    f"{EMOJI_SPARKLE} **Reason:** {reason}\n"
                    f"{EMOJI_RIBBON} **Moderator:** {ctx.author.mention}"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
            await member.send(embed=dm_embed)
            print(f"DM sent to {member.name} before kick.")
        except discord.Forbidden:
            print(f"Could not DM {member.name} before kick (DMs forbidden or no mutual guilds).")
        except Exception as dm_e:
            print(f"An unexpected error occurred while DMing {member.name} before kick: {dm_e}")

        await member.kick(reason=reason) # Perform the kick
        await ctx.send(f'{member.mention} has been kicked for: {reason}')
        print(f"Kicked {member.name} from {ctx.guild.name} for: {reason}.")

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Kick",
            member,
            ctx.author,
            reason
        )

    except discord.Forbidden:
        await ctx.send(f"I don't have permission to kick members. Please grant me 'Kick Members'.")
        print(f"Bot lacks permissions to kick {member.name}.")
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
        # Try to DM the user with an embed BEFORE banning
        try:
            dm_embed = discord.Embed(
                title=f"{EMOJI_HEART} You have been Banned! {EMOJI_HEART}",
                description=(
                    f"From **{ctx.guild.name}**:\n"
                    f"{EMOJI_SPARKLE} **Reason:** {reason}\n"
                    f"{EMOJI_RIBBON} **Moderator:** {ctx.author.mention}"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
            await member.send(embed=dm_embed)
            print(f"DM sent to {member.name} before ban.")
        except discord.Forbidden:
            print(f"Could not DM {member.name} before ban (DMs forbidden or no mutual guilds).")
        except Exception as dm_e:
            print(f"An unexpected error occurred while DMing {member.name} before ban: {dm_e}")

        await member.ban(reason=reason) # Perform the ban
        await ctx.send(f'{member.mention} has been banned for: {reason}')
        print(f"Banned {member.name} from {ctx.guild.name} for: {reason}.")

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Ban",
            member,
            ctx.author,
            reason
        )

    except discord.Forbidden:
        await ctx.send(f"I don't have permission to ban members. Please grant me 'Ban Members'.")
        print(f"Bot lacks permissions to ban {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to ban {member.mention}: {e}")
        print(f"Error banning {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in ban: {e}")

# --- Unban Command ---
@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban_user(ctx, user_id_or_name: str, *, reason: str = "No reason provided."):
    """Unbans a user from the server. Usage: eli unban <user_id_or_name> [reason]
    User ID is preferred for accuracy, but also accepts username#discriminator if unique.
    Requires 'Ban Members' permission."""

    try:
        # Get the banned user object
        banned_users = [entry async for entry in ctx.guild.bans()]
        user_to_unban = None

        # Loop through banned users to find a match by ID or name
        for ban_entry in banned_users:
            # Check by User ID (more reliable)
            if str(ban_entry.user.id) == user_id_or_name:
                user_to_unban = ban_entry.user
                break
            # Check by username#discriminator (less reliable if not unique)
            if ban_entry.user.name == user_id_or_name or str(ban_entry.user) == user_id_or_name:
                 user_to_unban = ban_entry.user
                 break


        if not user_to_unban:
            await ctx.send(f"Could not find a banned user matching `{user_id_or_name}` in the ban list.")
            return

        # Perform the unban
        await ctx.guild.unban(user_to_unban, reason=reason)

        # Try to DM the unbanned user with an embed
        try:
            dm_embed = discord.Embed(
                title=f"{EMOJI_HEART} You have been Unbanned! {EMOJI_HEART}",
                description=(
                    f"From **{ctx.guild.name}**:\n"
                    f"{EMOJI_SPARKLE} You may now rejoin the server."
                    # You could add moderator here if desired:
                    # f"\n{EMOJI_RIBBON} **Unbanned by:** {ctx.author.mention}"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
            await user_to_unban.send(embed=dm_embed)
            print(f"DM sent to {user_to_unban.name} after unban.")
        except discord.Forbidden:
            print(f"Could not DM {user_to_unban.name} after unban (DMs forbidden or no mutual guilds).")
        except Exception as dm_e:
            print(f"An unexpected error occurred while DMing {user_to_unban.name} after unban: {dm_e}")

        await ctx.send(f'{user_to_unban.name} has been unbanned. Reason: {reason}')
        print(f"Unbanned {user_to_unban.name} from {ctx.guild.name} for: {reason}.")

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Unban",
            user_to_unban, # Use user_to_unban as the target
            ctx.author,
            reason
        )

    except discord.Forbidden:
        await ctx.send(f"I don't have permission to unban members. Please grant me 'Ban Members'.")
        print(f"Bot lacks permissions to unban.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to unban `{user_id_or_name}`: {e}")
        print(f"Error unbanning `{user_id_or_name}`: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in unban: {e}")    


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
        time_delta = parse_duration(duration)
        timeout_until = datetime.datetime.now(datetime.timezone.utc) + time_delta

        # Create human-readable duration_str
        seconds = int(time_delta.total_seconds())
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        duration_parts = []
        if days:
            duration_parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours:
            duration_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            duration_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds and not days and not hours and not minutes:
             duration_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        if not duration_parts:
            duration_str = "0 seconds"
        else:
            duration_str = ", ".join(duration_parts)

        # Apply timeout
        await member.timeout(timeout_until, reason=reason)

        # Try to DM the user with an embed
        try: # This 'try' must be properly indented under the outer 'try'
            dm_embed = discord.Embed(
                title=f"{EMOJI_HEART} You have been Timed Out! {EMOJI_HEART}",
                description=(
                    f"In **{ctx.guild.name}**:\n"
                    f"{EMOJI_SPARKLE} **Reason:** {reason}\n"
                    f"{EMOJI_RIBBON} **Moderator:** {ctx.author.mention}\n"
                    f"{EMOJI_STAR} **Duration:** {duration_str} (until {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')})"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
            await member.send(embed=dm_embed) # Sending the embed
            print(f"DM sent to {member.name} after mute.")
        except discord.Forbidden: # This 'except' must align with the inner 'try'
            print(f"Could not DM {member.name} after mute (DMs forbidden or no mutual guilds).")
        except Exception as dm_e: # This 'except' must align with the inner 'try'
            print(f"An unexpected error occurred while DMing {member.name} after mute: {dm_e}")

        # This send is for the public channel, also properly indented under the outer 'try'
        await ctx.send(f'{member.mention} has been timed out for {duration_str} for: {reason}')
        print(f"Timed out {member.name} in {ctx.guild.name} for {duration_str} for: {reason}")

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Mute",
            member,
            ctx.author,
            reason,
            duration=duration_str # Pass the human-readable duration
        )

    except ValueError as ve:
        await ctx.send(f"Error: {ve}. Please use formats like `5s`, `10m`, `1h`, `3d`.")
    except discord.Forbidden:
        # This outer discord.Forbidden catches permission errors for `await member.timeout()`
        await ctx.send(f"I don't have permission to timeout members. Please grant me 'Moderate Members'.")
        print(f"Bot lacks permissions to timeout {member.name}.")
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

        # Try to DM the user with an embed
        try:
            dm_embed = discord.Embed(
                title=f"{EMOJI_HEART} Your Timeout has been Removed! {EMOJI_HEART}",
                description=(
                    f"In **{ctx.guild.name}**:\n"
                    f"{EMOJI_SPARKLE} **Reason:** {reason}\n"
                    f"{EMOJI_RIBBON} **Moderator:** {ctx.author.mention}"
                ),
                color=0xFFB6C1
            )
            dm_embed.set_footer(text=f"Server: {ctx.guild.name} | Bot: {bot.user.name}")
            await member.send(embed=dm_embed)
            print(f"DM sent to {member.name} after unmute.")
        except discord.Forbidden:
            print(f"Could not DM {member.name} after unmute (DMs forbidden or no mutual guilds).")
        except Exception as dm_e:
            print(f"An unexpected error occurred while DMing {member.name} after unmute: {dm_e}")

        await ctx.send(f'{member.mention} has been untimed out. Reason: {reason}')
        print(f"Untimed out {member.name} in {ctx.guild.name}. Reason: {reason}")

        # Call modlog function
        await send_modlog_embed(
            bot, # Pass your bot instance here
            ctx.guild,
            "Unmute",
            member,
            ctx.author,
            reason
        )

    except discord.Forbidden:
        await ctx.send(f"I don't have permission to untimeout members. Please grant me 'Moderate Members'.")
        print(f"Bot lacks permissions to untimeout {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred while trying to untimeout {member.mention}: {e}")
        print(f"Error untiming out {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred: {e}")
        print(f"Unexpected error in unmute: {e}")

# ----- SetModLogChannel command -----
@bot.command(name='setmodlogchannel')
@commands.has_permissions(manage_guild=True)
async def set_modlog_channel(ctx, channel: discord.TextChannel):
    """Sets the channel for moderation logs. Usage: eli setmodlogchannel #channel-name
    Requires 'Manage Server' permission."""
    modlog_settings = load_modlog_settings()
    modlog_settings[str(ctx.guild.id)] = str(channel.id)
    save_modlog_settings(modlog_settings)

    embed = discord.Embed(
        title=f"{EMOJI_RIBBON} Modlog Channel Set! {EMOJI_RIBBON}",
        description=f"Moderation logs will now be sent to {channel.mention}.",
        color=0x98FB98 # Pale Green
    )
    embed.set_footer(text=f"Set by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
    await ctx.send(embed=embed)
    print(f"Modlog channel set to {channel.name} ({channel.id}) for guild {ctx.guild.name}.")

# ---- SetModLog Error ----
@set_modlog_channel.error
async def set_modlog_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"{EMOJI_CROWN} You don't have permission to set the modlog channel. You need the 'Manage Server' permission. {EMOJI_CROWN}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{EMOJI_SPARKLE} Please mention a valid text channel. Usage: `eli setmodlogchannel #channel-name` {EMOJI_SPARKLE}")
    else:
        await ctx.send(f"{EMOJI_HEART} An error occurred: {error} {EMOJI_HEART}")
        print(f"Error in set_modlog_channel: {error}")

# --- Commands List Command ---
@bot.command(name='cmds', aliases=['help', 'commands'])
async def list_commands(ctx):
    """Displays a list of all available commands."""

    embed = discord.Embed(
        title=f"{EMOJI_HEART} Eli Bot Commands! {EMOJI_HEART}", # Using custom EMOJI_HEART
        description=f"{EMOJI_SPARKLE} Here's a list of commands you can use with Eli Bot. "
                    f"My prefix is `eli`. {EMOJI_SPARKLE}", # Using custom EMOJI_SPARKLE
        color=0xADD8E6
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    embed.set_footer(
        text=f"Requested by {ctx.author.name}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    general_cmds = []
    moderation_cmds = []

    for command in bot.commands:
        if command.hidden:
            continue

        formatted_cmd_name = f"**`{bot.command_prefix}{command.name}`**"

        # Check command name and add to appropriate list
        if command.name in ['eli', 'ping', 'info', 'say', 'cmds', 'help', 'commands', 'serverinfo', 'guildinfo', 'server' , 'botinfo' , 'userinfo' , 'whois']:
            general_cmds.append(formatted_cmd_name)
        elif command.name in ['purge', 'warn', 'mute', 'unmute', 'kick', 'ban', 'unban', 'warnings', 'setmodlogchannel']: # ADDED setmodlogchannel here
            moderation_cmds.append(formatted_cmd_name)

    if general_cmds:
        embed.add_field(
            name=f"{EMOJI_FLOWER} General Commands {EMOJI_FLOWER}", # Using custom EMOJI_FLOWER
            value="\n".join(general_cmds),
            inline=False
        )

    if moderation_cmds:
        embed.add_field(
            name=f"{EMOJI_CROWN} Moderation Commands {EMOJI_CROWN}", # Using custom EMOJI_CROWN
            value="\n".join(moderation_cmds),
            inline=False
        )

    await ctx.send(embed=embed)

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


bot.run(TOKEN)  # This will start your Discord bot