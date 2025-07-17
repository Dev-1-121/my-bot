# bot.py
import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import json
import os
import aiohttp # For fetching images for emoji commands and now for memes
from io import BytesIO # For handling image data
from typing import Union # Import Union from the typing module
import random # For random bot statuses
import re # For parsing time strings in remindme
from webserver import keep_alive # Import the keep_alive function from webserver.py

# IMPORTANT: Get the Discord bot token from environment variables for security.
# When deploying to Render, you will set this environment variable in their dashboard.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

# Define intents for your bot.
# Intents specify which events your bot wants to receive from Discord.
# discord.Intents.default() provides a good starting point.
# We also need to enable specific intents for member and message content.
intents = discord.Intents.default()
intents.members = True # Required to access member information (e.g., for kick/ban/mute/role/userinfo)
intents.message_content = True # Required to read message content for commands
intents.voice_states = True # Required for voice channel moderation commands

# --- Persistent Storage File Paths ---
PREFIXES_FILE = 'prefixes.json'
WARNINGS_FILE = 'warnings.json'
MOD_LOG_CHANNELS_FILE = 'mod_log_channels.json'
AFK_FILE = 'afk_status.json' # New file for AFK status
AUTOMOD_SETTINGS_FILE = 'automod_settings.json' # New file for AutoMod settings

# --- In-memory Dictionaries (will be loaded from/saved to files) ---
guild_prefixes = {}
user_warnings = {}
mod_log_channels = {}
afk_status = {} # New dictionary for AFK status
automod_settings = {} # Will be loaded from file

# --- Bot Activities for Status ---
# Changed to dnd status and watching "SERVERS !!!"
bot_activities = [
    discord.Activity(type=discord.ActivityType.watching, name="SERVERS !!!"),
]

# --- Functions for Persistent Storage ---

def load_prefixes():
    """Loads custom prefixes from a JSON file."""
    global guild_prefixes
    if os.path.exists(PREFIXES_FILE):
        with open(PREFIXES_FILE, 'r') as f:
            try:
                guild_prefixes = json.load(f)
                # Convert string keys (guild IDs) back to integers
                guild_prefixes = {int(k): v for k, v in guild_prefixes.items()}
                print(f"Loaded prefixes: {guild_prefixes}")
            except json.JSONDecodeError:
                print(f"Error decoding {PREFIXES_FILE}. Starting with empty prefixes.")
                guild_prefixes = {}
    else:
        print(f"{PREFIXES_FILE} not found. Starting with empty prefixes.")
        guild_prefixes = {}

def save_prefixes():
    """Saves custom prefixes to a JSON file."""
    with open(PREFIXES_FILE, 'w') as f:
        # Convert integer keys (guild IDs) to strings for JSON serialization
        json.dump({str(k): v for k, v in guild_prefixes.items()}, f, indent=4)
        print(f"Saved prefixes: {guild_prefixes}")

def load_warnings():
    """Loads user warnings from a JSON file."""
    global user_warnings
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, 'r') as f:
            try:
                user_warnings = json.load(f)
                # Convert string keys (user IDs) back to integers
                user_warnings = {int(k): v for k, v in user_warnings.items()}
                print(f"Loaded warnings: {user_warnings}")
            except json.JSONDecodeError:
                print(f"Error decoding {WARNINGS_FILE}. Starting with empty warnings.")
                user_warnings = {}
    else:
        print(f"{WARNINGS_FILE} not found. Starting with empty warnings.")
        user_warnings = {}

def save_warnings():
    """Saves user warnings to a JSON file."""
    with open(WARNINGS_FILE, 'w') as f:
        # Convert integer keys (user IDs) to strings for JSON serialization
        json.dump({str(k): v for k, v in user_warnings.items()}, f, indent=4)
        print(f"Saved warnings: {user_warnings}")

def load_mod_log_channels():
    """Loads moderation log channel IDs from a JSON file."""
    global mod_log_channels
    if os.path.exists(MOD_LOG_CHANNELS_FILE):
        with open(MOD_LOG_CHANNELS_FILE, 'r') as f:
            try:
                mod_log_channels = json.load(f)
                # Convert string keys (guild IDs) back to integers
                mod_log_channels = {int(k): v for k, v in mod_log_channels.items()}
                print(f"Loaded mod log channels: {mod_log_channels}")
            except json.JSONDecodeError:
                print(f"Error decoding {MOD_LOG_CHANNELS_FILE}. Starting with empty mod log channels.")
                mod_log_channels = {}
    else:
        print(f"{MOD_LOG_CHANNELS_FILE} not found. Starting with empty mod log channels.")
        mod_log_channels = {}

def save_mod_log_channels():
    """Saves moderation log channel IDs to a JSON file."""
    with open(MOD_LOG_CHANNELS_FILE, 'w') as f:
        # Convert integer keys (guild IDs) to strings for JSON serialization
        json.dump({str(k): v for k, v in mod_log_channels.items()}, f, indent=4)
        print(f"Saved mod log channels: {mod_log_channels}")

def load_afk_status():
    """Loads AFK statuses from a JSON file."""
    global afk_status
    if os.path.exists(AFK_FILE):
        with open(AFK_FILE, 'r') as f:
            try:
                afk_status = json.load(f)
                # Convert string keys (user IDs) back to integers
                afk_status = {int(k): v for k, v in afk_status.items()}
                print(f"Loaded AFK status: {afk_status}")
            except json.JSONDecodeError:
                print(f"Error decoding {AFK_FILE}. Starting with empty AFK status.")
                afk_status = {}
    else:
        print(f"{AFK_FILE} not found. Starting with empty AFK status.")
        afk_status = {}

def save_afk_status():
    """Saves AFK statuses to a JSON file."""
    with open(AFK_FILE, 'w') as f:
        # Convert integer keys (user IDs) to strings for JSON serialization
        json.dump({str(k): v for k, v in afk_status.items()}, f, indent=4)
        print(f"Saved AFK status: {afk_status}")

def load_automod_settings():
    """Loads AutoMod settings from a JSON file."""
    global automod_settings
    if os.path.exists(AUTOMOD_SETTINGS_FILE):
        with open(AUTOMOD_SETTINGS_FILE, 'r') as f:
            try:
                automod_settings = json.load(f)
                print(f"Loaded AutoMod settings: {automod_settings}")
            except json.JSONDecodeError:
                print(f"Error decoding {AUTOMOD_SETTINGS_FILE}. Starting with default AutoMod settings.")
                # Default settings if file is corrupt or empty
                automod_settings = {
                    "anti_invite_enabled": True,
                    "anti_link_enabled": False,
                    "anti_profanity_enabled": True,
                    "profanity_words": ["badword1", "badword2", "damn", "shit", "fuck", "bitch", "asshole", "cunt", "nigger", "faggot", "retard", "kys", "nigga"],
                    "automod_ignored_channels": [],
                    "automod_ignored_roles": []
                }
    else:
        print(f"{AUTOMOD_SETTINGS_FILE} not found. Starting with default AutoMod settings.")
        # Default settings if file doesn't exist
        automod_settings = {
            "anti_invite_enabled": True,
            "anti_link_enabled": False,
            "anti_profanity_enabled": True,
            "profanity_words": ["badword1", "badword2", "damn", "shit", "fuck", "bitch", "asshole", "cunt", "nigger", "faggot", "retard", "kys", "nigga"],
            "automod_ignored_channels": [],
            "automod_ignored_roles": []
        }

def save_automod_settings():
    """Saves AutoMod settings to a JSON file."""
    with open(AUTOMOD_SETTINGS_FILE, 'w') as f:
        json.dump(automod_settings, f, indent=4)
        print(f"Saved AutoMod settings: {automod_settings}")

# --- Helper to send DMs ---
async def _send_dm_to_member(member: discord.Member, message: str):
    """
    Attempts to send a direct message to a member.
    Handles cases where DMs might be disabled.
    """
    try:
        await member.send(message)
        print(f"DEBUG: Sent DM to {member.name} ({member.id}).")
    except discord.Forbidden:
        print(f"DEBUG: Could not send DM to {member.name} ({member.id}). DMs might be disabled.")
    except Exception as e:
        print(f"DEBUG: An error occurred while sending DM to {member.name} ({member.id}): {e}")

# Refactor warn logic into a reusable function
async def _perform_warn(guild: discord.Guild, channel: discord.TextChannel, member: discord.Member, moderator: discord.Member, reason: str):
    """
    Performs the warning action: adds to warnings, saves, sends message, logs.
    """
    if member.id not in user_warnings:
        user_warnings[member.id] = []
    user_warnings[member.id].append(reason)
    save_warnings() # Save warnings after modification

    await channel.send(f'{member.mention} has been warned by {moderator.mention} for: {reason}. They now have {len(user_warnings[member.id])} warning(s).')
    await log_moderation_action(guild, "Warn", member, moderator, reason)
    await _send_dm_to_member(member, f'You have been warned in {guild.name} for: {reason}')


# --- Dynamic Prefix Function ---
async def get_prefix(bot, message):
    """
    Dynamically gets the command prefix for the guild the message originated from.
    Falls back to '_' if no custom prefix is set for the guild.
    """
    if message.guild:
        # Get the custom prefix for the guild, defaulting to '_'
        return guild_prefixes.get(message.guild.id, '_')
    else:
        # For DMs, always use the default prefix
        return '_'

# Initialize the bot with a dynamic command prefix and the defined intents.
# We disable the default help command to create our own custom one.
bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# Emoji for poll reactions (up to 9 options)
poll_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']

# --- Helper Functions for Moderation Logic ---

async def _check_mod_permissions(ctx, member, action_name):
    """
    Checks if the command invoker and the bot have the necessary permissions
    and role hierarchy to perform a moderation action on a target member.
    Returns True if checks pass, False otherwise (and sends appropriate messages).
    """
    if member == ctx.author:
        await ctx.send(f"You cannot {action_name} yourself!")
        return False
    if member == bot.user:
        await ctx.send(f"I cannot {action_name} myself!")
        return False
    if member == ctx.guild.owner:
        await ctx.send(f"I cannot {action_name} the server owner.")
        return False
    
    # Bot's role must be higher than the target member's top role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot {action_name} {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return False
    
    # Moderator's role must be higher than the target member's top role (unless moderator is guild owner)
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(f"You cannot {action_name} someone with an equal or higher role than you.")
        return False
    
    return True

async def _confirm_action(ctx_or_interaction: Union[commands.Context, discord.Interaction], message_content: str, timeout: float = 30.0):
    """
    Sends a confirmation message with ✅ and ❌ reactions and waits for user input.
    Returns True if confirmed, False if cancelled or timed out.
    Handles both Context and Interaction objects for sending messages.
    """
    is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
    confirm_message = None

    try:
        if is_interaction:
            # For interactions, send the initial message via followup to allow for reactions
            # and then fetch the message to add reactions.
            # ephemeral=False means the message is visible to everyone, allowing reactions.
            confirm_message = await ctx_or_interaction.followup.send(f"{message_content} React with ✅ to confirm or ❌ to cancel.", wait=True)
            # wait=True ensures the message is sent and we get the message object back
        else:
            # For regular commands, use ctx.send
            confirm_message = await ctx_or_interaction.send(f"{message_content} React with ✅ to confirm or ❌ to cancel.")

        await confirm_message.add_reaction('✅')
        await confirm_message.add_reaction('❌')

        def check(reaction, user):
            # The user checking is always the original author for the command/interaction
            author_id = ctx_or_interaction.author.id if not is_interaction else ctx_or_interaction.user.id
            return user.id == author_id and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

        reaction, user = await bot.wait_for('reaction_add', timeout=timeout, check=check)
        await confirm_message.delete()

        if str(reaction.emoji) == '✅':
            return True
        else:
            if is_interaction:
                await ctx_or_interaction.followup.send("Action cancelled.", ephemeral=True)
            else:
                await ctx_or_interaction.send("Action cancelled.")
            return False
    except asyncio.TimeoutError:
        if confirm_message:
            await confirm_message.delete()
        if is_interaction:
            await ctx_or_interaction.followup.send("Action confirmation timed out. Action cancelled.", ephemeral=True)
        else:
            await ctx_or_interaction.send("Action confirmation timed out. Action cancelled.")
        return False
    except Exception as e:
        if confirm_message:
            await confirm_message.delete()
        if is_interaction:
            await ctx_or_interaction.followup.send(f"An error occurred during confirmation: `{e}`", ephemeral=True)
        else:
            await ctx_or_interaction.send(f"An error occurred during confirmation: `{e}`")
        print(f"DEBUG: Error in _confirm_action: {e}")
        return False

async def log_moderation_action(guild, action_type, target, moderator, reason):
    """
    Logs moderation actions to the designated moderation log channel.
    Target can be a Member, User, Channel, or Role object.
    """
    if guild.id not in mod_log_channels:
        print(f"DEBUG: No mod log channel set for guild {guild.name}. Skipping log.")
        return

    log_channel_id = mod_log_channels[guild.id]
    log_channel = guild.get_channel(log_channel_id)

    if not log_channel:
        print(f"DEBUG: Mod log channel with ID {log_channel_id} not found in guild {guild.name}. It might have been deleted. Skipping log.")
        # In a persistent setup, you'd remove this ID from storage here if it's no longer valid.
        return

    embed = discord.Embed(
        title=f"🚨 {action_type} Action",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    # Determine how to display the target based on its type
    if isinstance(target, (discord.Member, discord.User)):
        embed.add_field(name="Target User", value=f"{target.mention} (`{target.id}`)", inline=False)
    elif isinstance(target, (discord.TextChannel, discord.VoiceChannel)):
        embed.add_field(name="Target Channel", value=f"{target.mention if isinstance(target, discord.TextChannel) else target.name} (`{target.id}`)", inline=False)
    elif isinstance(target, discord.Role):
        embed.add_field(name="Target Role", value=f"{target.name} (`{target.id}`)", inline=False)
    else:
        embed.add_field(name="Target", value=str(target), inline=False) # Fallback for other types

    embed.add_field(name="Moderator", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)

    try:
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        print(f"DEBUG: Bot does not have permission to send messages to the mod log channel ({log_channel.name}) in guild {guild.name}. Check bot permissions.")
    except Exception as e:
        print(f"DEBUG: An error occurred while logging moderation action to channel {log_channel.name}: {e}")

# --- AutoMod Helper Functions ---

def _is_discord_invite(message_content: str):
    """Checks if the message contains a Discord invite link."""
    return re.search(r'(discord\.gg/|discordapp\.com/invite/|discord\.com/invite/)[\w-]+', message_content, re.IGNORECASE)

def _contains_link(message_content: str):
    """Checks if the message contains any http/https link."""
    # This regex is broad and might catch things like "example.com" without http/s
    # For more strict link detection, a more complex regex is needed.
    # We'll exclude discord.gg links if anti_invite is enabled to avoid double flagging.
    if automod_settings["anti_invite_enabled"] and _is_discord_invite(message_content): # Changed message.content to message_content
        return False # Handled by anti_invite
    # Updated regex to be more specific to actual URLs
    return re.search(r'https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message_content, re.IGNORECASE)

def _contains_profanity(message_content: str):
    """Checks if the message contains profanity from the defined list."""
    # Create a single regex pattern for all profanity words for efficiency
    # Sort words by length descending to match longer words first if they contain shorter ones
    sorted_words = sorted(automod_settings["profanity_words"], key=len, reverse=True)
    pattern = r'\b(?:' + '|'.join(re.escape(word) for word in sorted_words) + r')\b'
    return re.search(pattern, message_content, re.IGNORECASE)


# --- Bot Events ---

@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected to Discord.
    Loads persistent data (prefixes, warnings, mod log channels, AFK status, AutoMod settings).
    Starts the background task for changing bot status.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    load_prefixes()
    load_warnings()
    load_mod_log_channels()
    load_afk_status() # Load AFK status on startup
    load_automod_settings() # Load AutoMod settings on startup
    change_status.start() # Start the background task
    print('Bot is ready!')

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for commands.
    Catches common errors like missing permissions (both user and bot),
    missing arguments, and invalid arguments, and command cooldowns.
    """
    # Check if the error is already handled by a local command error handler
    if hasattr(ctx.command, 'on_error'):
        return

    # User-related errors
    if isinstance(error, commands.MissingPermissions):
        missing_perms = ', '.join(error.missing_permissions)
        await ctx.send(f"Sorry, {ctx.author.mention}, you don't have the necessary permissions to use this command. You need: `{missing_perms}`")
    elif isinstance(error, commands.MissingRequiredArgument):
        # Dynamically construct usage info from command help or usage attribute
        usage_info = ""
        if hasattr(ctx.command, 'usage') and ctx.command.usage:
            usage_info = f"Usage: `{ctx.command.usage.format(prefix=ctx.prefix)}`"
        elif ctx.command.help and 'Usage: ' in ctx.command.help:
            # Extract usage from help string if it follows "Usage: "
            help_parts = ctx.command.help.split('Usage: ')
            if len(help_parts) > 1:
                usage_info = f"Usage: `{ctx.prefix}{ctx.command.name} {help_parts[-1].strip()}`"
            else: # Fallback if "Usage: " is not explicitly in help
                usage_info = f"Usage: `{ctx.prefix}{ctx.command.name} <arguments>`"
        else:
            usage_info = f"Usage: `{ctx.prefix}{ctx.command.name} <arguments>` (Refer to `{ctx.prefix}help {ctx.command.name}` for details)"
        await ctx.send(f"Missing arguments for the command. {usage_info}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument provided. Please check the command usage and ensure you're providing valid inputs (e.g., mentioning a user, providing a number).")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Please try again in {error.retry_after:.2f} seconds.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(f"Could not find member: `{error.argument}`. Please ensure you've mentioned a valid member or provided a correct ID/name.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send(f"Could not find channel: `{error.argument}`. Please ensure you've mentioned a valid channel or provided a correct ID/name.")
    elif isinstance(error, commands.RoleNotFound):
        await ctx.send(f"Could not find role: `{error.argument}`. Please ensure you've provided a correct role name or ID.")
    elif isinstance(error, commands.EmojiNotFound):
        await ctx.send(f"Could not find emoji: `{error.argument}`. Please ensure you've provided a valid emoji (either custom or Unicode).")

    # Bot-related errors
    elif isinstance(error, commands.BotMissingPermissions):
        missing_perms = ', '.join(error.missing_permissions)
        await ctx.send(f"I don't have the necessary permissions to perform this action. Please ensure I have: `{missing_perms}`. Also, make sure my role is higher than the target user's role and any roles I need to manage.")

    # Other errors
    elif isinstance(error, commands.CommandNotFound):
        # Silently ignore if command not found to avoid spamming chat with errors for typos
        pass
    else:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred in command '{ctx.command.name}': {error}")
        await ctx.send(f"An unexpected error occurred while processing your command: `{e}`. Please try again or contact an administrator if the issue persists.")

@bot.event
async def on_message(message):
    """
    Processes messages to check for AFK users and bot mentions,
    and applies automod rules.
    """
    if message.author.bot: # Ignore bot messages
        return

    # Check if automod should ignore this channel or user's roles
    if message.guild: # AutoMod only applies in guilds
        # Exclude administrators from AutoMod checks
        if message.author.guild_permissions.administrator:
            await bot.process_commands(message)
            return

        if message.channel.id in automod_settings["automod_ignored_channels"]:
            await bot.process_commands(message) # Still process commands in ignored channels
            return
        for role in message.author.roles:
            if role.id in automod_settings["automod_ignored_roles"]:
                await bot.process_commands(message) # Still process commands for ignored roles
                return

        # --- AutoMod Checks ---
        if automod_settings["anti_invite_enabled"] and _is_discord_invite(message.content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, Discord invite links are not allowed here!", delete_after=5)
                await _perform_warn(message.guild, message.channel, message.author, bot.user, reason="Posted Discord invite link (AutoMod)")
            except discord.Forbidden:
                await message.channel.send(f"AutoMod: I lack permissions to delete messages or warn {message.author.mention}. Please grant 'Manage Messages' and 'Kick Members' permissions.", delete_after=10)
            return # Stop further processing

        if automod_settings["anti_link_enabled"] and _contains_link(message.content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, external links are not allowed here!", delete_after=5)
                await _perform_warn(message.guild, message.channel, message.author, bot.user, reason="Posted external link (AutoMod)")
            except discord.Forbidden:
                await message.channel.send(f"AutoMod: I lack permissions to delete messages or warn {message.author.mention}. Please grant 'Manage Messages' and 'Kick Members' permissions.", delete_after=10)
            return # Stop further processing

        if automod_settings["anti_profanity_enabled"] and _contains_profanity(message.content):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, please watch your language!", delete_after=5)
                await _perform_warn(message.guild, message.channel, message.author, bot.user, reason="Used profanity (AutoMod)")
            except discord.Forbidden:
                await message.channel.send(f"AutoMod: I lack permissions to delete messages or warn {message.author.mention}. Please grant 'Manage Messages' and 'Kick Members' permissions.", delete_after=10)
            return # Stop further processing

    # --- Bot Mention Reply ---
    # Check if the bot is mentioned and it's not a reply to the bot's own message
    if bot.user.mentioned_in(message) and (not message.reference or message.reference.resolved.author != bot.user):
        current_prefix = await bot.command_prefix(bot, message)
        embed = discord.Embed(
            description=f"My prefix here is `{current_prefix}`. Use `{current_prefix}help` to see all commands!",
            color=discord.Color.blue()
        )
        await message.reply(embed=embed, mention_author=False)
        # Do not return here, allow other on_message logic and command processing to continue

    # --- AFK Status Handling ---
    # Check if the author is AFK and remove their status
    if message.author.id in afk_status:
        del afk_status[message.author.id]
        save_afk_status()
        await message.channel.send(f"Welcome back {message.author.mention}! I've removed your AFK status.")
        
        # Check for any pending mentions (simplified for now)
        # In a more advanced system, you might DM the AFK user a summary of mentions.

    # Check for mentions of AFK users
    for member in message.mentions:
        if member.id in afk_status:
            afk_info = afk_status[member.id]
            afk_message = afk_info.get("message", "No AFK message provided.")
            afk_time_str = afk_info.get("time", "unknown time")

            # Create an embed for the AFK reply
            embed = discord.Embed(
                title=f"💤 {member.display_name} is AFK!",
                description=f"**Reason:** {afk_message}\n**Since:** {afk_time_str}",
                color=discord.Color.from_rgb(173, 216, 230), # Light blue color
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text=f"Mentioned by {message.author.display_name}")
            
            await message.channel.send(embed=embed)
            # Optionally, you could store who mentioned the AFK user
            # if afk_info.get("mentions") is None:
            #     afk_info["mentions"] = []
            # afk_info["mentions"].append(message.author.id)
            # save_afk_status() # Save the updated mentions

    await bot.process_commands(message) # Important: Process commands after AFK checks

# --- Background Task for Status ---
@tasks.loop(minutes=10) # Change status every 10 minutes
async def change_status():
    """Changes the bot's presence (activity/status) periodically."""
    # Set status to Do Not Disturb and activity to watching "SERVERS !!!"
    await bot.change_presence(status=discord.Status.dnd, activity=random.choice(bot_activities))
    # Corrected logging to use bot.status and bot.activity
    print(f"DEBUG: Changed bot status to: {bot.status} and activity to: {bot.activity.name if bot.activity else 'None'}")


# --- General Utility Commands ---

@bot.command(name='ping', help='Checks the bot\'s latency to Discord. Usage: {prefix}ping')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def ping(ctx):
    """
    Responds with the bot's latency (ping).
    """
    try:
        # Get the current prefix for the guild
        current_prefix = await bot.command_prefix(bot, ctx.message)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{round(bot.latency * 1000)}ms**",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Current Prefix", value=f"`{current_prefix}`", inline=False)
        embed.set_footer(text=f"Use {current_prefix}help for a list of commands.")
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"An error occurred while checking ping: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}ping command: {e}")

# --- Custom Help Command with Buttons ---
class HelpView(discord.ui.View):
    def __init__(self, bot_instance, categories):
        super().__init__(timeout=60) # View will expire after 60 seconds of inactivity
        self.bot = bot_instance
        self.categories = categories
        self.current_page = "main" # Start on the main page

        # Dynamically add buttons for each category
        # Assign a generic callback to these buttons
        # The row argument helps with layout, distributing buttons across rows
        for i, category_name in enumerate(self.categories.keys()):
            # Place 2 buttons per row (0-1 on row 0, 2-3 on row 1, etc.)
            row_index = i // 2
            button = discord.ui.Button(label=category_name, custom_id=f"help_category_{category_name}", style=discord.ButtonStyle.primary, row=row_index)
            button.callback = self._handle_category_button_click
            self.add_item(button)

        # The "Back to Categories" and "Close Help" buttons are added via their decorators below.
        # Do NOT add them again here with self.add_item() as that causes duplicates.

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who invoked the command to interact with the buttons
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You can only interact with your own help menu!", ephemeral=True)
            return False
        return True

    async def send_initial_message(self, ctx):
        self.ctx = ctx # Store the context for later use
        embed = discord.Embed(
            title="Bot Commands Categories",
            description="Click a button below to view commands in that category.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        self.message = await ctx.send(embed=embed, view=self)

    # The @discord.ui.button decorator for back_to_main is still needed as it's a fixed button.
    @discord.ui.button(label="Back to Categories", style=discord.ButtonStyle.secondary, custom_id="help_back_to_main", row=4)
    async def back_to_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "main"
        embed = discord.Embed(
            title="Bot Commands Categories",
            description="Click a button below to view commands in that category.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {self.ctx.author.display_name}")
        # Re-enable category buttons, disable back button
        for item in self.children:
            if item.custom_id.startswith("help_category_"):
                item.disabled = False
            elif item.custom_id == "help_back_to_main":
                item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    # The @discord.ui.button decorator for close_help is still needed as it's a fixed button.
    @discord.ui.button(label="Close Help", style=discord.ButtonStyle.danger, custom_id="help_close", row=4)
    async def close_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Help menu closed.", embed=None, view=None)
        self.stop() # Stop the view

    async def _handle_category_button_click(self, interaction: discord.Interaction):
        """
        Generic callback for all category buttons.
        Determines the category from the button's custom_id and displays commands.
        """
        # Access custom_id from interaction.data dictionary to avoid AttributeError
        category_name = interaction.data['custom_id'].replace("help_category_", "")
        self.current_page = category_name

        embed = discord.Embed(
            title=f"{category_name} Commands",
            description=f"Commands for {category_name.lower()}.",
            color=discord.Color.blue() # You can customize colors per category if desired
        )
        for cmd_name in self.categories[category_name]:
            command = self.bot.get_command(cmd_name)
            if command and not command.hidden:
                embed.add_field(name=f"`{self.ctx.prefix}{command.name}`", value=command.help.format(prefix=self.ctx.prefix), inline=False)
        embed.set_footer(text=f"Requested by {self.ctx.author.display_name}")

        # Disable category buttons, enable back button
        for item in self.children:
            if item.custom_id.startswith("help_category_"):
                item.disabled = True
            elif item.custom_id == "help_back_to_main":
                item.disabled = False
        await interaction.response.edit_message(embed=embed, view=self)


# Define command categories
COMMAND_CATEGORIES = {
    "Moderation": [
        "kick", "ban", "unban", "mute", "unmute", "purge", "warn",
        "warnings", "unwarn", "clearwarnings", "softban", "slowmode", "lock",
        "unlock", "timeout", "untimeout", "mass_kick", "mass_ban", "warns_clear_all", "clear", "punish"
    ],
    "Server Management": [
        "create_role", "delete_role", "create_channel", "delete_channel",
        "setmodlog", "nick", "setprefix", "set_channel_topic", "mass_role",
        "add_role_to_all", "remove_role_from_all", "add_role_to_member", "remove_role_from_member"
    ],
    "Utility": [
        "ping", "userinfo", "serverinfo", "announce", "poll", "dm",
        "channel_info", "role_info", "avatar", "afk", "remindme"
    ],
    "Voice Chat": [
        "move_member", "kick_from_vc", "ban_vc", "unban_vc", "mass_move_vc"
    ],
    "Fun": [
        "8ball", "coinflip", "dice", "fact", "joke", "tictactoe", "meme", "kill", "slap" # Added "kill" and "slap" here
    ],
    "AutoMod": [
        "automod", "add_bad_word", "remove_bad_word", "list_bad_words" # Added new AutoMod commands
    ]
}

@bot.command(name='help', help='Displays all available commands and their usage. Usage: {prefix}help')
@commands.cooldown(1, 5, commands.BucketType.user)
async def help_command(ctx):
    """
    Displays an interactive help menu with categorized commands.
    """
    view = HelpView(bot, COMMAND_CATEGORIES)
    await view.send_initial_message(ctx)

@bot.command(name='setprefix', help='Sets a custom command prefix for this server. Usage: {prefix}setprefix <new_prefix>')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 10, commands.BucketType.guild)
async def set_prefix(ctx, new_prefix: str):
    """
    Sets a custom command prefix for the current server.
    Requires 'Administrator' permission.
    The new prefix must be a single character or a short string.
    """
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    if not new_prefix:
        await ctx.send("The new prefix cannot be empty. Please provide a valid prefix.")
        return

    if len(new_prefix) > 5: # Limit prefix length to prevent abuse
        await ctx.send("The new prefix cannot be longer than 5 characters.")
        return

    try:
        guild_prefixes[ctx.guild.id] = new_prefix
        save_prefixes() # Save the updated prefixes to file
        await ctx.send(f"The command prefix for this server has been set to `{new_prefix}`. You can now use commands like `{new_prefix}help`.")
        await log_moderation_action(ctx.guild, "Prefix Change", "Server", ctx.author, f"Prefix changed to '{new_prefix}'")
    except discord.Forbidden:
        await ctx.send("I don't have permission to update server settings. Please check my permissions.")
        print(f"DEBUG: Bot missing permissions to change prefix in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to set the prefix: `{e}`")
        print(f"DEBUG: HTTPException during setprefix: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to set the prefix: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}setprefix command: {e}")


# --- Moderation Commands ---

@bot.command(name='kick', help='Kicks a member from the server. Usage: {prefix}kick <member> [reason]')
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Kicks the specified member from the server.
    Requires 'Kick Members' permission for the user.
    """
    if not await _check_mod_permissions(ctx, member, "kick"):
        return

    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Kick", member, ctx.author, reason)
        await _send_dm_to_member(member, f'You have been kicked from {ctx.guild.name} for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to kick {member.mention}. Please ensure my role is higher than theirs and I have the 'Kick Members' permission.")
        print(f"DEBUG: Bot missing permissions to kick {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to kick {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during kick for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to kick: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}kick command for {member.name}: {e}")

@bot.command(name='ban', help='Bans a member from the server. Usage: {prefix}ban <member> [reason]')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.user)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Bans the specified member from the server.
    Requires 'Ban Members' permission for the user.
    Includes a confirmation step.
    """
    if not await _check_mod_permissions(ctx, member, "ban"):
        return

    confirmation_message = f"Are you sure you want to ban {member.mention} for: `{reason}`?"
    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        await member.ban(reason=reason, delete_message_days=0) # delete_message_days=0 means no messages are deleted
        await ctx.send(f'{member.mention} has been banned by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Ban", member, ctx.author, reason)
        await _send_dm_to_member(member, f'You have been banned from {ctx.guild.name} for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to ban {member.mention}. Please ensure my role is higher than theirs and I have the 'Ban Members' permission.")
        print(f"DEBUG: Bot missing permissions to ban {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to ban {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during ban for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to ban: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}ban command for {member.name}: {e}")


@bot.command(name='unban', help='Unbans a user by their name and discriminator (e.g., {prefix}unban User#1234) or User ID. Usage: {prefix}unban <User ID or Username#Discriminator>')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def unban(ctx, *, member_id_or_name: str):
    """
    Unbans a user from the server.
    Requires 'Ban Members' permission for the user.
    Can unban by user ID or by username#discriminator.
    """
    try:
        banned_users = [entry async for entry in ctx.guild.bans()] # Get all banned users

        # Try to unban by ID first
        try:
            member_id = int(member_id_or_name)
            for ban_entry in banned_users:
                user = ban_entry.user
                if user.id == member_id:
                    await ctx.guild.unban(user)
                    await ctx.send(f'{user.mention} has been unbanned by {ctx.author.mention}.')
                    await log_moderation_action(ctx.guild, "Unban", user, ctx.author, "Manual unban")
                    return
        except ValueError:
            pass # Not an integer ID, proceed to check by name#discriminator

        # If not found by ID, try to unban by name#discriminator
        for ban_entry in banned_users:
            user = ban_entry.user
            if str(user) == member_id_or_name:
                await ctx.guild.unban(user)
                await ctx.send(f'{user.mention} has been unbanned by {ctx.author.mention}.')
                await log_moderation_action(ctx.guild, "Unban", user, ctx.author, "Manual unban")
                return

        await ctx.send(f'Could not find a banned user with ID or name "{member_id_or_name}".')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to unban users. Please ensure I have the 'Ban Members' permission.")
        print(f"DEBUG: Bot missing permissions to unban in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to unban: `{e}`")
        print(f"DEBUG: HTTPException during unban: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unban: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unban command for {member_id_or_name}: {e}")

@bot.command(name='mute', help='Mutes a member for a specified duration (in minutes). Usage: {prefix}mute <member> <duration_minutes> [reason]')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def mute(ctx, member: discord.Member, duration_minutes: int, *, reason: str = "No reason provided"):
    """
    Mutes the specified member for a given duration.
    Requires 'Manage Roles' permission for the user.
    This command assumes you have a role named 'Muted' set up on your server
    that denies 'Send Messages' permission in all channels.
    """
    if not await _check_mod_permissions(ctx, member, "mute"):
        return

    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

    if not muted_role:
        await ctx.send("The 'Muted' role was not found. Please create a role named 'Muted' and configure its permissions to deny 'Send Messages' in all channels.")
        return

    # Check if the bot's role is higher than the muted role it's trying to assign
    if ctx.guild.me.top_role <= muted_role:
        await ctx.send(f"I cannot assign the '{muted_role.name}' role because my highest role is not above it. Please ensure my role is higher than the 'Muted' role.")
        return

    if muted_role in member.roles:
        await ctx.send(f"{member.mention} is already muted.")
        return

    try:
        await member.add_roles(muted_role, reason=reason)
        await ctx.send(f'{member.mention} has been muted by {ctx.author.mention} for {duration_minutes} minutes for: {reason}')
        await log_moderation_action(ctx.guild, "Mute", member, ctx.author, reason)
        await _send_dm_to_member(member, f'You have been muted in {ctx.guild.name} for {duration_minutes} minutes for: {reason}')

        # Schedule the unmute
        await asyncio.sleep(duration_minutes * 60) # Convert minutes to seconds
        if muted_role in member.roles: # Check if they are still muted after the duration
            try:
                await member.remove_roles(muted_role, reason="Mute duration expired")
                await ctx.send(f'{member.mention} has been unmuted automatically after {duration_minutes} minutes.')
                await log_moderation_action(ctx.guild, "Unmute (Auto)", member, bot.user, "Mute duration expired")
                await _send_dm_to_member(member, f'You have been unmuted in {ctx.guild.name}.')
            except discord.Forbidden:
                print(f"DEBUG: Bot missing permissions to auto-unmute {member.name} in guild {ctx.guild.name}.")
            except discord.HTTPException as e:
                print(f"DEBUG: HTTPException during auto-unmute for {member.name}: {e}")
            except Exception as e:
                print(f"DEBUG: An unexpected error occurred while trying to automatically unmute {member.mention}: `{e}`")

    except discord.Forbidden:
        await ctx.send(f"I don't have permission to assign roles to {member.mention}. Please ensure my role is higher than the 'Muted' role and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to mute {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to mute {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during mute for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to mute: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}mute command for {member.name}: {e}")

@bot.command(name='unmute', help='Unmutes a member. Usage: {prefix}unmute <member> [reason]')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def unmute(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Unmutes the specified member.
    Requires 'Manage Roles' permission for the user.
    """
    # No need for _check_mod_permissions here as it's removing a role, not directly affecting hierarchy in the same way.
    # However, we still need to check bot's role vs muted_role.

    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")

    if not muted_role:
        await ctx.send("The 'Muted' role was not found. Please create a role named 'Muted'.")
        return

    # Check if the bot's role is higher than the muted role it's trying to remove
    if ctx.guild.me.top_role <= muted_role:
        await ctx.send(f"I cannot remove the '{muted_role.name}' role because my highest role is not above it. Please ensure my role is higher than the 'Muted' role.")
        return

    if muted_role not in member.roles:
        await ctx.send(f"{member.mention} is not currently muted.")
        return

    try:
        await member.remove_roles(muted_role, reason=reason)
        await ctx.send(f'{member.mention} has been unmuted by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Unmute", member, ctx.author, reason)
        await _send_dm_to_member(member, f'You have been unmuted in {ctx.guild.name}.')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to remove roles from {member.mention}. Please ensure my role is higher than the 'Muted' role and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to unmute {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to unmute {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during unmute for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unmute: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unmute command for {member.name}: {e}")

@bot.command(name='purge', help='Clears a specified number of messages from the channel, optionally from a specific member. Messages older than 30 days cannot be purged. Usage: {prefix}purge <amount> OR {prefix}purge <member> <amount>')
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.channel) # 1 use per 5 seconds per channel
async def purge(ctx, member_or_amount: Union[discord.Member, int], amount: int = None):
    """
    Clears messages from the current channel.
    If a member is specified, clears messages only from that member.
    If only an amount is specified, clears general messages.
    Messages older than 30 days cannot be purged.
    Requires 'Manage Messages' permission for the user.
    Includes a confirmation step.
    """
    target_member = None
    if isinstance(member_or_amount, discord.Member):
        target_member = member_or_amount
        if amount is None: # Now mandatory if member is specified
            await ctx.send("When purging messages from a specific member, you must specify the number of messages to purge. Usage: `{prefix}purge <member> <amount>`".format(prefix=ctx.prefix))
            return
    else: # It's an amount if not a member
        amount = member_or_amount

    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to purge.")
        return
    if amount > 1000: # Practical limit to prevent excessive fetching/deletion and potential rate limits
        await ctx.send("You can purge a maximum of 1000 messages at once.")
        return

    # Discord API generally restricts bulk deletion to messages younger than 14 days.
    # We'll set a check for 30 days, but Discord's API will still enforce its own limits.
    fourteen_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)

    if target_member:
        confirmation_message = f"Are you sure you want to purge {amount} messages from {target_member.mention} in this channel? (Note: Discord only allows bulk deletion of messages up to 14 days old.)"
    else:
        confirmation_message = f"Are you sure you want to purge {amount} messages in this channel? (Note: Discord only allows bulk deletion of messages up to 14 days old.)"

    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        # Add 1 to limit to account for the command message itself.
        # The confirmation message is deleted by _confirm_action.
        def is_target_message(message):
            # Only delete messages within the 14-day window for bulk deletion
            return (message.author == target_member if target_member else True) and message.created_at > fourteen_days_ago

        # Fetch messages, including the command message itself, but excluding the confirmation message
        # We fetch one more than 'amount' to potentially include the command message if it's not deleted by _confirm_action's prompt.
        # However, since _confirm_action deletes its own message, we only need to worry about ctx.message here.
        # The purge function itself will remove the command message if it's within the limit.
        deleted = await ctx.channel.purge(limit=amount + 1, check=is_target_message, before=datetime.datetime.now(datetime.timezone.utc))
        
        # Adjust count if the command message was among those deleted
        actual_deleted_count = len(deleted)
        if ctx.message in deleted:
            actual_deleted_count -= 1 # The command message itself

        if actual_deleted_count < 0: # Should not happen, but a safeguard
            actual_deleted_count = 0

        if target_member:
            await ctx.send(f'Successfully purged {actual_deleted_count} messages from {target_member.mention}.', delete_after=5)
            log_reason = f"{actual_deleted_count} messages purged from {target_member.name}"
        else:
            await ctx.send(f'Successfully purged {actual_deleted_count} messages.', delete_after=5)
            log_reason = f"{actual_deleted_count} messages purged"
        
        await log_moderation_action(ctx.guild, "Purge Messages", ctx.channel, ctx.author, log_reason)
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage messages in this channel. Please ensure I have the 'Manage Messages' permission.")
        print(f"DEBUG: Bot missing permissions to purge messages in channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to purge messages: `{e}`")
        print(f"DEBUG: HTTPException during purge: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to purge messages: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}purge command: {e}")


@bot.command(name='warn', help='Warns a member. Usage: {prefix}warn <member> [reason]')
@commands.has_permissions(kick_members=True) # Or a custom role for moderators
@commands.cooldown(1, 3, commands.BucketType.user)
async def warn_command(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Warns the specified member. Warnings are stored persistently.
    """
    if not await _check_mod_permissions(ctx, member, "warn"):
        return
    
    await _perform_warn(ctx.guild, ctx.channel, member, ctx.author, reason)


@bot.command(name='unwarn', help='Removes a specific warning from a member by its number. Usage: {prefix}unwarn <member> <warning_number>')
@commands.has_permissions(kick_members=True) # Or a custom role for moderators
@commands.cooldown(1, 3, commands.BucketType.user)
async def unwarn(ctx, member: discord.Member, warning_number: int):
    """
    Removes a specific warning from the specified member by its number.
    Warning numbers start from 1.
    """
    if member.id not in user_warnings or not user_warnings[member.id]:
        await ctx.send(f'{member.mention} has no warnings to remove.')
        return

    if not 1 <= warning_number <= len(user_warnings[member.id]):
        await ctx.send(f"Invalid warning number. {member.mention} has {len(user_warnings[member.id])} warning(s). Please choose a number between 1 and {len(user_warnings[member.id])}.")
        return

    try:
        removed_reason = user_warnings[member.id].pop(warning_number - 1) # Adjust for 0-based indexing
        save_warnings() # Save warnings after modification
        await ctx.send(f'Removed warning #{warning_number} from {member.mention}: "{removed_reason}". They now have {len(user_warnings[member.id])} warning(s).')
        await log_moderation_action(ctx.guild, "Unwarn", member, ctx.author, f"Removed warning #{warning_number}: '{removed_reason}'")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to remove warning: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unwarn command for {member.name}: {e}")


@bot.command(name='warnings', help='Shows the warnings for a member. Usage: {prefix}warnings <member>')
@commands.has_permissions(kick_members=True) # Or a custom role for moderators
@commands.cooldown(1, 5, commands.BucketType.user)
async def show_warnings(ctx, member: discord.Member):
    """
    Shows the warnings for the specified member.
    """
    try:
        if member.id not in user_warnings or not user_warnings[member.id]:
            await ctx.send(f'{member.mention} has no warnings.')
            return

        warnings_list = "\n".join([f"{i+1}. {w}" for i, w in enumerate(user_warnings[member.id])])
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            description=warnings_list,
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to show warnings: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}warnings command for {member.name}: {e}")

@bot.command(name='clearwarnings', help='Clears all warnings for a member. Usage: {prefix}clearwarnings <member>')
@commands.has_permissions(ban_members=True) # Higher permission for clearing warnings
@commands.cooldown(1, 5, commands.BucketType.user)
async def clear_warnings(ctx, member: discord.Member):
    """
    Clears all warnings for the specified member.
    """
    try:
        if member.id in user_warnings:
            del user_warnings[member.id]
            save_warnings() # Save warnings after modification
            await ctx.send(f'All warnings for {member.mention} have been cleared.')
            await log_moderation_action(ctx.guild, "Clear Warnings", member, ctx.author, "All warnings cleared")
        else:
            await ctx.send(f'{member.mention} has no warnings to clear.')
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to clear warnings: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}clearwarnings command for {member.name}: {e}")

@bot.command(name='softban', help='Kicks a member and deletes their messages from the last X days. Usage: {prefix}softban <member> <days> [reason]')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.user)
async def softban(ctx, member: discord.Member, days: int = 0, *, reason: str = "No reason provided"):
    """
    Softbans a member (kicks and deletes messages from the last 'days' days).
    Requires 'Ban Members' permission for the user.
    """
    if not await _check_mod_permissions(ctx, member, "softban"):
        return

    try:
        # Ban the member, deleting messages for 'days'
        await member.ban(reason=reason, delete_message_days=days)
        # Immediately unban them to achieve the "kick with message deletion" effect
        await ctx.guild.unban(member, reason="Softban: immediate unban after message deletion")
        await ctx.send(f'{member.mention} has been softbanned by {ctx.author.mention} (kicked and messages from last {days} days deleted) for: {reason}')
        await log_moderation_action(ctx.guild, "Softban", member, ctx.author, reason)
        await _send_dm_to_member(member, f'You have been softbanned from {ctx.guild.name} (kicked and messages from last {days} days deleted) for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to softban {member.mention}. Please ensure my role is higher than theirs and I have the 'Ban Members' permission.")
        print(f"DEBUG: Bot missing permissions to softban {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to softban {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during softban: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to softban: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}softban command for {member.name}: {e}")

@bot.command(name='slowmode', help='Sets slowmode on the current channel (in seconds). Usage: {prefix}slowmode <seconds>')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.channel)
async def slowmode(ctx, seconds: int):
    """
    Sets the slowmode delay for the current channel.
    Requires 'Manage Channels' permission for the user.
    """
    if not 0 <= seconds <= 21600: # Discord's limit for slowmode is 6 hours (21600 seconds)
        await ctx.send("Slowmode delay must be between 0 and 21600 seconds (6 hours).")
        return

    try:
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("Slowmode has been disabled for this channel.")
            await log_moderation_action(ctx.guild, "Slowmode Disabled", ctx.channel, ctx.author, "Slowmode disabled")
        else:
            await ctx.send(f"Slowmode set to {seconds} seconds for this channel.")
            await log_moderation_action(ctx.guild, "Slowmode Enabled", ctx.channel, ctx.author, f"Slowmode set to {seconds}s")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channels. Please ensure I have the 'Manage Channels' permission.")
        print(f"DEBUG: Bot missing permissions to set slowmode in channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to set slowmode: `{e}`")
        print(f"DEBUG: HTTPException during slowmode: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to set slowmode: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}slowmode command: {e}")

@bot.command(name='lock', aliases=['channel_lockdown'], help='Locks down the current channel, preventing @everyone from sending messages. Usage: {prefix}lock [reason]')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.channel)
async def lock(ctx, *, reason: str = "No reason provided"):
    """
    Locks down the current channel, preventing @everyone from sending messages.
    Requires 'Manage Channels' permission for the user.
    """
    # Get the @everyone role
    everyone_role = ctx.guild.default_role

    # Check if the channel is already locked down
    if ctx.channel.overwrites_for(everyone_role).send_messages is False:
        await ctx.send("This channel is already locked down.")
        return

    try:
        # Set permissions to deny sending messages for @everyone
        await ctx.channel.set_permissions(everyone_role, send_messages=False, reason=reason)
        await ctx.send(f'Channel has been locked down by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Channel Lockdown", ctx.channel, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channel permissions. Please ensure I have the 'Manage Channels' permission and my role is higher than @everyone's.")
        print(f"DEBUG: Bot missing permissions to lock channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to lock down the channel: `{e}`")
        print(f"DEBUG: HTTPException during lock: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to lock down the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}lock command: {e}")

@bot.command(name='unlock', aliases=['channel_unlock'], help='Unlocks the current channel, allowing @everyone to send messages. Usage: {prefix}unlock [reason]')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.channel)
async def unlock(ctx, *, reason: str = "No reason provided"):
    """
    Unlocks the current channel, allowing @everyone to send messages.
    Requires 'Manage Channels' permission for the user.
    """
    # Get the @everyone role
    everyone_role = ctx.guild.default_role

    # Check if the channel is already unlocked (or doesn't have explicit deny)
    if ctx.channel.overwrites_for(everyone_role).send_messages is None or ctx.channel.overwrites_for(everyone_role).send_messages is True:
        await ctx.send("This channel is not currently locked down.")
        return

    try:
        # Set permissions to allow sending messages for @everyone (or remove the overwrite)
        await ctx.channel.set_permissions(everyone_role, send_messages=None, reason=reason) # None removes the overwrite
        await ctx.send(f'Channel has been unlocked by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Channel Unlock", ctx.channel, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channel permissions. Please ensure I have the 'Manage Channels' permission and my role is higher than @everyone's.")
        print(f"DEBUG: Bot missing permissions to unlock channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to unlock the channel: `{e}`")
        print(f"DEBUG: HTTPException during unlock: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unlock the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unlock command: {e}")

@bot.command(name='timeout', help='Times out a member for a specified duration (e.g., 1h, 30m, 7d). Usage: {prefix}timeout <member> <duration> [reason]')
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def timeout(ctx, member: discord.Member, duration_str: str, *, reason: str = "No reason provided"):
    """
    Times out a member for a specified duration.
    Examples: 1h (1 hour), 30m (30 minutes), 7d (7 days).
    Requires 'Moderate Members' permission for the user and bot.
    """
    if not await _check_mod_permissions(ctx, member, "timeout"):
        return

    # Parse duration string
    delta = None
    try:
        if duration_str.endswith('s'):
            delta = datetime.timedelta(seconds=int(duration_str[:-1]))
        elif duration_str.endswith('m'):
            delta = datetime.timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith('h'):
            delta = datetime.timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith('d'):
            delta = datetime.timedelta(days=int(duration_str[:-1]))
        else:
            await ctx.send("Invalid duration format. Use 's' for seconds, 'm' for minutes, 'h' for hours, or 'd' for days (e.g., `30m`, `1h`, `7d`).")
            return

        if delta.total_seconds() <= 0:
            await ctx.send("Duration must be positive.")
            return
        if delta.total_seconds() > 2419200: # Max timeout duration is 28 days (2,419,200 seconds)
            await ctx.send("Timeout duration cannot exceed 28 days.")
            return

    except ValueError:
        await ctx.send("Invalid duration value. Please provide a number followed by 's', 'm', 'h', or 'd' (e.g., `30m`).")
        return
    except Exception as e:
        await ctx.send(f"An error occurred while parsing the duration: `{e}`")
        print(f"DEBUG: Error parsing timeout duration: {e}")
        return

    try:
        await member.timeout(delta, reason=reason)
        await ctx.send(f'{member.mention} has been timed out by {ctx.author.mention} for {duration_str} for: {reason}')
        await log_moderation_action(ctx.guild, "Timeout", member, ctx.author, f"Duration: {duration_str}, Reason: {reason}")
        await _send_dm_to_member(member, f'You have been timed out in {ctx.guild.name} for {duration_str} for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to timeout {member.mention}. Please ensure my role is higher than theirs and I have the 'Moderate Members' permission.")
        print(f"DEBUG: Bot missing permissions to timeout {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to time out {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during timeout for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to time out: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}timeout command for {member.name}: {e}")

@bot.command(name='untimeout', help='Removes an active timeout from a member. Usage: {prefix}untimeout <member> [reason]')
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def untimeout(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Removes an active timeout from the specified member.
    Requires 'Moderate Members' permission for the user and bot.
    """
    if not await _check_mod_permissions(ctx, member, "untimeout"):
        return
    
    if not member.timed_out:
        await ctx.send(f"{member.mention} is not currently timed out.")
        return

    try:
        await member.timeout(None, reason=reason) # Setting duration to None removes timeout
        await ctx.send(f'Timeout removed from {member.mention} by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Untimeout", member, ctx.author, reason)
        await _send_dm_to_member(member, f'Your timeout in {ctx.guild.name} has been removed for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to remove timeout from {member.mention}. Please ensure my role is higher than theirs and I have the 'Moderate Members' permission.")
        print(f"DEBUG: Bot missing permissions to untimeout {member.name} in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to remove timeout from {member.mention}: `{e}`")
        print(f"DEBUG: HTTPException during untimeout for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to remove timeout: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}untimeout command for {member.name}: {e}")

@bot.command(name='nick', help='Changes a member\'s nickname. Usage: {prefix}nick <member> [new_nickname]')
@commands.has_permissions(manage_nicknames=True)
@commands.bot_has_permissions(manage_nicknames=True) # Bot must have this permission
@commands.cooldown(1, 3, commands.BucketType.user)
async def nick(ctx, member: discord.Member, *, new_nickname: str = None):
    """
    Changes the nickname of the specified member.
    If no new_nickname is provided, it resets the nickname.
    Requires 'Manage Nicknames' permission for the user.
    """
    if member == bot.user:
        await ctx.send("I cannot change my own nickname using this command.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot change the nickname of the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot change {member.mention}'s nickname because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot change the nickname of someone with an equal or higher role than you.")
        return
    if member == ctx.author and new_nickname is None:
        await ctx.send("You cannot reset your own nickname with this command. Use Discord's built-in feature.")
        return

    try:
        old_nickname = member.nick if member.nick else member.name
        await member.edit(nick=new_nickname)
        if new_nickname:
            await ctx.send(f'Changed {old_nickname}\'s nickname to {new_nickname}.')
            await log_moderation_action(ctx.guild, "Nickname Change", member, ctx.author, f"Changed from '{old_nickname}' to '{new_nickname}'")
        else:
            await ctx.send(f'Reset {old_nickname}\'s nickname.')
            await log_moderation_action(ctx.guild, "Nickname Reset", member, ctx.author, f"Reset from '{old_nickname}'")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to change {member.mention}'s nickname. Please ensure my role is higher than theirs and I have the 'Manage Nicknames' permission.")
        print(f"DEBUG: Bot missing permissions to change nickname for {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to change nickname: `{e}`")
        print(f"DEBUG: HTTPException during nick for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to change nickname: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}nick command for {member.name}: {e}")

@bot.command(name='role', help='Adds or removes a role from a member. Usage: {prefix}role <member> <add|remove> <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def role(ctx, member: discord.Member, action: str, *, role_name: str):
    """
    Adds or removes a role from the specified member.
    Requires 'Manage Roles' permission for the user.
    """
    action = action.lower()
    target_role = discord.utils.get(ctx.guild.roles, name=role_name)

    if not target_role:
        await ctx.send(f"Role '{role_name}' not found.")
        return

    if target_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot assign or remove a role that is equal to or higher than your own.")
        return

    # Check if the bot's highest role is lower than or equal to the target role
    if ctx.guild.me.top_role <= target_role:
        await ctx.send(f"I cannot assign or remove the '{target_role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to manage.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot manage roles for the server owner.")
        return

    try:
        if action == 'add':
            if target_role in member.roles:
                await ctx.send(f'{member.mention} already has the role {target_role.name}.')
            else:
                await member.add_roles(target_role, reason=f"Role added by {ctx.author.name}")
                await ctx.send(f'Added role {target_role.name} to {member.mention}.')
                await log_moderation_action(ctx.guild, "Role Added", member, ctx.author, f"Added role: {target_role.name}")
        elif action == 'remove':
            if target_role not in member.roles:
                await ctx.send(f'{member.mention} does not have the role {target_role.name}.')
            else:
                await member.remove_roles(target_role, reason=f"Role removed by {ctx.author.name}")
                await ctx.send(f'Removed role {target_role.name} from {member.mention}.')
                await log_moderation_action(ctx.guild, "Role Removed", member, ctx.author, f"Removed role: {target_role.name}")
        else:
            await ctx.send("Invalid action. Please use 'add' or 'remove'.")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage roles for {member.mention}. Please ensure my role is higher than {target_role.name} and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to manage role {target_role.name} for {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to manage roles: `{e}`")
        print(f"DEBUG: HTTPException during role management: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to manage roles: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}role command for {member.name} and role {role_name}: {e}")

@bot.command(name='add_role_to_member', help='Adds a role to a specific member. Usage: {prefix}add_role_to_member <member> <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def add_role_to_member(ctx, member: discord.Member, *, role_name: str):
    """
    Adds a specified role to a member.
    Requires 'Manage Roles' permission for the user and bot.
    """
    target_role = discord.utils.get(ctx.guild.roles, name=role_name)

    if not target_role:
        await ctx.send(f"Role '{role_name}' not found.")
        return

    if target_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot assign a role that is equal to or higher than your own.")
        return

    if ctx.guild.me.top_role <= target_role:
        await ctx.send(f"I cannot assign the '{target_role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to assign.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot manage roles for the server owner.")
        return
    
    if target_role in member.roles:
        await ctx.send(f'{member.mention} already has the role {target_role.name}.')
        return

    try:
        await member.add_roles(target_role, reason=f"Role added by {ctx.author.name}")
        await ctx.send(f'Added role {target_role.name} to {member.mention}.')
        await log_moderation_action(ctx.guild, "Role Added", member, ctx.author, f"Added role: {target_role.name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to add roles to {member.mention}. Please ensure my role is higher than {target_role.name} and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to add role {target_role.name} for {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to add role: `{e}`")
        print(f"DEBUG: HTTPException during add_role_to_member: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to add role: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}add_role_to_member command: {e}")

@bot.command(name='remove_role_from_member', help='Removes a role from a specific member. Usage: {prefix}remove_role_from_member <member> <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
@commands.cooldown(1, 5, commands.BucketType.user)
async def remove_role_from_member(ctx, member: discord.Member, *, role_name: str):
    """
    Removes a specified role from a member.
    Requires 'Manage Roles' permission for the user and bot.
    """
    target_role = discord.utils.get(ctx.guild.roles, name=role_name)

    if not target_role:
        await ctx.send(f"Role '{role_name}' not found.")
        return

    if target_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot remove a role that is equal to or higher than your own.")
        return

    if ctx.guild.me.top_role <= target_role:
        await ctx.send(f"I cannot remove the '{target_role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to remove.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot manage roles for the server owner.")
        return

    if target_role not in member.roles:
        await ctx.send(f'{member.mention} does not have the role {target_role.name}.')
        return

    try:
        await member.remove_roles(target_role, reason=f"Role removed by {ctx.author.name}")
        await ctx.send(f'Removed role {target_role.name} from {member.mention}.')
        await log_moderation_action(ctx.guild, "Role Removed", member, ctx.author, f"Removed role: {target_role.name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to remove roles from {member.mention}. Please ensure my role is higher than {target_role.name} and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to remove role {target_role.name} for {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to remove role: `{e}`")
        print(f"DEBUG: HTTPException during remove_role_from_member: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to remove role: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}remove_role_from_member command: {e}")


@bot.command(name='announce', help='Sends an announcement to a specified channel. Usage: {prefix}announce <channel> <message>')
@commands.has_permissions(manage_channels=True) # Or a custom role for announcements
@commands.bot_has_permissions(send_messages=True) # Bot must have this permission in the target channel
@commands.cooldown(1, 15, commands.BucketType.guild) # 1 use per 15 seconds per guild
async def announce(ctx, channel: discord.TextChannel, *, message: str):
    """
    Sends an announcement message to the specified text channel.
    Requires 'Manage Channels' permission for the user.
    """
    try:
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Announced by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        await channel.send(embed=embed)
        await ctx.send(f'Announcement sent to {channel.mention}.')
        await log_moderation_action(ctx.guild, "Announcement", channel, ctx.author, f"Message: {message[:100]}...") # Log first 100 chars
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to send messages in {channel.mention}. Please check my permissions in that channel.")
        print(f"DEBUG: Bot missing permissions to send announcement to channel {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to send the announcement: `{e}`")
        print(f"DEBUG: HTTPException during announce: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to send the announcement: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}announce command to channel {channel.name}: {e}")

@bot.command(name='poll', help='Creates a simple poll. Usage: {prefix}poll "Question" "Option 1" "Option 2" ... (up to 9 options)')
@commands.has_permissions(manage_channels=True) # Or a custom role for creating polls
@commands.bot_has_permissions(add_reactions=True, manage_messages=True) # Bot needs these for poll
@commands.cooldown(1, 10, commands.BucketType.channel)
async def poll(ctx, question: str, *options: str):
    """
    Creates a poll with a question and up to 9 options.
    Each option should be enclosed in quotes.
    Requires 'Manage Channels' permission for the user.
    """
    if len(options) > 9:
        await ctx.send("You can only provide a maximum of 9 options for the poll.")
        return
    if len(options) < 2:
        await ctx.send("Please provide at least two options for the poll.")
        return

    description = f"**{question}**\n\n"
    for i, option in enumerate(options):
        description += f"{poll_emojis[i]} {option}\n"

    embed = discord.Embed(
        title="📊 New Poll!",
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Poll by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)

    try:
        poll_message = await ctx.send(embed=embed)
        for i in range(len(options)):
            await poll_message.add_reaction(poll_emojis[i])
        await ctx.message.delete() # Delete the command message to keep chat clean
        await log_moderation_action(ctx.guild, "Poll Created", ctx.channel, ctx.author, f"Question: {question[:100]}...")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to add reactions or manage messages in this channel. Please check my permissions.")
        print(f"DEBUG: Bot missing permissions for poll in channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to create the poll: `{e}`")
        print(f"DEBUG: HTTPException during poll: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to create the poll: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}poll command: {e}")

@bot.command(name='userinfo', aliases=['whois'], help='Displays information about a user. Usage: {prefix}userinfo [member]')
@commands.cooldown(1, 3, commands.BucketType.user)
async def userinfo(ctx, member: discord.Member = None):
    """
    Displays information about a specified user or the command invoker.
    """
    if member is None:
        member = ctx.author

    try:
        embed = discord.Embed(
            title=f"User Info: {member.display_name}",
            color=member.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Username", value=str(member), inline=True)
        embed.add_field(name="Nickname", value=member.nick if member.nick else "None", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        if roles:
            embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles), inline=False)
        else:
            embed.add_field(name="Roles", value="None", inline=False)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(name="Bot?", value="Yes" if member.bot else "No", inline=True)

        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to get user info: `{e}`")
        print(f"DEBUG: HTTPException during userinfo for {member.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to get user info: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}userinfo command for {member.name}: {e}")

@bot.command(name='channel_info', help='Displays information about a text or voice channel. Usage: {prefix}channel_info [channel]')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def channel_info(ctx, channel: discord.abc.GuildChannel = None):
    """
    Displays information about a specified text or voice channel.
    If no channel is specified, defaults to the current channel.
    """
    if channel is None:
        channel = ctx.channel

    try:
        embed = discord.Embed(
            title=f"Channel Info: #{channel.name}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="ID", value=channel.id, inline=True)
        embed.add_field(name="Type", value=str(channel.type).replace('channel_type.', ''), inline=True) # Clean up enum string
        embed.add_field(name="Created At", value=channel.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="Topic", value=channel.topic if channel.topic else "No topic set", inline=False)
            embed.add_field(name="NSFW", value=channel.is_nsfw(), inline=True)
            embed.add_field(name="Slowmode Delay", value=f"{channel.slowmode_delay} seconds", inline=True)
        elif isinstance(channel, discord.VoiceChannel):
            embed.add_field(name="Bitrate", value=f"{channel.bitrate / 1000} kbps", inline=True)
            embed.add_field(name="User Limit", value=channel.user_limit if channel.user_limit != 0 else "None", inline=True)
            embed.add_field(name="Connected Members", value=len(channel.members), inline=True)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to get channel info: `{e}`")
        print(f"DEBUG: HTTPException during channel_info for {channel.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to get channel info: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}channel_info command: {e}")

@bot.command(name='role_info', help='Displays information about a role. Usage: {prefix}role_info <role_name>')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def role_info(ctx, *, role: discord.Role):
    """
    Displays information about a specified role.
    """
    try:
        embed = discord.Embed(
            title=f"Role Info: {role.name}",
            color=role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color (Hex)", value=str(role.color), inline=True)
        embed.add_field(name="Members with Role", value=len(role.members), inline=True)
        embed.add_field(name="Created At", value=role.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        embed.add_field(name="Hoisted", value=role.hoist, inline=True)
        embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
        embed.add_field(name="Managed by Integration", value=role.managed, inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)

        permissions = [perm[0] for perm in role.permissions if perm[1]]
        if permissions:
            embed.add_field(name="Key Permissions", value=", ".join(permissions), inline=False)
        else:
            embed.add_field(name="Key Permissions", value="None", inline=False)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to get role info: `{e}`")
        print(f"DEBUG: HTTPException during role_info for {role.name}: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to get role info: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}role_info command: {e}")


@bot.command(name='serverinfo', aliases=['guildinfo'], help='Displays information about the server. Usage: {prefix}serverinfo')
@commands.cooldown(1, 5, commands.BucketType.guild)
async def serverinfo(ctx):
    """
    Displays information about the Discord server.
    """
    guild = ctx.guild

    try:
        embed = discord.Embed(
            title=f"Server Info: {guild.name}",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=f"{len(guild.text_channels)} Text, {len(guild.voice_channels)} Voice", inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Server Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
        embed.add_field(name="Boost Level", value=guild.premium_tier, inline=True)
        embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)

        await ctx.send(embed=embed)
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to get server info: `{e}`")
        print(f"DEBUG: HTTPException during serverinfo: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to get server info: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}serverinfo command: {e}")

@bot.command(name='dm', help='Direct messages a user. Usage: {prefix}dm <member> <message>')
@commands.has_permissions(manage_messages=True) # Or a custom role for DMs
@commands.bot_has_permissions(send_messages=True) # Bot needs to be able to send DMs (usually implied)
@commands.cooldown(1, 3, commands.BucketType.user)
async def dm(ctx, member: discord.Member, *, message: str):
    """
    Sends a direct message to the specified member.
    Requires 'Manage Messages' permission for the user.
    """
    await _send_dm_to_member(member, f"Message from {ctx.author.display_name} in {ctx.guild.name}:\n{message}")
    await ctx.send(f'Attempted to send DM to {member.mention}. (Note: DMs might be disabled for the user.)')

@bot.command(name='setmodlog', help='Sets the channel for moderation action logging. Usage: {prefix}setmodlog <channel>')
@commands.has_permissions(administrator=True) # Only administrators can set the log channel
@commands.bot_has_permissions(send_messages=True) # Bot must be able to send messages to the log channel
async def set_mod_log_channel(ctx, channel: discord.TextChannel):
    """
    Sets the current guild's moderation log channel.
    Requires 'Administrator' permission.
    """
    try:
        mod_log_channels[ctx.guild.id] = channel.id
        save_mod_log_channels() # Save mod log channels after modification
        await ctx.send(f'Moderation actions will now be logged in {channel.mention}.')
        print(f"DEBUG: Mod log channel for guild {ctx.guild.name} set to {channel.name} ({channel.id}).")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to send messages in {channel.mention}. Please ensure I have the 'Send Messages' permission in the designated log channel.")
        print(f"DEBUG: Bot missing permissions to send messages to mod log channel {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to set the mod log channel: `{e}`")
        print(f"DEBUG: HTTPException during setmodlog: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to set the moderation log channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}setmodlog command: {e}")

@bot.command(name='warns_clear_all', help='Clears all warnings for all members in the server. Usage: {prefix}warns_clear_all')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 30, commands.BucketType.guild) # Long cooldown for a destructive command
async def warns_clear_all(ctx):
    """
    Clears all temporary warnings for all users in the server.
    Requires 'Administrator' permission.
    Includes a confirmation step.
    """
    confirmation_message = f"Are you absolutely sure you want to clear ALL warnings for ALL users in this server? This action is irreversible."
    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        global user_warnings
        user_warnings = {} # Clear the dictionary
        save_warnings() # Save warnings after modification
        await ctx.send("All warnings for all users have been cleared.")
        await log_moderation_action(ctx.guild, "Clear All Warnings", "All Users", ctx.author, "All warnings cleared server-wide")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to clear all warnings: `{e}`")
        print(f"DEBUG: HTTPException during warns_clear_all: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to clear all warnings: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}warns_clear_all command: {e}")

@bot.command(name='mass_kick', help='Kicks multiple members. Usage: {prefix}mass_kick <member1> <member2> ... [reason]')
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True) # Bot must have this permission
@commands.cooldown(1, 15, commands.BucketType.guild)
async def mass_kick(ctx, *members: discord.Member, reason: str = "No reason provided"):
    """
    Kicks multiple specified members from the server.
    Requires 'Kick Members' permission.
    """
    if not members:
        await ctx.send("Please mention at least one member to kick.")
        return

    kicked_count = 0
    failed_kicks = []

    for member in members:
        # Use the helper for individual member checks
        if not await _check_mod_permissions(ctx, member, "kick"):
            failed_kicks.append(f"{member.mention} (Permission/Role Hierarchy Issue)")
            continue

        try:
            await member.kick(reason=reason)
            kicked_count += 1
            await log_moderation_action(ctx.guild, "Mass Kick", member, ctx.author, reason)
            await _send_dm_to_member(member, f'You have been kicked from {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            failed_kicks.append(f"{member.mention} (Bot missing permissions)")
            print(f"DEBUG: Bot missing permissions to kick {member.name} in guild {ctx.guild.name}.")
        except discord.HTTPException as e:
            failed_kicks.append(f"{member.mention} (Discord API error: {e})")
            print(f"DEBUG: HTTPException during mass kick for {member.name}: {e}")
        except Exception as e:
            failed_kicks.append(f"{member.mention} (Unexpected error: {e})")
            print(f"DEBUG: Error kicking {member.name}: {e}")

    if kicked_count > 0:
        await ctx.send(f'Successfully kicked {kicked_count} member(s).')
    if failed_kicks:
        await ctx.send(f'Failed to kick: {", ".join(failed_kicks)}')

@bot.command(name='mass_ban', help='Bans multiple members. Usage: {prefix}mass_ban <member1> <member2> ... [reason]')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True) # Bot must have this permission
@commands.cooldown(1, 30, commands.BucketType.guild)
async def mass_ban(ctx, *members: discord.Member, reason: str = "No reason provided"):
    """
    Bans multiple specified members from the server.
    Requires 'Ban Members' permission.
    Includes a confirmation step.
    """
    if not members:
        await ctx.send("Please mention at least one member to ban.")
        return

    member_mentions = ", ".join([m.mention for m in members])
    confirmation_message = f"Are you sure you want to ban the following members: {member_mentions} for: `{reason}`?"
    if not await _confirm_action(ctx, confirmation_message):
        return

    banned_count = 0
    failed_bans = []

    for member in members:
        # Use the helper for individual member checks
        if not await _check_mod_permissions(ctx, member, "ban"):
            failed_bans.append(f"{member.mention} (Permission/Role Hierarchy Issue)")
            continue

        try:
            await member.ban(reason=reason, delete_message_days=0)
            banned_count += 1
            await log_moderation_action(ctx.guild, "Mass Ban", member, ctx.author, reason)
            await _send_dm_to_member(member, f'You have been banned from {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            failed_bans.append(f"{member.mention} (Bot missing permissions)")
            print(f"DEBUG: Bot missing permissions to ban {member.name} in guild {ctx.guild.name}.")
        except discord.HTTPException as e:
            failed_bans.append(f"{member.mention} (Discord API error: {e})")
            print(f"DEBUG: HTTPException during mass ban for {member.name}: {e}")
        except Exception as e:
            failed_bans.append(f"{member.mention} (Unexpected error: {e})")
            print(f"DEBUG: Error banning {member.name}: {e}")

    if banned_count > 0:
        await ctx.send(f'Successfully banned {banned_count} member(s).')
    if failed_bans:
        await ctx.send(f'Failed to ban: {", ".join(failed_bans)}')

@bot.command(name='create_role', help='Creates a new role. Usage: {prefix}create_role <name> [hex_color]')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def create_role(ctx, name: str, hex_color: str = "#000000"):
    """
    Creates a new role with the given name and optional hex color.
    Requires 'Manage Roles' permission.
    """
    try:
        color = discord.Color(int(hex_color.replace("#", ""), 16))
    except ValueError:
        await ctx.send("Invalid hex color provided. Please use a format like `#RRGGBB` (e.g., `#FF0000` for red).")
        return

    try:
        # Check if a role with that name already exists
        if discord.utils.get(ctx.guild.roles, name=name):
            await ctx.send(f"A role named '{name}' already exists.")
            return

        # Check if the bot can create a role at the desired position (usually top-most below its own)
        # Discord API automatically places new roles below the bot's highest role,
        # but if the bot's highest role is very low, it might not be able to create roles with certain permissions.
        # This is implicitly handled by bot_has_permissions(manage_roles=True)

        new_role = await ctx.guild.create_role(name=name, color=color, reason=f"Role created by {ctx.author.name}")
        await ctx.send(f'Successfully created role: {new_role.mention}')
        await log_moderation_action(ctx.guild, "Role Created", new_role, ctx.author, f"Name: {name}, Color: {hex_color}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to create roles. Please ensure I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to create role in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to create the role: `{e}`")
        print(f"DEBUG: HTTPException during create_role: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to create the role: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}create_role command: {e}")

@bot.command(name='delete_role', help='Deletes an existing role. Usage: {prefix}delete_role <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def delete_role(ctx, *, role_name: str):
    """
    Deletes an existing role by its name.
    Requires 'Manage Roles' permission.
    Includes a confirmation step.
    """
    target_role = discord.utils.get(ctx.guild.roles, name=role_name)

    if not target_role:
        await ctx.send(f"Role '{role_name}' not found.")
        return
    if target_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot delete a role that is equal to or higher than your own.")
        return
    # Check if the bot's highest role is lower than or equal to the target role
    if ctx.guild.me.top_role <= target_role:
        await ctx.send(f"I cannot delete the '{target_role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to delete.")
        return
    if target_role == ctx.guild.default_role:
        await ctx.send("I cannot delete the `@everyone` role.")
        return
    # Removed the problematic line: if target_role == ctx.guild.owner_role:

    confirmation_message = f"Are you sure you want to delete the role '{target_role.name}'? This action is irreversible."
    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        await target_role.delete(reason=f"Role deleted by {ctx.author.name}")
        await ctx.send(f"Successfully deleted role: '{role_name}'.")
        await log_moderation_action(ctx.guild, "Role Deleted", target_role, ctx.author, f"Name: {role_name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to delete the role '{target_role.name}'. Please ensure my role is higher than the role you are trying to delete and I have the 'Manage Roles' permission.")
        print(f"DEBUG: Bot missing permissions to delete role {target_role.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to delete the role: `{e}`")
        print(f"DEBUG: HTTPException during delete_role: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to delete the role: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}delete_role command: {e}")

@bot.command(name='create_channel', help='Creates a new text or voice channel. Usage: {prefix}create_channel <type> <name>')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def create_channel(ctx, channel_type: str, *, name: str):
    """
    Creates a new text or voice channel.
    Requires 'Manage Channels' permission.
    """
    channel_type = channel_type.lower()
    try:
        # Check if a channel with that name already exists
        existing_channel = discord.utils.get(ctx.guild.channels, name=name)
        if existing_channel:
            await ctx.send(f"A channel named '{name}' already exists.")
            return

        if channel_type == 'text':
            new_channel = await ctx.guild.create_text_channel(name, reason=f"Text channel created by {ctx.author.name}")
            await ctx.send(f'Successfully created text channel: {new_channel.mention}')
            await log_moderation_action(ctx.guild, "Channel Created", new_channel, ctx.author, f"Type: Text, Name: {name}")
        elif channel_type == 'voice':
            new_channel = await ctx.guild.create_voice_channel(name, reason=f"Voice channel created by {ctx.author.name}")
            await ctx.send(f'Successfully created voice channel: {new_channel.name}')
            await log_moderation_action(ctx.guild, "Channel Created", new_channel, ctx.author, f"Type: Voice, Name: {name}")
        else:
            await ctx.send("Invalid channel type. Please specify 'text' or 'voice'.")
            return
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to create channels. Please ensure I have the 'Manage Channels' permission.")
        print(f"DEBUG: Bot missing permissions to create channel in guild {ctx.guild.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to create the channel: `{e}`")
        print(f"DEBUG: HTTPException during create_channel: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to create the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}create_channel command: {e}")

@bot.command(name='delete_channel', help='Deletes an existing channel. Usage: {prefix}delete_channel <channel>')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def delete_channel(ctx, channel: discord.abc.GuildChannel):
    """
    Deletes an existing text or voice channel.
    Requires 'Manage Channels' permission.
    Includes a confirmation step.
    """
    # Prevent deleting the channel where the command was issued
    if channel == ctx.channel:
        await ctx.send("You cannot delete the channel you are currently in.")
        return

    confirmation_message = f"Are you sure you want to delete the channel '{channel.name}'? This action is irreversible."
    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        channel_name = channel.name # Store name before deletion
        channel_id = channel.id # Store ID for logging
        await channel.delete(reason=f"Channel deleted by {ctx.author.name}")
        await ctx.send(f"Successfully deleted channel: '{channel_name}'.")
        await log_moderation_action(ctx.guild, "Channel Deleted", f"Channel Name: {channel_name}, ID: {channel_id}", ctx.author, f"Name: {channel_name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to delete the channel '{channel.name}'. Please ensure I have the 'Manage Channels' permission.")
        print(f"DEBUG: Bot missing permissions to delete channel {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to delete the channel: `{e}`")
        print(f"DEBUG: HTTPException during delete_channel: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to delete the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}delete_channel command: {e}")

@bot.command(name='set_channel_topic', help='Sets the topic of a text channel. Usage: {prefix}set_channel_topic [channel] <new_topic>')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True)
@commands.cooldown(1, 10, commands.BucketType.channel)
async def set_channel_topic(ctx, channel: discord.TextChannel = None, *, new_topic: str):
    """
    Sets the topic of a specified text channel. If no channel is specified, defaults to the current channel.
    Requires 'Manage Channels' permission for the user and bot.
    """
    if channel is None:
        channel = ctx.channel

    if not isinstance(channel, discord.TextChannel):
        await ctx.send("You can only set the topic for text channels.")
        return
    
    if len(new_topic) > 1024: # Discord API limit for channel topic length
        await ctx.send("Channel topic cannot exceed 1024 characters.")
        return

    try:
        old_topic = channel.topic if channel.topic else "no topic"
        await channel.edit(topic=new_topic, reason=f"Channel topic set by {ctx.author.name}")
        await ctx.send(f'Successfully set the topic for {channel.mention} to: "{new_topic}". (Old topic: "{old_topic}")')
        await log_moderation_action(ctx.guild, "Channel Topic Set", channel, ctx.author, f"New Topic: {new_topic[:100]}..., Old Topic: {old_topic[:100]}...")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channels in {channel.mention}. Please ensure I have the 'Manage Channels' permission.")
        print(f"DEBUG: Bot missing permissions to set channel topic in {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to set the channel topic: `{e}`")
        print(f"DEBUG: HTTPException during set_channel_topic: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to set the channel topic: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}set_channel_topic command: {e}")


@bot.command(name='move_member', help='Moves a member to a different voice channel. Usage: {prefix}move_member <member> <voice_channel>')
@commands.has_permissions(move_members=True)
@commands.bot_has_permissions(move_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def move_member(ctx, member: discord.Member, channel: discord.VoiceChannel):
    """
    Moves a specified member to another voice channel.
    Requires 'Move Members' permission.
    """
    if not await _check_mod_permissions(ctx, member, "move"):
        return

    if member.voice is None or member.voice.channel is None:
        await ctx.send(f"{member.mention} is not currently in a voice channel.")
        return
    if member.voice.channel == channel:
        await ctx.send(f"{member.mention} is already in {channel.name}.")
        return

    try:
        old_channel_name = member.voice.channel.name
        await member.move_to(channel, reason=f"Moved by {ctx.author.name}")
        await ctx.send(f'Successfully moved {member.mention} from {old_channel_name} to {channel.name}.')
        await log_moderation_action(ctx.guild, "Move Member", member, ctx.author, f"Moved from {old_channel_name} to {channel.name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to move {member.mention}. Please ensure my role is higher than theirs and I have the 'Move Members' permission.")
        print(f"DEBUG: Bot missing permissions to move {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to move the member: `{e}`")
        print(f"DEBUG: HTTPException during move_member: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to move the member: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}move_member command: {e}")

@bot.command(name='kick_from_vc', help='Kicks a member from their current voice channel. Usage: {prefix}kick_from_vc <member>')
@commands.has_permissions(move_members=True) # Kicking from VC uses move_members permission
@commands.bot_has_permissions(move_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def kick_from_vc(ctx, member: discord.Member):
    """
    Kicks a specified member from their current voice channel.
    Requires 'Move Members' permission.
    """
    if not await _check_mod_permissions(ctx, member, "kick from VC"):
        return

    if member.voice is None or member.voice.channel is None:
        await ctx.send(f"{member.mention} is not currently in a voice channel.")
        return

    try:
        old_channel_name = member.voice.channel.name
        await member.move_to(None, reason=f"Kicked from VC by {ctx.author.name}") # Moving to None disconnects them
        await ctx.send(f'Successfully kicked {member.mention} from voice channel {old_channel_name}.')
        await log_moderation_action(ctx.guild, "Kick from VC", member, ctx.author, f"Kicked from {old_channel_name}")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to kick {member.mention} from voice channels. Please ensure my role is higher than theirs and I have the 'Move Members' permission.")
        print(f"DEBUG: Bot missing permissions to kick from VC for {member.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to kick from VC: `{e}`")
        print(f"DEBUG: HTTPException during kick_from_vc: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to kick from VC: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}kick_from_vc command: {e}")

@bot.command(name='ban_vc', help='Bans a member from a specific voice channel. Usage: {prefix}ban_vc <member> <voice_channel> [reason]')
@commands.has_permissions(manage_channels=True) # Managing channel permissions for voice channels
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def ban_vc(ctx, member: discord.Member, channel: discord.VoiceChannel, *, reason: str = "No reason provided"):
    """
    Bans a specified member from joining a specific voice channel.
    Requires 'Manage Channels' permission.
    """
    # _check_mod_permissions is not directly applicable here as it's about channel overwrites,
    # not directly moving/kicking the member based on role hierarchy.
    if member == ctx.author:
        await ctx.send("You cannot ban yourself from a voice channel.")
        return
    if member == bot.user:
        await ctx.send("I cannot ban myself from a voice channel.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot ban the server owner from a voice channel.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    # This check is less critical for channel specific overwrites, but good practice.
    if ctx.guild.me.top_role <= member.top_role and member != ctx.guild.owner:
        await ctx.send(f"I cannot ban {member.mention} from voice channel {channel.name} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with an equal or higher role than you from a voice channel.")
        return

    # Check if they are already banned from this VC
    if channel.overwrites_for(member).connect is False:
        await ctx.send(f"{member.mention} is already banned from {channel.name}.")
        return

    try:
        # Deny 'Connect' permission for the member in that voice channel
        await channel.set_permissions(member, connect=False, reason=reason)
        # If they are currently in the channel, disconnect them
        if member.voice and member.voice.channel == channel:
            await member.move_to(None, reason=f"VC ban: disconnected from {channel.name}")

        await ctx.send(f'Successfully banned {member.mention} from voice channel {channel.name} for: {reason}')
        await log_moderation_action(ctx.guild, "VC Ban", member, ctx.author, f"Banned from {channel.name} for: {reason}")
        await _send_dm_to_member(member, f'You have been banned from voice channel {channel.name} in {ctx.guild.name} for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channel permissions in {channel.name}. Please ensure I have the 'Manage Channels' permission and my role is higher than {member.mention}'s.")
        print(f"DEBUG: Bot missing permissions to ban from VC for {member.name} in channel {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to ban from VC: `{e}`")
        print(f"DEBUG: HTTPException during ban_vc: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to ban from VC: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}ban_vc command: {e}")

@bot.command(name='unban_vc', help='Unbans a member from a specific voice channel. Usage: {prefix}unban_vc <member> <voice_channel> [reason]')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.guild)
async def unban_vc(ctx, member: discord.Member, channel: discord.VoiceChannel, *, reason: str = "No reason provided"):
    """
    Unbans a specified member from joining a specific voice channel.
    Requires 'Manage Channels' permission.
    """
    # Check if they are actually banned from this VC
    if not channel.overwrites_for(member).connect is False:
        await ctx.send(f"{member.mention} is not currently banned from {channel.name}.")
        return

    try:
        # Set 'Connect' permission to None (neutral/inherit) for the member in that voice channel
        await channel.set_permissions(member, connect=None, reason=reason)
        await ctx.send(f'Successfully unbanned {member.mention} from voice channel {channel.name} for: {reason}')
        await log_moderation_action(ctx.guild, "VC Unban", member, ctx.author, f"Unbanned from {channel.name} for: {reason}")
        await _send_dm_to_member(member, f'You have been unbanned from voice channel {channel.name} in {ctx.guild.name} for: {reason}')
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage channel permissions in {channel.name}. Please ensure I have the 'Manage Channels' permission and my role is higher than {member.mention}'s.")
        print(f"DEBUG: Bot missing permissions to unban from VC for {member.name} in channel {channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to unban from VC: `{e}`")
        print(f"DEBUG: HTTPException during unban_vc: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unban from VC: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unban_vc command: {e}")

@bot.command(name='mass_move_vc', help='Moves all members from one voice channel to another. Usage: {prefix}mass_move_vc <source_voice_channel> <destination_voice_channel>')
@commands.has_permissions(move_members=True)
@commands.bot_has_permissions(move_members=True)
@commands.cooldown(1, 15, commands.BucketType.guild)
async def mass_move_vc(ctx, source_vc: discord.VoiceChannel, destination_vc: discord.VoiceChannel):
    """
    Moves all members from the source voice channel to the destination voice channel.
    Requires 'Move Members' permission for the user and bot.
    """
    if source_vc == destination_vc:
        await ctx.send("Source and destination voice channels cannot be the same.")
        return
    
    if not source_vc.members:
        await ctx.send(f"There are no members in {source_vc.name} to move.")
        return

    moved_count = 0
    failed_moves = []

    for member in list(source_vc.members): # Iterate over a copy as members list changes during iteration
        if member == bot.user:
            continue # Don't try to move the bot itself

        # Check if the bot has permission to move this specific member
        # User's role hierarchy check is not needed here as it's a mass action by the bot.
        if ctx.guild.me.top_role <= member.top_role:
            failed_moves.append(f"{member.mention} (Bot role too low to move)")
            continue
        
        try:
            await member.move_to(destination_vc, reason=f"Mass moved by {ctx.author.name}")
            moved_count += 1
        except discord.Forbidden:
            failed_members.append(f"{member.mention} (Bot missing permissions)")
            print(f"DEBUG: Bot missing permissions to move {member.name} to {destination_vc.name}.")
        except discord.HTTPException as e:
            failed_moves.append(f"{member.mention} (Discord API error: {e})")
            print(f"DEBUG: HTTPException during mass move for {member.name}: {e}")
        except Exception as e:
            failed_moves.append(f"{member.mention} (Unexpected error: {e})")
            print(f"DEBUG: Error moving {member.name}: {e}")

    if moved_count > 0:
        await ctx.send(f'Successfully moved {moved_count} member(s) from {source_vc.name} to {destination_vc.name}.')
        await log_moderation_action(ctx.guild, "Mass Move VC", f"From {source_vc.name} to {destination_vc.name}", ctx.author, f"Moved {moved_count} members.")
    if failed_moves:
        await ctx.send(f'Failed to move: {", ".join(failed_moves)}')
    if moved_count == 0 and not failed_moves:
        await ctx.send(f"No members were affected by the mass role move operation for '{source_vc.name}'.")

# --- New Commands ---

@bot.command(name='mass_role', help='Adds or removes a role from multiple members. Usage: {prefix}mass_role <add|remove> <role_name> <member1> <member2> ... [reason]')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
@commands.cooldown(1, 15, commands.BucketType.guild)
async def mass_role(ctx, action: str, role_name: str, *members: discord.Member, reason: str = "No reason provided"):
    """
    Adds or removes a specified role from multiple members.
    Requires 'Manage Roles' permission.
    """
    action = action.lower()
    if action not in ['add', 'remove']:
        await ctx.send("Invalid action. Please use 'add' or 'remove'.")
        return
    
    target_role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not target_role:
        await ctx.send(f"Role '{role_name}' not found.")
        return

    if not members:
        await ctx.send("Please mention at least one member to apply/remove the role from.")
        return

    # Check if the bot's highest role is lower than or equal to the target role
    if ctx.guild.me.top_role <= target_role:
        await ctx.send(f"I cannot {action} the '{target_role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to manage.")
        return
    
    # Check if the user's role is higher than the target role
    if ctx.author.top_role <= target_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot manage a role that is equal to or higher than your own.")
        return

    processed_count = 0
    failed_members = []

    for member in members:
        if member.bot or member == ctx.guild.owner or member.top_role >= ctx.guild.me.top_role:
            # Skip bots, server owner, and members with higher or equal roles than the bot
            continue
        if role in member.roles:
            continue # Skip if already has the role

        try:
            if action == 'add':
                if target_role not in member.roles:
                    await member.add_roles(target_role, reason=f"Mass role add by {ctx.author.name}: {reason}")
                    processed_count += 1
                else:
                    failed_members.append(f"{member.mention} (Already has role)")
            elif action == 'remove':
                if target_role in member.roles:
                    await member.remove_roles(target_role, reason=f"Mass role remove by {ctx.author.name}: {reason}")
                    processed_count += 1
                else:
                    failed_members.append(f"{member.mention} (Does not have role)")
        except discord.Forbidden:
            failed_members.append(f"{member.mention} (Bot missing permissions)")
            print(f"DEBUG: Bot missing permissions to {action} role for {member.name}.")
        except discord.HTTPException as e:
            failed_members.append(f"{member.mention} (Discord API error: {e})")
            print(f"DEBUG: HTTPException during mass_role for {member.name}: {e}")
        except Exception as e:
            failed_members.append(f"{member.mention} (Unexpected error: {e})")
            print(f"DEBUG: Error during mass_role for {member.name}: {e}")

    if processed_count > 0:
        await ctx.send(f'Successfully {action}ed role `{target_role.name}` for {processed_count} member(s).')
        await log_moderation_action(ctx.guild, f"Mass Role {action.capitalize()}", target_role, ctx.author, f"Role: {target_role.name}, Action: {action}, Count: {processed_count}, Reason: {reason}")
    if failed_members:
        await ctx.send(f'Failed to {action} role for: {", ".join(failed_members)}')
    if processed_count == 0 and not failed_members:
        await ctx.send(f"No members were affected by the mass role move operation for '{target_role.name}'.")

@bot.command(name='afk', help='Sets your AFK status. The bot will respond when you are mentioned. Usage: {prefix}afk [message]')
@commands.cooldown(1, 10, commands.BucketType.user)
async def afk(ctx, *, message: str = "No message provided."):
    """
    Sets the user's AFK status.
    When the user is mentioned, the bot will respond with their AFK message.
    Their AFK status is automatically removed when they send another message.
    """
    # Store AFK status with current time
    afk_status[ctx.author.id] = {
        "message": message,
        "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    save_afk_status()

    embed = discord.Embed(
        title="💤 AFK Status Set!",
        description=f"You are now AFK. I will notify others if they mention you.\n**Your message:** {message}",
        color=discord.Color.from_rgb(173, 216, 230), # Light blue color
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"AFK set by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='avatar', help='Displays a user\'s avatar. Usage: {prefix}avatar [member]')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def avatar(ctx, member: discord.Member = None):
    """
    Displays the avatar of a specified user or the command invoker.
    """
    if member is None:
        member = ctx.author

    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

    embed = discord.Embed(
        title=f"{member.display_name}'s Avatar",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_image(url=avatar_url)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")

    await ctx.send(embed=embed)

@bot.command(name='remindme', help='Sets a reminder. Usage: {prefix}remindme <duration> <message> (e.g., 10m, 1h, 2d)')
@commands.cooldown(1, 5, commands.BucketType.user)
async def remindme(ctx, duration: str, *, message: str):
    """
    Sets a reminder for the user after a specified duration.
    Duration examples: 30s, 5m, 2h, 1d.
    """
    seconds = 0
    match = re.fullmatch(r'(\d+)([smhd])', duration.lower())
    if not match:
        await ctx.send("Invalid duration format. Please use a number followed by 's' (seconds), 'm' (minutes), 'h' (hours), or 'd' (days). E.g., `10m`, `2h`, `3d`.")
        return

    value, unit = int(match.group(1)), match.group(2)

    if unit == 's':
        seconds = value
    elif unit == 'm':
        seconds = value * 60
    elif unit == 'h':
        seconds = value * 3600
    elif unit == 'd':
        seconds = value * 86400

    if seconds <= 0:
        await ctx.send("Reminder duration must be positive.")
        return
    if seconds > 7 * 86400: # Max 7 days reminder to prevent excessive long-running tasks
        await ctx.send("Reminder duration cannot exceed 7 days.")
        return

    try:
        await ctx.send(f"Okay, {ctx.author.mention}, I will remind you in {duration} about: `{message}`.")
        await asyncio.sleep(seconds)
        
        embed = discord.Embed(
            title="⏰ Reminder!",
            description=f"You asked me to remind you about: **{message}**",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Reminder set by {ctx.author.display_name}")
        
        await ctx.author.send(embed=embed) # DM the user
        if ctx.guild and ctx.author.dm_channel != ctx.channel: # If not in DM, send a confirmation in original channel
            await ctx.send(f"{ctx.author.mention}, your reminder is ready! I've sent it to your DMs.")
    except discord.Forbidden:
        await ctx.send(f"I couldn't send you a DM, {ctx.author.mention}. Please check your privacy settings to allow DMs from server members.")
    except Exception as e:
        await ctx.send(f"An error occurred while setting the reminder: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}remindme command: {e}")

@bot.command(name='add_role_to_all', help='Adds a role to all members in the server. Usage: {prefix}add_role_to_all <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
@commands.cooldown(1, 60, commands.BucketType.guild) # Long cooldown for mass action
async def add_role_to_all(ctx, *, role: discord.Role):
    """
    Adds a specified role to all members in the server.
    Requires 'Manage Roles' permission.
    Includes a confirmation step.
    """
    if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot assign a role that is equal to or higher than your own.")
        return
    if ctx.guild.me.top_role <= role:
        await ctx.send(f"I cannot assign the '{role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to assign.")
        return
    if role.managed:
        await ctx.send(f"Cannot manage role '{role.name}' as it's managed by an integration.")
        return

    confirmation_message = f"Are you sure you want to add the role '{role.name}' to ALL members in this server?"
    if not await _confirm_action(ctx, confirmation_message):
        return

    added_count = 0
    failed_members = []
    message = await ctx.send(f"Attempting to add role '{role.name}' to all members... This may take a while.")

    for member in ctx.guild.members:
        if member.bot or member == ctx.guild.owner or member.top_role >= ctx.guild.me.top_role:
            # Skip bots, server owner, and members with higher or equal roles than the bot
            continue
        if role in member.roles:
            continue # Skip if already has the role

        try:
            await member.add_roles(role, reason=f"Mass role add by {ctx.author.name}")
            added_count += 1
        except discord.Forbidden:
            failed_members.append(f"{member.mention} (Bot missing permissions)")
        except discord.HTTPException as e:
            failed_members.append(f"{member.mention} (Discord API error: {e})")
        except Exception as e:
            failed_members.append(f"{member.mention} (Unexpected error: {e})")
        await asyncio.sleep(0.1) # Small delay to avoid hitting Discord's rate limits

    await message.delete() # Delete the initial "attempting" message

    if added_count > 0:
        await ctx.send(f'Successfully added role `{role.name}` to {added_count} member(s).')
        await log_moderation_action(ctx.guild, "Mass Role Add", role, ctx.author, f"Added role to {added_count} members.")
    if failed_members:
        await ctx.send(f'Failed to add role `{role.name}` to: {", ".join(failed_members)}')
    if added_count == 0 and not failed_members:
        await ctx.send(f"No members were affected by the mass role add operation for '{role.name}'.")

@bot.command(name='remove_role_from_all', help='Removes a role from all members in the server. Usage: {prefix}remove_role_from_all <role_name>')
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
@commands.cooldown(1, 60, commands.BucketType.guild) # Long cooldown for mass action
async def remove_role_from_all(ctx, *, role: discord.Role):
    """
    Removes a specified role from all members in the server.
    Requires 'Manage Roles' permission.
    Includes a confirmation step.
    """
    if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot remove a role that is equal to or higher than your own.")
        return
    if ctx.guild.me.top_role <= role:
        await ctx.send(f"I cannot remove the '{role.name}' role because my highest role is not above it. Please ensure my role is higher than the role you are trying to remove.")
        return
    if role.managed:
        await ctx.send(f"Cannot manage role '{role.name}' as it's managed by an integration.")
        return
    if role == ctx.guild.default_role:
        await ctx.send("I cannot remove the `@everyone` role.")
        return

    confirmation_message = f"Are you sure you want to remove the role '{role.name}' from ALL members in this server? This action is irreversible."
    if not await _confirm_action(ctx, confirmation_message):
        return

    removed_count = 0
    failed_members = []
    message = await ctx.send(f"Attempting to remove role '{role.name}' from all members... This may take a while.")

    for member in ctx.guild.members:
        if member.bot or member == ctx.guild.owner or member.top_role >= ctx.guild.me.top_role:
            # Skip bots, server owner, and members with higher or equal roles than the bot
            continue
        if role not in member.roles:
            continue # Skip if doesn't have the role

        try:
            await member.remove_roles(role, reason=f"Mass role remove by {ctx.author.name}")
            removed_count += 1
        except discord.Forbidden:
            failed_members.append(f"{member.mention} (Bot missing permissions)")
        except discord.HTTPException as e:
            failed_members.append(f"{member.mention} (Discord API error: {e})")
        except Exception as e:
            failed_members.append(f"{member.mention} (Unexpected error: {e})")
        await asyncio.sleep(0.1) # Small delay to avoid hitting Discord's rate limits

    await message.delete() # Delete the initial "attempting" message

    if removed_count > 0:
        await ctx.send(f'Successfully removed role `{role.name}` from {removed_count} member(s).')
        await log_moderation_action(ctx.guild, "Mass Role Remove", role, ctx.author, f"Removed role from {removed_count} members.")
    if failed_members:
        await ctx.send(f'Failed to remove role `{role.name}` from: {", ".join(failed_members)}')
    if removed_count == 0 and not failed_members:
        await ctx.send(f"No members were affected by the mass role remove operation for '{role.name}'.")

# --- Fun Commands ---

@bot.command(name='8ball', help='Ask the magic 8-ball a question! Usage: {prefix}8ball <question>')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def eightball(ctx, *, question: str):
    """
    Answers a yes/no question using a magic 8-ball.
    """
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes - definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]
    embed = discord.Embed(
        title="🎱 Magic 8-Ball",
        description=f"**Question:** {question}\n**Answer:** {random.choice(responses)}",
        color=discord.Color.dark_purple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Asked by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='coinflip', aliases=['flip'], help='Flips a coin. Usage: {prefix}coinflip')
@commands.cooldown(1, 2, commands.BucketType.channel)
async def coinflip(ctx):
    """
    Flips a coin and returns either "Heads" or "Tails".
    """
    result = random.choice(["Heads", "Tails"])
    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"The coin landed on: **{result}**!",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Flipped by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='dice', aliases=['roll'], help='Rolls a dice. Usage: {prefix}dice [sides=6]')
@commands.cooldown(1, 2, commands.BucketType.channel)
async def dice(ctx, sides: int = 6):
    """
    Rolls a dice with a specified number of sides (default is 6).
    """
    if sides < 2:
        await ctx.send("A dice must have at least 2 sides.")
        return
    result = random.randint(1, sides)
    embed = discord.Embed(
        title="🎲 Dice Roll",
        description=f"You rolled a {sides}-sided dice and got: **{result}**!",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Rolled by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='fact', help='Get a random interesting fact. Usage: {prefix}fact')
@commands.cooldown(1, 5, commands.BucketType.channel)
async def fact(ctx):
    """
    Sends a random interesting fact.
    """
    facts = [
        "A group of owls is called a parliament.",
        "Honey never spoils.",
        "The shortest war in history lasted 38 to 45 minutes.",
        "Octopuses have three hearts.",
        "A jiffy is an actual unit of time: 1/100th of a second.",
        "The average person walks the equivalent of three times around the world in a lifetime.",
        "Butterflies taste with their feet.",
        "It is impossible for most people to lick their own elbow.",
        "A crocodile cannot stick its tongue out.",
        "A shrimp's heart is in its head."
    ]
    embed = discord.Embed(
        title="💡 Random Fact",
        description=random.choice(facts),
        color=discord.Color.teal(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='joke', help='Tells a random joke. Usage: {prefix}joke')
@commands.cooldown(1, 5, commands.BucketType.channel)
async def joke(ctx):
    """
    Tells a random joke.
    """
    jokes = [
        "Why don't scientists trust atoms? Because they make up everything!",
        "What do you call a fake noodle? An impasta!",
        "Why did the scarecrow win an award? Because he was outstanding in his field!",
        "I told my wife she was drawing her eyebrows too high. She looked surprised.",
        "What do you call a sad strawberry? A blueberry.",
        "How do you organize a space party? You planet!",
        "Why did the bicycle fall over? Because it was two-tired!",
        "What do you call cheese that isn't yours? Nacho cheese!",
        "Did you hear about the chameleon who couldn't change color? He had a reptile dysfunction.",
        "What's orange and sounds like a parrot? A carrot."
    ]
    embed = discord.Embed(
        title="😂 Random Joke",
        description=random.choice(jokes),
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command(name='meme', help='Fetches a random meme from Reddit. Usage: {prefix}meme')
@commands.cooldown(1, 5, commands.BucketType.channel)
async def meme(ctx):
    """
    Fetches a random meme from a meme API and sends it to the channel.
    """
    meme_api_url = "https://meme-api.com/gimme"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(meme_api_url) as response:
                if response.status == 200:
                    meme_data = await response.json()
                    meme_url = meme_data['url']
                    meme_title = meme_data['title']
                    meme_author = meme_data['author']
                    meme_subreddit = meme_data['subreddit']

                    embed = discord.Embed(
                        title=meme_title,
                        url=meme_url, # Link title to the meme image
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    embed.set_image(url=meme_url)
                    embed.set_footer(text=f"From r/{meme_subreddit} by u/{meme_author} | Requested by {ctx.author.display_name}")
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"Could not fetch a meme. API returned status: {response.status}")
    except aiohttp.ClientError as e:
        await ctx.send(f"An error occurred while connecting to the meme API: `{e}`")
        print(f"DEBUG: aiohttp.ClientError in meme command: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to fetch a meme: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}meme command: {e}")

# List of example GIF URLs for the 'kill' command
# You can replace these with actual GIF URLs or integrate with a GIF API
kill_gifs = [
    "https://i.giphy.com/12zQQNVooHEIGQ.webp", # Updated GIF 1
    "https://media.giphy.com/media/3o7TKoHnJ2Q6yD2yA/giphy.gif", # Placeholder GIF 2
    "https://media.giphy.com/media/3o7TKoHnJ2Q6yD2yA/giphy.gif", # Placeholder GIF 3
    "https://media.giphy.com/media/3o7TKoHnJ2Q6yD2yA/giphy.gif" # Placeholder GIF 4
]

@bot.command(name='kill', help='''"Kills" a mentioned user with a random, humorous death message and a GIF. Usage: {prefix}kill <member>''')
@commands.cooldown(1, 5, commands.BucketType.channel)
async def kill(ctx, member: discord.Member):
    """
    "Kills" a mentioned user with a random, humorous death message and a GIF.
    """
    if member == ctx.author:
        await ctx.send(f"{ctx.author.mention} tries to kill themselves, but misses spectacularly and just trips over their own feet.")
        return
    if member == bot.user:
        await ctx.send(f"You try to kill me, but I'm just a bot! I'm already dead inside. 🤖")
        return

    death_messages = [
        f"{ctx.author.mention} unleashed a flock of angry geese on {member.mention}, who was last seen running towards the horizon, honking loudly.",
        f"{ctx.author.mention} challenged {member.mention} to a staring contest. {member.mention} blinked first, and then spontaneously combusted from the sheer disappointment.",
        f"{ctx.author.mention} hit {member.mention} with a rubber chicken. It was surprisingly effective.",
        f"{ctx.author.mention} convinced {member.mention} that gravity was optional. It was not.",
        f"{ctx.author.mention} fed {member.mention} a sandwich made entirely of spicy memes. {member.mention}'s brain overheated.",
        f"{ctx.author.mention} used the forbidden tickle jutsu on {member.mention}, who laughed themselves into oblivion.",
        f"{ctx.author.mention} whispered a terrible pun into {member.mention}'s ear. The sheer cringe was fatal.",
        f"{ctx.author.mention} accidentally dropped a piano on {member.mention}. Oops.",
        f"{ctx.author.mention} turned {member.mention} into a marketable plushie. Their cuteness was overwhelming.",
        f"{ctx.author.mention} taught {member.mention} how to code in assembly. {member.mention}'s head exploded from the complexity."
    ]

    embed = discord.Embed(
        title="💀 Fatal Encounter!",
        description=random.choice(death_messages),
        color=discord.Color.dark_grey(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    # Add a random GIF to the embed
    embed.set_image(url=random.choice(kill_gifs))
    embed.set_footer(text="F in the chat for the fallen.")
    await ctx.send(embed=embed)

# List of example GIF URLs for the 'slap' command
# You can replace these with actual GIF URLs or integrate with a GIF API
slap_gifs = [
    "https://c.tenor.com/wDu33wHVM_wAAAAd/tenor.gif", # Updated GIF 1
    "https://media.giphy.com/media/xT0BKlXf6qHw6a/giphy.gif", # Placeholder GIF 2
    "https://media.giphy.com/media/xT0BKlXf6qHw6a/giphy.gif", # Placeholder GIF 3
    "https://media.giphy.com/media/xT0BKlXf6qHw6a/giphy.gif" # Placeholder GIF 4
]

@bot.command(name='slap', help='''Slaps a mentioned user with a random, humorous slap message and a GIF. Usage: {prefix}slap <member>''')
@commands.cooldown(1, 5, commands.BucketType.channel)
async def slap(ctx, member: discord.Member):
    """
    Slaps a mentioned user with a random, humorous slap message and a GIF.
    """
    if member == ctx.author:
        await ctx.send(f"{ctx.author.mention} attempts to slap themselves, but ends up just lightly patting their own cheek. A for effort?")
        return
    if member == bot.user:
        await ctx.send(f"You try to slap me, but I'm intangible! Your hand phases right through. 👻")
        return

    slap_messages = [
        f"{ctx.author.mention} slaps {member.mention} with a large, wet fish. The smell lingers.",
        f"{ctx.author.mention} delivers a gentle, yet firm, slap to {member.mention} with a velvet glove.",
        f"{ctx.author.mention} slaps {member.mention} with the force of a thousand suns... or maybe just a slightly firm handshake.",
        f"{ctx.author.mention} winds up and slaps {member.mention} with a freshly baked pie. Delicious!",
        f"{ctx.author.mention} gives {member.mention} a disciplinary slap with a newspaper rolled into a tube. 'Bad human!'",
        f"{ctx.author.mention} slaps {member.mention} so hard, they briefly question their life choices.",
        f"{ctx.author.mention} slaps {member.mention} with a single, solitary high-five. It was awkward.",
        f"{ctx.author.mention} slaps {member.mention} with a stack of unread terms and conditions.",
        f"{ctx.author.mention} slaps {member.mention} with the truth, and it stings.",
        f"{ctx.author.mention} slaps {member.mention} with a wet noodle. It makes a surprisingly loud *thwack*."
    ]

    embed = discord.Embed(
        title="👋 Slap!",
        description=random.choice(slap_messages),
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    # Add a random GIF to the embed
    embed.set_image(url=random.choice(slap_gifs))
    embed.set_footer(text="That's gonna leave a mark... or not.")
    await ctx.send(embed=embed)

# --- Tic-Tac-Toe Game ---

# Dictionary to store active games by channel ID to prevent multiple games in one channel
active_tictactoe_games = {}

class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member, ctx: commands.Context):
        super().__init__(timeout=120) # Game times out after 2 minutes of inactivity
        self.player1 = player1 # Player X
        self.player2 = player2 # Player O
        self.players = {'X': player1, 'O': player2}
        self.board = ['-' for _ in range(9)] # Represents the 3x3 board, changed ' ' to '-'
        self.current_player_mark = 'X'
        self.game_over = False
        self.ctx = ctx # Store the context to send messages to the original channel
        self.message = None # To store the message the board is on

        # Create the 3x3 grid of buttons
        for i in range(9):
            self.add_item(self._create_button(i))
        
        # Removed the explicit add_item for the reset button as it's added by the decorator
        # self.add_item(discord.ui.Button(label="Reset Game", style=discord.ButtonStyle.secondary, row=3, custom_id="tictactoe_reset"))

    def _create_button(self, index: int):
        """Helper to create a single button for the board."""
        # Custom ID includes the index to identify which button was pressed
        # Changed label from ' ' to '-' to fix Discord API error
        button = discord.ui.Button(label='-', style=discord.ButtonStyle.grey, row=index // 3, custom_id=f"tictactoe_cell_{index}")
        button.callback = self.button_callback # Assign the common callback
        return button

    async def update_board_buttons(self):
        """Updates the labels and styles of the board buttons based on the current board state."""
        for item in self.children:
            # Only process buttons that are part of the Tic-Tac-Toe grid
            if item.custom_id and item.custom_id.startswith("tictactoe_cell_"):
                try:
                    # Extract the cell index from the custom_id
                    cell_index = int(item.custom_id.split('_')[-1])
                    # Ensure the index is within the valid range of the board
                    if 0 <= cell_index < len(self.board):
                        item.label = self.board[cell_index]
                        if self.board[cell_index] == 'X':
                            item.style = discord.ButtonStyle.green
                        elif self.board[cell_index] == 'O':
                            item.style = discord.ButtonStyle.red
                        else:
                            item.style = discord.ButtonStyle.grey
                        item.disabled = self.board[cell_index] != '-' or self.game_over # Disable clicked cells or if game is over
                    else:
                        print(f"WARNING: Invalid cell_index {cell_index} found in custom_id {item.custom_id} during button update.")
                except (ValueError, IndexError) as e:
                    print(f"WARNING: Could not parse cell_index from custom_id: {item.custom_id}. Error: {e}")
            # The 'Reset Game' button and any other non-game buttons will be skipped by the if condition.


    async def send_game_message(self):
        """Sends the initial game message or updates it."""
        embed = self._create_game_embed()
        if self.message:
            await self.message.edit(embed=embed, view=self)
        else:
            self.message = await self.ctx.send(embed=embed, view=self)

    def _create_game_embed(self, status_message: str = None):
        """Creates the embed displaying the Tic-Tac-Toe board and game status."""
        board_display = ""
        for i in range(3):
            board_display += "|".join(self.board[i*3 : i*3+3]) + "\n"
            if i < 2:
                board_display += "-----\n"
        
        embed = discord.Embed(
            title="🎮 Tic-Tac-Toe!",
            description=f"```\n{board_display}\n```",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        
        if self.game_over:
            if status_message:
                embed.add_field(name="Game Over!", value=status_message, inline=False)
            else: # Fallback, should ideally be set by check_winner/check_draw
                embed.add_field(name="Game Over!", value="Game ended.", inline=False)
        else:
            embed.add_field(name="Current Turn", value=self.players[self.current_player_mark].mention, inline=False)
        
        embed.set_footer(text=f"X: {self.player1.display_name} | O: {self.player2.display_name}")
        return embed

    def check_winner(self):
        """Checks if there's a winner."""
        winning_combinations = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
            (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
            (0, 4, 8), (2, 4, 6)              # Diagonals - Corrected
        ]
        for combo in winning_combinations:
            if self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]] != '-': # Changed ' ' to '-'
                self.game_over = True
                return self.board[combo[0]]
        return None

    def check_draw(self):
        """Checks if the game is a draw."""
        return '-' not in self.board and not self.check_winner() # Changed ' ' to '-'

    async def disable_all_buttons(self):
        """Disables all buttons on the board."""
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def button_callback(self, interaction: discord.Interaction):
        """Callback for when a Tic-Tac-Toe board button is pressed."""
        if self.game_over:
            await interaction.response.send_message("The game is already over! Use 'Reset Game' to start a new one.", ephemeral=True)
            return

        # Check if it's the correct player's turn
        if interaction.user.id != self.players[self.current_player_mark].id:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        # Extract the cell index from the custom_id
        try:
            cell_index = int(interaction.data['custom_id'].split('_')[-1])
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid button interaction.", ephemeral=True)
            return

        # Check if the cell is already occupied
        if self.board[cell_index] != '-': # Changed ' ' to '-'
            await interaction.response.send_message("That cell is already taken!", ephemeral=True)
            return

        # Make the move
        self.board[cell_index] = self.current_player_mark
        await self.update_board_buttons()

        winner = self.check_winner()
        if winner:
            winning_player = self.players[winner]
            await interaction.response.edit_message(embed=self._create_game_embed(f"🎉 {winning_player.mention} ({winner}) wins!"), view=self)
            await self.disable_all_buttons()
            del active_tictactoe_games[self.ctx.channel.id]
            self.stop() # Stop the view
            return

        if self.check_draw():
            self.game_over = True
            await interaction.response.edit_message(embed=self._create_game_embed("It's a draw! 🤝"), view=self)
            await self.disable_all_buttons()
            del active_tictactoe_games[self.ctx.channel.id]
            self.stop() # Stop the view
            return

        # Switch player
        self.current_player_mark = 'O' if self.current_player_mark == 'X' else 'X'
        await interaction.response.edit_message(embed=self._create_game_embed(), view=self)

    @discord.ui.button(label="Reset Game", style=discord.ButtonStyle.secondary, row=3, custom_id="tictactoe_reset")
    async def reset_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Resets the Tic-Tac-Toe game."""
        # Only allow players or ctx.author to reset
        if interaction.user.id not in [self.player1.id, self.player2.id, self.ctx.author.id]:
            await interaction.response.send_message("Only the players or the command invoker can reset the game.", ephemeral=True)
            return

        # Confirmation for reset
        # Pass the interaction object directly
        confirm_reset = await _confirm_action(interaction, "Are you sure you want to reset the Tic-Tac-Toe game?")
        if not confirm_reset:
            return

        # Reset game state
        self.board = ['-' for _ in range(9)] # Changed ' ' to '-'
        self.current_player_mark = 'X'
        self.game_over = False
        
        # Randomly swap X and O players for the new game
        if random.choice([True, False]):
            self.player1, self.player2 = self.player2, self.player1
            self.players = {'X': self.player1, 'O': self.player2}

        await self.update_board_buttons()
        await interaction.response.edit_message(embed=self._create_game_embed("Game has been reset! X goes first."), view=self)

    async def on_timeout(self):
        """Called when the view times out due to inactivity."""
        self.game_over = True
        await self.disable_all_buttons()
        if self.message:
            await self.message.edit(embed=self._create_game_embed("Game timed out due to inactivity."), view=self)
        if self.ctx.channel.id in active_tictactoe_games:
            del active_tictactoe_games[self.ctx.channel.id]
        self.stop() # Stop the view

@bot.command(name='tictactoe', help='Starts a Tic-Tac-Toe game with another member. Usage: {prefix}tictactoe <@player2>')
@commands.guild_only() # Only allow in guilds
@commands.cooldown(1, 10, commands.BucketType.channel) # One game per channel at a time
async def tictactoe(ctx, player2: discord.Member):
    """
    Starts a Tic-Tac-Toe game against another player.
    """
    if ctx.channel.id in active_tictactoe_games:
        await ctx.send("There's already an active Tic-Tac-Toe game in this channel. Please wait for it to finish or reset it.")
        return

    player1 = ctx.author # Player 1 is the command invoker

    if player1.id == player2.id:
        await ctx.send("You cannot play Tic-Tac-Toe against yourself!")
        return
    if player2.bot:
        await ctx.send("You cannot play Tic-Tac-Toe against a bot!")
        return

    # Randomly decide who goes first
    players_order = [player1, player2]
    random.shuffle(players_order)
    
    # Player X is players_order[0], Player O is players_order[1]
    game_view = TicTacToeView(players_order[0], players_order[1], ctx)
    active_tictactoe_games[ctx.channel.id] = game_view # Store the game

    await game_view.send_game_message()

# --- AutoMod Commands ---

@bot.group(name='automod', invoke_without_command=True, help='Manages custom AutoMod features. Use `{prefix}automod help` for subcommands.')
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def automod(ctx):
    """
    Base command for AutoMod management. Shows current status if no subcommand is given.
    """
    embed = discord.Embed(
        title="🛡️ Custom AutoMod Status",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="Anti-Invite", value="Enabled ✅" if automod_settings["anti_invite_enabled"] else "Disabled ❌", inline=False)
    embed.add_field(name="Anti-Link", value="Enabled ✅" if automod_settings["anti_link_enabled"] else "Disabled ❌", inline=False)
    embed.add_field(name="Anti-Profanity", value="Enabled ✅" if automod_settings["anti_profanity_enabled"] else "Disabled ❌", inline=False)

    ignored_channels_mentions = [ctx.guild.get_channel(cid).mention for cid in automod_settings["automod_ignored_channels"] if ctx.guild.get_channel(cid)]
    ignored_roles_mentions = [ctx.guild.get_role(rid).mention for rid in automod_settings["automod_ignored_roles"] if ctx.guild.get_role(rid)]

    embed.add_field(name="Ignored Channels", value=", ".join(ignored_channels_mentions) if ignored_channels_mentions else "None", inline=False)
    embed.add_field(name="Ignored Roles", value=", ".join(ignored_roles_mentions) if ignored_roles_mentions else "None", inline=False)
    
    embed.set_footer(text=f"Use {ctx.prefix}automod <enable|disable|ignore> to configure.")
    await ctx.send(embed=embed)

@automod.command(name='enable', help='Enables an AutoMod feature. Usage: {prefix}automod enable <feature_name>')
@commands.has_permissions(administrator=True)
async def automod_enable(ctx, feature: str):
    """Enables a specified AutoMod feature."""
    feature = feature.lower()
    if feature == "anti_invite":
        automod_settings["anti_invite_enabled"] = True
        await ctx.send("Anti-invite feature enabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-invite enabled")
    elif feature == "anti_link":
        automod_settings["anti_link_enabled"] = True
        await ctx.send("Anti-link feature enabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-link enabled")
    elif feature == "anti_profanity":
        automod_settings["anti_profanity_enabled"] = True
        await ctx.send("Anti-profanity feature enabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-profanity enabled")
    else:
        await ctx.send("Invalid AutoMod feature. Choose from: `anti_invite`, `anti_link`, `anti_profanity`.")
    save_automod_settings() # Save changes

@automod.command(name='disable', help='Disables an AutoMod feature. Usage: {prefix}automod disable <feature_name>')
@commands.has_permissions(administrator=True)
async def automod_disable(ctx, feature: str):
    """Disables a specified AutoMod feature."""
    feature = feature.lower()
    if feature == "anti_invite":
        automod_settings["anti_invite_enabled"] = False
        await ctx.send("Anti-invite feature disabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-invite disabled")
    elif feature == "anti_link":
        automod_settings["anti_link_enabled"] = False
        await ctx.send("Anti-link feature disabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-link disabled")
    elif feature == "anti_profanity":
        automod_settings["anti_profanity_enabled"] = False
        await ctx.send("Anti-profanity feature disabled.")
        await log_moderation_action(ctx.guild, "AutoMod Config", bot.user, ctx.author, "Anti-profanity disabled")
    else:
        await ctx.send("Invalid AutoMod feature. Choose from: `anti_invite`, `anti_link`, `anti_profanity`.")
    save_automod_settings() # Save changes

@automod.group(name='ignore', invoke_without_command=True, help='Manages ignored channels/roles for AutoMod. Use `{prefix}automod ignore help` for subcommands.')
@commands.has_permissions(administrator=True)
async def automod_ignore(ctx):
    """Base command for AutoMod ignore settings."""
    await ctx.send_help(ctx.command) # Show help for the group

@automod_ignore.command(name='channel', help='Adds or removes a channel from AutoMod ignore list. Usage: {prefix}automod ignore channel <add|remove> <channel>')
@commands.has_permissions(administrator=True)
async def automod_ignore_channel(ctx, action: str, channel: discord.TextChannel):
    """Adds or removes a channel from the AutoMod ignore list."""
    action = action.lower()
    if action == "add":
        if channel.id not in automod_settings["automod_ignored_channels"]:
            automod_settings["automod_ignored_channels"].append(channel.id)
            await ctx.send(f"Channel {channel.mention} added to AutoMod ignore list.")
            await log_moderation_action(ctx.guild, "AutoMod Config", channel, ctx.author, "Added to ignore list")
        else:
            await ctx.send(f"Channel {channel.mention} is already in the AutoMod ignore list.")
    elif action == "remove":
        if channel.id in automod_settings["automod_ignored_channels"]:
            automod_settings["automod_ignored_channels"].remove(channel.id)
            await ctx.send(f"Channel {channel.mention} removed from AutoMod ignore list.")
            await log_moderation_action(ctx.guild, "AutoMod Config", channel, ctx.author, "Removed from ignore list")
        else:
            await ctx.send(f"Channel {channel.mention} is not in the AutoMod ignore list.")
    else:
        await ctx.send("Invalid action. Use 'add' or 'remove'.")
    save_automod_settings() # Save changes

@automod_ignore.command(name='role', help='Adds or removes a role from AutoMod ignore list. Usage: {prefix}automod ignore role <add|remove> <role_name>')
@commands.has_permissions(administrator=True)
async def automod_ignore_role(ctx, action: str, *, role: discord.Role):
    """Adds or removes a role from the AutoMod ignore list."""
    action = action.lower()
    if action == "add":
        if role.id not in automod_settings["automod_ignored_roles"]:
            automod_settings["automod_ignored_roles"].append(role.id)
            await ctx.send(f"Role {role.mention} added to AutoMod ignore list.")
            await log_moderation_action(ctx.guild, "AutoMod Config", role, ctx.author, "Added to ignore list")
        else:
            await ctx.send(f"Role {role.mention} is already in the AutoMod ignore list.")
    elif action == "remove":
        if role.id in automod_settings["automod_ignored_roles"]:
            automod_settings["automod_ignored_roles"].remove(role.id)
            await ctx.send(f"Role {role.mention} removed from AutoMod ignore list.")
            await log_moderation_action(ctx.guild, "AutoMod Config", role, ctx.author, "Removed from ignore list")
        else:
            await ctx.send(f"Role {role.mention} is not in the AutoMod ignore list.")
    else:
        await ctx.send("Invalid action. Use 'add' or 'remove'.")
    save_automod_settings() # Save changes

@bot.command(name='add_bad_word', help='Adds a word to the profanity filter. Usage: {prefix}add_bad_word <word>')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 3, commands.BucketType.guild)
async def add_bad_word(ctx, *, word: str):
    """
    Adds a word to the AutoMod profanity filter.
    Requires 'Administrator' permission.
    """
    word = word.lower()
    if word in automod_settings["profanity_words"]:
        await ctx.send(f"'{word}' is already in the profanity filter.")
        return

    automod_settings["profanity_words"].append(word)
    save_automod_settings()
    await ctx.send(f"Added '{word}' to the profanity filter.")
    await log_moderation_action(ctx.guild, "AutoMod Profanity", "Profanity List", ctx.author, f"Added word: '{word}'")

@bot.command(name='remove_bad_word', help='Removes a word from the profanity filter. Usage: {prefix}remove_bad_word <word>')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 3, commands.BucketType.guild)
async def remove_bad_word(ctx, *, word: str):
    """
    Removes a word from the AutoMod profanity filter.
    Requires 'Administrator' permission.
    """
    word = word.lower()
    if word not in automod_settings["profanity_words"]:
        await ctx.send(f"'{word}' is not in the profanity filter.")
        return

    automod_settings["profanity_words"].remove(word)
    save_automod_settings()
    await ctx.send(f"Removed '{word}' from the profanity filter.")
    await log_moderation_action(ctx.guild, "AutoMod Profanity", "Profanity List", ctx.author, f"Removed word: '{word}'")

@bot.command(name='list_bad_words', help='Lists all words in the profanity filter. Usage: {prefix}list_bad_words')
@commands.has_permissions(kick_members=True) # Or a custom role for moderators
@commands.cooldown(1, 5, commands.BucketType.guild)
async def list_bad_words(ctx):
    """
    Lists all words currently configured in the AutoMod profanity filter.
    Requires 'Kick Members' permission.
    """
    if not automod_settings["profanity_words"]:
        await ctx.send("The profanity filter list is currently empty.")
        return

    words_list = "\n".join(sorted(automod_settings["profanity_words"]))
    embed = discord.Embed(
        title="🚫 Profanity Filter Words",
        description=f"```\n{words_list}\n```",
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@bot.command(name='clear', help='Clears a specified number of messages from the channel. Messages older than 14 days cannot be cleared. Usage: {prefix}clear <amount>')
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True)
@commands.cooldown(1, 5, commands.BucketType.channel)
async def clear(ctx, amount: int):
    """
    Clears a specified number of messages from the current channel.
    Messages older than 14 days cannot be cleared due to Discord API limitations.
    Requires 'Manage Messages' permission for the user and bot.
    Includes a confirmation step.
    """
    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to clear.")
        return
    if amount > 100: # Setting a reasonable upper limit to prevent abuse and rate limits
        await ctx.send("You can clear a maximum of 100 messages at once.")
        return

    confirmation_message = f"Are you sure you want to clear {amount} messages in this channel? (Note: Discord only allows bulk deletion of messages up to 14 days old.)"
    if not await _confirm_action(ctx, confirmation_message):
        return

    try:
        # Fetch messages, including the command message itself.
        # The `before` parameter ensures we only fetch messages up to the current time.
        # The `limit` is `amount + 1` to also delete the command message itself.
        deleted = await ctx.channel.purge(limit=amount + 1, before=datetime.datetime.now(datetime.timezone.utc))
        
        # Adjust count if the command message was among those deleted
        actual_deleted_count = len(deleted)
        if ctx.message in deleted:
            actual_deleted_count -= 1 # The command message itself

        if actual_deleted_count < 0: # Should not happen, but a safeguard
            actual_deleted_count = 0

        await ctx.send(f'Successfully cleared {actual_deleted_count} messages.', delete_after=5)
        await log_moderation_action(ctx.guild, "Clear Messages", ctx.channel, ctx.author, f"{actual_deleted_count} messages cleared")
    except discord.Forbidden:
        await ctx.send(f"I don't have permission to manage messages in this channel. Please ensure I have the 'Manage Messages' permission.")
        print(f"DEBUG: Bot missing permissions to clear messages in channel {ctx.channel.name}.")
    except discord.HTTPException as e:
        await ctx.send(f"An error occurred with Discord's API while trying to clear messages: `{e}`")
        print(f"DEBUG: HTTPException during clear: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to clear messages: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}clear command: {e}")

@bot.command(name='punish', help='Applies a custom punishment (kick, ban, or timeout) to a member. Usage: {prefix}punish <member> <kick|ban|timeout> [duration] [reason]')
@commands.cooldown(1, 7, commands.BucketType.user) # Cooldown for this versatile command
async def punish(ctx, member: discord.Member, punishment_type: str, duration_or_days: str = None, *, reason: str = "No reason provided"):
    """
    Applies a custom punishment (kick, ban, or timeout) to a member.
    - `kick`: Kicks the member. Duration is ignored.
    - `ban`: Bans the member. Duration can be a number of days (0-7) to delete messages. Default is 0 days.
    - `timeout`: Times out the member. Duration is required (e.g., 30s, 5m, 2h, 1d).
    Requires appropriate permissions for the chosen punishment type.
    """
    punishment_type = punishment_type.lower()

    # Check general moderation permissions and hierarchy
    if not await _check_mod_permissions(ctx, member, punishment_type):
        return

    # --- Handle Kick ---
    if punishment_type == 'kick':
        if not ctx.author.guild_permissions.kick_members:
            await ctx.send("You don't have permission to kick members.")
            return
        if not ctx.guild.me.guild_permissions.kick_members:
            await ctx.send("I don't have permission to kick members.")
            return
        
        confirmation_message = f"Are you sure you want to **kick** {member.mention} for: `{reason}`?"
        if not await _confirm_action(ctx, confirmation_message):
            return
        
        try:
            await member.kick(reason=reason)
            await ctx.send(f'{member.mention} has been kicked by {ctx.author.mention} for: {reason}')
            await log_moderation_action(ctx.guild, "Custom Punish (Kick)", member, ctx.author, reason)
            await _send_dm_to_member(member, f'You have been kicked from {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            await ctx.send(f"I don't have permission to kick {member.mention}. Please ensure my role is higher than theirs and I have the 'Kick Members' permission.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred with Discord's API while trying to kick {member.mention}: `{e}`")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred while trying to kick: `{e}`")

    # --- Handle Ban ---
    elif punishment_type == 'ban':
        if not ctx.author.guild_permissions.ban_members:
            await ctx.send("You don't have permission to ban members.")
            return
        if not ctx.guild.me.guild_permissions.ban_members:
            await ctx.send("I don't have permission to ban members.")
            return
        
        delete_message_days = 0
        if duration_or_days:
            try:
                delete_message_days = int(duration_or_days)
                if not 0 <= delete_message_days <= 7:
                    await ctx.send("For ban, message deletion days must be between 0 and 7.")
                    return
            except ValueError:
                await ctx.send("Invalid duration for ban. Please provide a number (0-7) for message deletion days, or omit it.")
                return

        confirmation_message = f"Are you sure you want to **ban** {member.mention} (deleting messages from last {delete_message_days} days) for: `{reason}`?"
        if not await _confirm_action(ctx, confirmation_message):
            return
        
        try:
            await member.ban(reason=reason, delete_message_days=delete_message_days)
            await ctx.send(f'{member.mention} has been banned by {ctx.author.mention} (deleting messages from last {delete_message_days} days) for: {reason}')
            await log_moderation_action(ctx.guild, "Custom Punish (Ban)", member, ctx.author, reason)
            await _send_dm_to_member(member, f'You have been banned from {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            await ctx.send(f"I don't have permission to ban {member.mention}. Please ensure my role is higher than theirs and I have the 'Ban Members' permission.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred with Discord's API while trying to ban {member.mention}: `{e}`")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred while trying to ban: `{e}`")

    # --- Handle Timeout ---
    elif punishment_type == 'timeout':
        if not ctx.author.guild_permissions.moderate_members:
            await ctx.send("You don't have permission to timeout members.")
            return
        if not ctx.guild.me.guild_permissions.moderate_members:
            await ctx.send("I don't have permission to timeout members.")
            return

        if not duration_or_days:
            await ctx.send("For timeout, a duration is required (e.g., `30s`, `5m`, `2h`, `1d`).")
            return

        delta = None
        try:
            if duration_or_days.endswith('s'):
                delta = datetime.timedelta(seconds=int(duration_or_days[:-1]))
            elif duration_or_days.endswith('m'):
                delta = datetime.timedelta(minutes=int(duration_or_days[:-1]))
            elif duration_or_days.endswith('h'):
                delta = datetime.timedelta(hours=int(duration_or_days[:-1]))
            elif duration_or_days.endswith('d'):
                delta = datetime.timedelta(days=int(duration_or_days[:-1]))
            else:
                await ctx.send("Invalid duration format. Use 's' for seconds, 'm' for minutes, 'h' for hours, or 'd' for days (e.g., `30m`, `1h`, `7d`).")
                return

            if delta.total_seconds() <= 0:
                await ctx.send("Punishment duration must be positive.")
                return
            if delta.total_seconds() > 2419200: # Max timeout duration is 28 days (2,419,200 seconds)
                await ctx.send("Timeout duration cannot exceed 28 days.")
                return

        except ValueError:
            await ctx.send("Invalid duration value. Please provide a number followed by 's', 'm', 'h', or 'd' (e.g., `30m`).")
            return
        except Exception as e:
            await ctx.send(f"An error occurred while parsing the duration: `{e}`")
            print(f"DEBUG: Error parsing punishment duration: {e}")
            return

        confirmation_message = f"Are you sure you want to **timeout** {member.mention} for {duration_or_days} for: `{reason}`?"
        if not await _confirm_action(ctx, confirmation_message):
            return
        
        try:
            await member.timeout(delta, reason=reason)
            await ctx.send(f'{member.mention} has been timed out by {ctx.author.mention} for {duration_or_days} for: {reason}')
            await log_moderation_action(ctx.guild, "Custom Punish (Timeout)", member, ctx.author, f"Duration: {duration_or_days}, Reason: {reason}")
            await _send_dm_to_member(member, f'You have been timed out in {ctx.guild.name} for {duration_or_days} for: {reason}')
        except discord.Forbidden:
            await ctx.send(f"I don't have permission to timeout {member.mention}. Please ensure my role is higher than theirs and I have the 'Moderate Members' permission.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred with Discord's API while trying to timeout {member.mention}: `{e}`")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred while trying to timeout: `{e}`")

    else:
        await ctx.send("Invalid punishment type. Please choose from `kick`, `ban`, or `timeout`.")


# Run the bot with your token
if __name__ == '__main__':
    keep_alive() # Start the web server to keep the bot alive on hosting platforms
    bot.run(DISCORD_BOT_TOKEN)
