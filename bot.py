# bot.py
import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import json
import os
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

# --- Persistent Storage for Prefixes ---
PREFIXES_FILE = 'prefixes.json'
guild_prefixes = {} # Dictionary to store custom prefixes for each guild

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

# Dictionary to store warnings for users.
# IMPORTANT: This is in-memory and will reset when the bot restarts.
# For persistent storage, consider using a database (e.g., SQLite, Firebase Firestore).
user_warnings = {}

# Dictionary to store moderation log channel IDs for each guild (server)
# IMPORTANT: This is in-memory and will reset when the bot restarts.
# For persistent storage, consider using a database (e.g., SQLite, Firebase Firestore).
mod_log_channels = {}

# Emoji for poll reactions (up to 9 options)
poll_emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']

# --- Helper Function for Logging Moderation Actions ---
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
        # In a persistent setup, you'd remove this ID from storage here.
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

# --- Bot Events ---

@bot.event
async def on_ready():
    """
    This event fires when the bot successfully connects to Discord.
    Sets the bot's status and activity.
    Loads prefixes from file.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('Bot is ready!')
    print('------')

    # Load prefixes when the bot starts
    load_prefixes()

    # Set bot's status to Do Not Disturb and activity to "Watching SERVERS !!!"
    activity = discord.Activity(type=discord.ActivityType.watching, name="SERVERS !!!")
    await bot.change_presence(status=discord.Status.dnd, activity=activity)
    print("Bot status set to DND, watching 'SERVERS !!!'")


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
        usage_info = f"Usage: `{ctx.command.usage.format(prefix=ctx.prefix)}`" if hasattr(ctx.command, 'usage') else f"Usage: `{ctx.prefix}{ctx.command.name} {ctx.command.help.split('Usage: ')[-1].strip() if 'Usage: ' in ctx.command.help else ''}`"
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
        await ctx.send(f"An unexpected error occurred while processing your command: `{error}`. Please try again or contact an administrator if the issue persists.")

# --- General Utility Commands ---

@bot.command(name='ping', help='Checks the bot\'s latency to Discord. Usage: {prefix}ping')
@commands.cooldown(1, 3, commands.BucketType.channel)
async def ping(ctx):
    """
    Responds with the bot's latency (ping).
    """
    try:
        await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')
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

        # Add buttons for each category
        for category_name in self.categories.keys():
            self.add_item(discord.ui.Button(label=category_name, custom_id=f"help_category_{category_name}"))

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

    @discord.ui.button(label="Close Help", style=discord.ButtonStyle.danger, custom_id="help_close", row=4)
    async def close_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Help menu closed.", embed=None, view=None)
        self.stop() # Stop the view

    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.primary, custom_id="help_category_Moderation", row=1)
    async def show_moderation_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "Moderation"
        embed = discord.Embed(
            title="Moderation Commands",
            description="Commands for managing users and messages.",
            color=discord.Color.red()
        )
        for cmd_name in self.categories["Moderation"]:
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

    @discord.ui.button(label="Server Management", style=discord.ButtonStyle.primary, custom_id="help_category_Server Management", row=1)
    async def show_server_management_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "Server Management"
        embed = discord.Embed(
            title="Server Management Commands",
            description="Commands for managing server roles and channels.",
            color=discord.Color.orange()
        )
        for cmd_name in self.categories["Server Management"]:
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

    @discord.ui.button(label="Utility", style=discord.ButtonStyle.primary, custom_id="help_category_Utility", row=2)
    async def show_utility_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "Utility"
        embed = discord.Embed(
            title="Utility Commands",
            description="General purpose commands.",
            color=discord.Color.green()
        )
        for cmd_name in self.categories["Utility"]:
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

    @discord.ui.button(label="Voice Chat", style=discord.ButtonStyle.primary, custom_id="help_category_Voice Chat", row=2)
    async def show_voice_chat_commands(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = "Voice Chat"
        embed = discord.Embed(
            title="Voice Chat Commands",
            description="Commands for managing voice channels.",
            color=discord.Color.blue()
        )
        for cmd_name in self.categories["Voice Chat"]:
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
        "kick", "ban", "unban", "mute", "unmute", "clear", "warn",
        "warnings", "clearwarnings", "softban", "slowmode", "lockdown",
        "unlock", "mass_kick", "mass_ban", "warns_clear_all"
    ],
    "Server Management": [
        "create_role", "delete_role", "create_channel", "delete_channel",
        "setmodlog", "nick", "setprefix"
    ],
    "Utility": [
        "ping", "userinfo", "serverinfo", "announce", "poll", "dm"
    ],
    "Voice Chat": [
        "move_member", "kick_from_vc", "ban_vc", "unban_vc"
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

    if len(new_prefix) > 5: # Limit prefix length to prevent abuse
        await ctx.send("The new prefix cannot be longer than 5 characters.")
        return

    # Check if the bot has permission to send messages with the new prefix
    # This is a bit tricky as the prefix itself doesn't require permissions,
    # but if it clashes with another bot or system, it could cause issues.
    # For now, we'll assume the user sets a reasonable prefix.

    guild_prefixes[ctx.guild.id] = new_prefix
    save_prefixes() # Save the updated prefixes to file
    await ctx.send(f"The command prefix for this server has been set to `{new_prefix}`. You can now use commands like `{new_prefix}help`.")
    await log_moderation_action(ctx.guild, "Prefix Change", "Server", ctx.author, f"Prefix changed to '{new_prefix}'")


# --- Moderation Commands ---

@bot.command(name='kick', help='Kicks a member from the server. Usage: {prefix}kick <member> [reason]')
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user) # 1 use per 5 seconds per user
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Kicks the specified member from the server.
    Requires 'Kick Members' permission for the user.
    """
    if member == ctx.author:
        await ctx.send("You cannot kick yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot kick myself!")
        return
    # Check if the target member is the guild owner
    if member == ctx.guild.owner:
        await ctx.send("I cannot kick the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot kick {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    # Ensure the moderator cannot kick someone with an equal or higher role, unless they are the guild owner.
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot kick someone with an equal or higher role than you.")
        return

    try:
        await member.kick(reason=reason)
        await ctx.send(f'{member.mention} has been kicked by {ctx.author.mention} for: {reason}')
        await log_moderation_action(ctx.guild, "Kick", member, ctx.author, reason)
        # Attempt to DM the kicked member
        try:
            await member.send(f'You have been kicked from {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being kicked (Forbidden error).")
        except Exception as e:
            print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being kicked: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to kick: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}kick command for {member.name}: {e}")

@bot.command(name='ban', help='Bans a member from the server. Usage: {prefix}ban <member> [reason]')
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.user) # 1 use per 10 seconds per user
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Bans the specified member from the server.
    Requires 'Ban Members' permission for the user.
    Includes a confirmation step.
    """
    if member == ctx.author:
        await ctx.send("You cannot ban yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot ban myself!")
        return
    # Check if the target member is the guild owner
    if member == ctx.guild.owner:
        await ctx.send("I cannot ban the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot ban {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot ban someone with an equal or higher role than you.")
        return

    # Confirmation step
    confirm_message = await ctx.send(f"Are you sure you want to ban {member.mention} for: `{reason}`? React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            try:
                # delete_message_days=0 means no messages are deleted
                await member.ban(reason=reason, delete_message_days=0)
                await ctx.send(f'{member.mention} has been banned by {ctx.author.mention} for: {reason}')
                await log_moderation_action(ctx.guild, "Ban", member, ctx.author, reason)
                # Attempt to DM the banned member
                try:
                    await member.send(f'You have been banned from {ctx.guild.name} for: {reason}')
                except discord.Forbidden:
                    print(f"DEBUG: Could not DM {member.name} about being banned (Forbidden error).")
                except Exception as e:
                    print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being banned: {e}")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while trying to ban: `{e}`")
                print(f"DEBUG: Error in {ctx.prefix}ban command for {member.name}: {e}")
        else:
            await ctx.send("Ban cancelled.")
        await confirm_message.delete() # Clean up confirmation message
    except asyncio.TimeoutError:
        await ctx.send("Ban confirmation timed out. Action cancelled.")
        await confirm_message.delete() # Clean up confirmation message
    except Exception as e:
        await ctx.send(f"An error occurred during ban confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}ban confirmation logic: {e}")


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
    if member == ctx.author:
        await ctx.send("You cannot mute yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot mute myself!")
        return
    # Check if the target member is the guild owner
    if member == ctx.guild.owner:
        await ctx.send("I cannot mute the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot mute {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot mute someone with an equal or higher role than you.")
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
        try:
            await member.send(f'You have been muted in {ctx.guild.name} for {duration_minutes} minutes for: {reason}')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being muted (Forbidden error).")
        except Exception as e:
            print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being muted: {e}")

        # Schedule the unmute
        await asyncio.sleep(duration_minutes * 60) # Convert minutes to seconds
        if muted_role in member.roles: # Check if they are still muted after the duration
            try:
                await member.remove_roles(muted_role, reason="Mute duration expired")
                await ctx.send(f'{member.mention} has been unmuted automatically after {duration_minutes} minutes.')
                await log_moderation_action(ctx.guild, "Unmute (Auto)", member, bot.user, "Mute duration expired")
                try:
                    await member.send(f'You have been unmuted in {ctx.guild.name}.')
                except discord.Forbidden:
                    print(f"DEBUG: Could not DM {member.name} about being unmuted (Forbidden error).")
                except Exception as e:
                    print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being unmuted: {e}")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while trying to automatically unmute {member.mention}: `{e}`")
                print(f"DEBUG: Error in automatic unmute for {member.name}: {e}")

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
        try:
            await member.send(f'You have been unmuted in {ctx.guild.name}.')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being unmuted (Forbidden error).")
        except Exception as e:
            print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being unmuted: {e}")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unmute: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unmute command for {member.name}: {e}")

@bot.command(name='clear', help='Clears a specified number of messages from the channel. Usage: {prefix}clear <amount>')
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.channel) # 1 use per 5 seconds per channel
async def clear(ctx, amount: int):
    """
    Clears the specified number of messages from the current channel.
    Requires 'Manage Messages' permission for the user.
    Includes a confirmation step.
    """
    if amount <= 0:
        await ctx.send("Please specify a positive number of messages to clear.")
        return

    # Confirmation step
    confirm_message = await ctx.send(f"Are you sure you want to clear {amount} messages in this channel? React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            try:
                # Add 1 to amount to also delete the command message itself and the confirmation message
                # Note: purge can't delete messages older than 14 days. This is a Discord API limitation.
                deleted = await ctx.channel.purge(limit=amount + 2)
                # Send a confirmation message and delete it after 5 seconds
                await ctx.send(f'Successfully cleared {len(deleted) - 2} messages.', delete_after=5)
                await log_moderation_action(ctx.guild, "Clear Messages", ctx.channel, ctx.author, f"{len(deleted) - 2} messages cleared")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while trying to clear messages: `{e}`")
                print(f"DEBUG: Error in {ctx.prefix}clear command: {e}")
        else:
            await ctx.send("Clear messages cancelled.")
        await confirm_message.delete() # Clean up confirmation message
    except asyncio.TimeoutError:
        await ctx.send("Clear messages confirmation timed out. Action cancelled.")
        await confirm_message.delete() # Clean up confirmation message
    except Exception as e:
        await ctx.send(f"An error occurred during clear confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}clear confirmation logic: {e}")


@bot.command(name='warn', help='Warns a member. Usage: {prefix}warn <member> [reason]')
@commands.has_permissions(kick_members=True) # Or a custom role for moderators
@commands.cooldown(1, 3, commands.BucketType.user)
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Warns the specified member. Warnings are stored temporarily.
    """
    if member == ctx.author:
        await ctx.send("You cannot warn yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot warn myself!")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot warn the server owner.")
        return

    if member.id not in user_warnings:
        user_warnings[member.id] = []
    user_warnings[member.id].append(reason)

    try:
        await member.send(f'You have been warned in {ctx.guild.name} for: {reason}')
        await ctx.send(f'{member.mention} has been warned by {ctx.author.mention} for: {reason}. They now have {len(user_warnings[member.id])} warning(s).')
        await log_moderation_action(ctx.guild, "Warn", member, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send(f"Warned {member.mention} for: {reason}, but could not DM them (DMs might be disabled). They now have {len(user_warnings[member.id])} warning(s).")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to warn: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}warn command for {member.name}: {e}")

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

        warnings_list = "\n".join([f"- {w}" for w in user_warnings[member.id]])
        await ctx.send(f'Warnings for {member.mention}:\n{warnings_list}')
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
    if member == ctx.author:
        await ctx.send("You cannot softban yourself!")
        return
    if member == bot.user:
        await ctx.send("I cannot softban myself!")
        return
    # Check if the target member is the guild owner
    if member == ctx.guild.owner:
        await ctx.send("I cannot softban the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot softban {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot softban someone with an equal or higher role than you.")
        return

    try:
        # Ban the member, deleting messages for 'days'
        await member.ban(reason=reason, delete_message_days=days)
        # Immediately unban them to achieve the "kick with message deletion" effect
        await ctx.guild.unban(member, reason="Softban: immediate unban after message deletion")
        await ctx.send(f'{member.mention} has been softbanned by {ctx.author.mention} (kicked and messages from last {days} days deleted) for: {reason}')
        await log_moderation_action(ctx.guild, "Softban", member, ctx.author, reason)
        try:
            await member.send(f'You have been softbanned from {ctx.guild.name} (kicked and messages from last {days} days deleted) for: {reason}')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being softbanned (Forbidden error).")
        except Exception as e:
            print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being softbanned: {e}")
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
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to set slowmode: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}slowmode command: {e}")

@bot.command(name='lockdown', help='Locks down the current channel, preventing @everyone from sending messages. Usage: {prefix}lockdown [reason]')
@commands.has_permissions(manage_channels=True)
@commands.bot_has_permissions(manage_channels=True) # Bot must have this permission
@commands.cooldown(1, 10, commands.BucketType.channel)
async def lockdown(ctx, *, reason: str = "No reason provided"):
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
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to lock down the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}lockdown command: {e}")

@bot.command(name='unlock', help='Unlocks the current channel, allowing @everyone to send messages. Usage: {prefix}unlock [reason]')
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
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unlock the channel: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unlock command: {e}")

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
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to manage roles: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}role command for {member.name} and role {role_name}: {e}")

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
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to get user info: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}userinfo command for {member.name}: {e}")

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
    try:
        await member.send(f"Message from {ctx.author.display_name} in {ctx.guild.name}:\n{message}")
        await ctx.send(f'Successfully sent DM to {member.mention}.')
    except discord.Forbidden:
        await ctx.send(f"Could not send DM to {member.mention}. They might have DMs disabled or blocked me.")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to send the DM: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}dm command to {member.name}: {e}")

@bot.command(name='setmodlog', help='Sets the channel for moderation action logging. Usage: {prefix}setmodlog <channel>')
@commands.has_permissions(administrator=True) # Only administrators can set the log channel
@commands.bot_has_permissions(send_messages=True) # Bot must be able to send messages to the log channel
async def set_mod_log_channel(ctx, channel: discord.TextChannel):
    """
    Sets the current guild's moderation log channel.
    Requires 'Administrator' permission.
    """
    mod_log_channels[ctx.guild.id] = channel.id
    await ctx.send(f'Moderation actions will now be logged in {channel.mention}.')
    print(f"DEBUG: Mod log channel for guild {ctx.guild.name} set to {channel.name} ({channel.id}).")

@bot.command(name='warns_clear_all', help='Clears all warnings for all members in the server. Usage: {prefix}warns_clear_all')
@commands.has_permissions(administrator=True)
@commands.cooldown(1, 30, commands.BucketType.guild) # Long cooldown for a destructive command
async def warns_clear_all(ctx):
    """
    Clears all temporary warnings for all users in the server.
    Requires 'Administrator' permission.
    Includes a confirmation step.
    """
    confirm_message = await ctx.send(f"Are you absolutely sure you want to clear ALL warnings for ALL users in this server? This action is irreversible. React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            global user_warnings
            user_warnings = {} # Clear the dictionary
            await ctx.send("All warnings for all users have been cleared.")
            await log_moderation_action(ctx.guild, "Clear All Warnings", "All Users", ctx.author, "All warnings cleared server-wide")
        else:
            await ctx.send("Clearing all warnings cancelled.")
        await confirm_message.delete()
    except asyncio.TimeoutError:
        await ctx.send("Clearing all warnings confirmation timed out. Action cancelled.")
        await confirm_message.delete()
    except Exception as e:
        await ctx.send(f"An error occurred during clearing all warnings confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}warns_clear_all confirmation logic: {e}")

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
        if member == ctx.author:
            failed_kicks.append(f"{member.mention} (Cannot kick self)")
            continue
        if member == bot.user:
            failed_kicks.append(f"{member.mention} (Cannot kick bot)")
            continue
        if member == ctx.guild.owner:
            failed_kicks.append(f"{member.mention} (Cannot kick server owner)")
            continue
        # Check if the bot's highest role is lower than or equal to the target's highest role
        if ctx.guild.me.top_role <= member.top_role:
            failed_kicks.append(f"{member.mention} (Bot role too low)")
            continue
        if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
            failed_kicks.append(f"{member.mention} (Invoker role too low)")
            continue

        try:
            await member.kick(reason=reason)
            kicked_count += 1
            await log_moderation_action(ctx.guild, "Mass Kick", member, ctx.author, reason)
            try:
                await member.send(f'You have been kicked from {ctx.guild.name} for: {reason}')
            except discord.Forbidden:
                print(f"DEBUG: Could not DM {member.name} about being mass kicked.")
            except Exception as e:
                print(f"DEBUG: An unexpected error occurred while DMing {member.name} about being mass kicked: {e}")
        except Exception as e:
            failed_kicks.append(f"{member.mention} (Error: {e})")
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

    # Confirmation step
    member_mentions = ", ".join([m.mention for m in members])
    confirm_message = await ctx.send(f"Are you sure you want to ban the following members: {member_mentions} for: `{reason}`? React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            banned_count = 0
            failed_bans = []

            for member in members:
                if member == ctx.author:
                    failed_bans.append(f"{member.mention} (Cannot ban self)")
                    continue
                if member == bot.user:
                    failed_bans.append(f"{member.mention} (Cannot ban bot)")
                    continue
                if member == ctx.guild.owner:
                    failed_bans.append(f"{member.mention} (Cannot ban server owner)")
                    continue
                # Check if the bot's highest role is lower than or equal to the target's highest role
                if ctx.guild.me.top_role <= member.top_role:
                    failed_bans.append(f"{member.mention} (Bot role too low)")
                    continue
                if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
                    failed_bans.append(f"{member.mention} (Invoker role too low)")
                    continue

                try:
                    await member.ban(reason=reason, delete_message_days=0)
                    banned_count += 1
                    await log_moderation_action(ctx.guild, "Mass Ban", member, ctx.author, reason)
                    try:
                        await member.send(f'You have been banned from {ctx.guild.name} for: {reason}')
                    except discord.Forbidden:
                        print(f"DEBUG: Could not DM {member.name} about being mass banned.")
                except Exception as e:
                    failed_bans.append(f"{member.mention} (Error: {e})")
                    print(f"DEBUG: Error banning {member.name}: {e}")

            if banned_count > 0:
                await ctx.send(f'Successfully banned {banned_count} member(s).')
            if failed_bans:
                await ctx.send(f'Failed to ban: {", ".join(failed_bans)}')
        else:
            await ctx.send("Mass ban cancelled.")
        await confirm_message.delete()
    except asyncio.TimeoutError:
        await ctx.send("Mass ban confirmation timed out. Action cancelled.")
        await confirm_message.delete()
    except Exception as e:
        await ctx.send(f"An error occurred during mass ban confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}mass_ban confirmation logic: {e}")

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
    if target_role == ctx.guild.owner_role: # Prevent deleting the owner's role if it's separate
        await ctx.send("I cannot delete the server owner's role.")
        return

    confirm_message = await ctx.send(f"Are you sure you want to delete the role '{target_role.name}'? This action is irreversible. React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            try:
                await target_role.delete(reason=f"Role deleted by {ctx.author.name}")
                await ctx.send(f"Successfully deleted role: '{role_name}'.")
                await log_moderation_action(ctx.guild, "Role Deleted", target_role, ctx.author, f"Name: {role_name}")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while trying to delete the role: `{e}`")
                print(f"DEBUG: Error in {ctx.prefix}delete_role command: {e}")
        else:
            await ctx.send("Role deletion cancelled.")
        await confirm_message.delete()
    except asyncio.TimeoutError:
        await ctx.send("Role deletion confirmation timed out. Action cancelled.")
        await confirm_message.delete()
    except Exception as e:
        await ctx.send(f"An error occurred during role deletion confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}delete_role confirmation logic: {e}")

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

    confirm_message = await ctx.send(f"Are you sure you want to delete the channel '{channel.name}'? This action is irreversible. React with ✅ to confirm or ❌ to cancel.")
    await confirm_message.add_reaction('✅')
    await confirm_message.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)

        if str(reaction.emoji) == '✅':
            try:
                channel_name = channel.name # Store name before deletion
                channel_id = channel.id # Store ID for logging
                await channel.delete(reason=f"Channel deleted by {ctx.author.name}")
                await ctx.send(f"Successfully deleted channel: '{channel_name}'.")
                await log_moderation_action(ctx.guild, "Channel Deleted", f"Channel Name: {channel_name}, ID: {channel_id}", ctx.author, f"Name: {channel_name}")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while trying to delete the channel: `{e}`")
                print(f"DEBUG: Error in {ctx.prefix}delete_channel command: {e}")
        else:
            await ctx.send("Channel deletion cancelled.")
        await confirm_message.delete()
    except asyncio.TimeoutError:
        await ctx.send("Channel deletion confirmation timed out. Action cancelled.")
        await confirm_message.delete()
    except Exception as e:
        await ctx.send(f"An error occurred during channel deletion confirmation: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}delete_channel confirmation logic: {e}")

@bot.command(name='move_member', help='Moves a member to a different voice channel. Usage: {prefix}move_member <member> <voice_channel>')
@commands.has_permissions(move_members=True)
@commands.bot_has_permissions(move_members=True) # Bot must have this permission
@commands.cooldown(1, 5, commands.BucketType.user)
async def move_member(ctx, member: discord.Member, channel: discord.VoiceChannel):
    """
    Moves a specified member to another voice channel.
    Requires 'Move Members' permission.
    """
    if member.voice is None or member.voice.channel is None:
        await ctx.send(f"{member.mention} is not currently in a voice channel.")
        return
    if member.voice.channel == channel:
        await ctx.send(f"{member.mention} is already in {channel.name}.")
        return
    if member == ctx.author:
        await ctx.send("You cannot move yourself using this command.")
        return
    if member == bot.user:
        await ctx.send("I cannot move myself using this command.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot move the server owner.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot move {member.mention} because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot move someone with an equal or higher role than you.")
        return

    try:
        old_channel_name = member.voice.channel.name
        await member.move_to(channel, reason=f"Moved by {ctx.author.name}")
        await ctx.send(f'Successfully moved {member.mention} from {old_channel_name} to {channel.name}.')
        await log_moderation_action(ctx.guild, "Move Member", member, ctx.author, f"Moved from {old_channel_name} to {channel.name}")
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
    if member.voice is None or member.voice.channel is None:
        await ctx.send(f"{member.mention} is not currently in a voice channel.")
        return
    if member == ctx.author:
        await ctx.send("You cannot kick yourself from a voice channel using this command.")
        return
    if member == bot.user:
        await ctx.send("I cannot kick myself from a voice channel using this command.")
        return
    if member == ctx.guild.owner:
        await ctx.send("I cannot kick the server owner from a voice channel.")
        return
    # Check if the bot's highest role is lower than or equal to the target's highest role
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"I cannot kick {member.mention} from voice channel because their highest role is equal to or higher than my highest role. Please ensure my role is above theirs.")
        return
    if ctx.author.top_role <= member.top_role and ctx.author != ctx.guild.owner:
        await ctx.send("You cannot kick someone with an equal or higher role than you from a voice channel.")
        return

    try:
        old_channel_name = member.voice.channel.name
        await member.move_to(None, reason=f"Kicked from VC by {ctx.author.name}") # Moving to None disconnects them
        await ctx.send(f'Successfully kicked {member.mention} from voice channel {old_channel_name}.')
        await log_moderation_action(ctx.guild, "Kick from VC", member, ctx.author, f"Kicked from {old_channel_name}")
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
        try:
            await member.send(f'You have been banned from voice channel {channel.name} in {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being VC banned.")
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
        try:
            await member.send(f'You have been unbanned from voice channel {channel.name} in {ctx.guild.name} for: {reason}')
        except discord.Forbidden:
            print(f"DEBUG: Could not DM {member.name} about being VC unbanned.")
    except Exception as e:
        await ctx.send(f"An unexpected error occurred while trying to unban from VC: `{e}`")
        print(f"DEBUG: Error in {ctx.prefix}unban_vc command: {e}")


# Run the bot with your token
if __name__ == '__main__':
    keep_alive() # Start the web server to keep the bot alive on hosting platforms
    bot.run(DISCORD_BOT_TOKEN)
