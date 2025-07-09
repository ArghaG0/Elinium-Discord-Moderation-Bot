import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import datetime
import asyncio

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
        color=discord.Color.blue() # You can choose any color like discord.Color.green(), 0xHEXCODE, etc.
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