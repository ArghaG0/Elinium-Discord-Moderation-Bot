import json
import discord
import datetime
import re # For parse_duration

# --- Helper Functions for Warnings ---
WARNINGS_FILE = 'warnings.json'

def load_warnings():
    """Loads warning data from warnings.json."""
    try:
        with open(WARNINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {} # Return empty dict if file doesn't exist
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {WARNINGS_FILE}. Returning empty dictionary.")
        return {}

def save_warnings(warnings_data):
    """Saves warning data to warnings.json."""
    with open(WARNINGS_FILE, 'w') as f:
        json.dump(warnings_data, f, indent=4)

# --- NEW: Helper Functions for Blacklists ---
# --- CORRECTED: Helper Functions for Per-Guild Blacklists ---
BLACKLISTS_FILE = 'blacklists.json'

def load_blacklists():
    """Loads per-guild blacklisted words and links from blacklists.json."""
    try:
        with open(BLACKLISTS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # IMPORTANT: Return empty dict if file doesn't exist, to represent no guilds having blacklists yet
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {BLACKLISTS_FILE}. Returning empty dictionary for blacklists.")
        return {}

def save_blacklists(blacklists_data):
    """Saves per-guild blacklisted words and links to blacklists.json."""
    with open(BLACKLISTS_FILE, 'w') as f:
        json.dump(blacklists_data, f, indent=4)

# --- Helper Functions for Modlog Channel ---
MODLOG_SETTINGS_FILE = 'modlog_settings.json'

def load_modlog_settings():
    """Loads modlog channel settings from modlog_settings.json."""
    try:
        with open(MODLOG_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {MODLOG_SETTINGS_FILE}. Returning empty dictionary.")
        return {}

def save_modlog_settings(settings_data):
    """Saves modlog channel settings to modlog_settings.json."""
    with open(MODLOG_SETTINGS_FILE, 'w') as f:
        json.dump(settings_data, f, indent=4)

# --- Modlog Embed Function ---
async def send_modlog_embed(bot, guild, action_type, member, moderator, reason, duration=None, warning_count=None, purge_count=None):
    """Sends a moderation log embed to the configured modlog channel."""
    modlog_settings = load_modlog_settings()
    modlog_channel_id = modlog_settings.get(str(guild.id))

    if not modlog_channel_id:
        return # No modlog channel set for this guild

    modlog_channel = guild.get_channel(int(modlog_channel_id))

    if not modlog_channel:
        print(f"Modlog channel (ID: {modlog_channel_id}) not found in guild {guild.name}.")
        return

    title = f"<:pinkexclamationmark:1393151965114011760> {action_type} Log"
    description = (
        f"**User:** {member.mention} ({member.id})\n"
        f"**Moderator:** {moderator.mention} ({moderator.id})\n"
        f"**Reason:** {reason}"
    )

    color = 0xFFB6C1 # Default color

    # Set specific color and add extra fields based on action type
    if action_type == "Warn":
        #color = discord.Color.gold() # Yellow
        description += f"\n**Warning Count:** {warning_count}"
    elif action_type == "Mute":
        #color = discord.Color.orange() # Orange
        description += f"\n**Duration:** {duration}"
    elif action_type == "Unmute":
        pass
        #color = discord.Color.green() # Green
    elif action_type == "Kick":
        pass
        #color = discord.Color.dark_orange() # Darker Orange
    elif action_type == "Ban":
        pass
        #color = discord.Color.red() # Red
    elif action_type == "Unban":
        pass
        #color = discord.Color.blue() # Blue
    elif action_type == "Purge":
        #color = discord.Color.dark_purple() # Dark Purple
        description += f"\n**Messages Purged:** {purge_count}"
    elif action_type == "Automod":
        #color = discord.Color.dark_red() # Dark Red
        description = (
            f"**User:** {member.mention} ({member.id})\n"
            f"**Action:** Message deleted due to automod\n"
            f"**Reason:** {reason}"
        )

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.set_footer(text=f"Guild: {guild.name} | Bot: {bot.user.name}", icon_url=bot.user.avatar.url if bot.user.avatar else None)

    try:
        await modlog_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"Bot lacks permissions to send messages to modlog channel {modlog_channel.name} in {guild.name}.")
    except Exception as e:
        print(f"Error sending modlog embed to {modlog_channel.name} in {guild.name}: {e}")

# --- Duration Parser ---
def parse_duration(duration_str):
    """Parses a duration string (e.g., '30s', '5m', '1h') into a timedelta object."""
    if not duration_str:
        return None

    # Regex to capture number and unit (s, m, h, d, w)
    pattern = re.compile(r'(\d+)([smhdw])')
    match = pattern.match(duration_str.lower())

    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == 's':
        return datetime.timedelta(seconds=value)
    elif unit == 'm':
        return datetime.timedelta(minutes=value)
    elif unit == 'h':
        return datetime.timedelta(hours=value)
    elif unit == 'd':
        return datetime.timedelta(days=value)
    elif unit == 'w':
        return datetime.timedelta(weeks=value)
    else:
        return None