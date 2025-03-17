import discord
import datetime
import json
import os
import aiohttp
import asyncio
import config
import random
import re
import requests
import certifi
import yt_dlp as youtube_dl
from discord import Webhook
from discord.ext import commands

# Initialize bot with intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

# FFmpeg options
FFMPEG_OPTIONS = {
    'options': '-vn'
}

# YTDL options
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'auto',
}

# Function to extract info from YouTube URL or search query
async def get_audio_source(url):
    with youtube_dl.YoutubeDL(YTDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        return {
            'source': info['url'],
            'title': info['title']
        }

# Database to store warnings
warnings_db = {}

# Check if warnings file exists, load if it does
if os.path.exists('warnings.json'):
    with open('warnings.json', 'r') as f:
        warnings_db = json.load(f)

# Function to save warnings to file
def save_warnings():
    with open('warnings.json', 'w') as f:
        json.dump(warnings_db, f)

# 8ball responses
EIGHTBALL_RESPONSES = [
    "Yes.", "No.", "Maybe.", "Ask again later.", "Definitely!", 
    "I don't think so.", "Absolutely!", "Very doubtful."
]

# Check if a user is an admin
def is_admin(ctx):
    return ctx.author.id in config.ADMIN_IDS

# Admin check decorator
def admin_only():
    async def predicate(ctx):
        if not is_admin(ctx):
            await ctx.send("You don't have permission to use this command.")
            return False
        return True
    return commands.check(predicate)

# Send a message to the modlog channel
async def send_to_modlog(guild, title, description, color=discord.Color.blue()):
    modlog_channel = bot.get_channel(config.MODLOG_CHANNEL_ID)
    if modlog_channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now()
        )
        await modlog_channel.send(embed=embed)

# Bot startup event
@bot.event
async def on_ready():
    print(f'{bot.user.name} is online and ready!')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name=f"{config.PREFIX}commands for commands"
    ))

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"Command not found. Use `{config.PREFIX}commands` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument. Use `{config.PREFIX}commands {ctx.command}` for usage information.")
    elif isinstance(error, commands.CheckFailure):
        pass  # Admin check will handle this
    else:
        await ctx.send(f"An error occurred: {error}")

# WARN COMMAND
@bot.command(name="warn")
@admin_only()
async def warn(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        user = await bot.fetch_user(user_id)
        
        if not reason:
            reason = config.DEFAULT_REASON
        
        if str(user_id) not in warnings_db:
            warnings_db[str(user_id)] = []
        
        warning_data = {
            "reason": reason,
            "timestamp": datetime.datetime.now().isoformat(),
            "warned_by": ctx.author.id
        }
        
        warnings_db[str(user_id)].append(warning_data)
        save_warnings()
        
        # Check for auto-timeout
        if len(warnings_db[str(user_id)]) >= config.MAX_WARNINGS:
            member = ctx.guild.get_member(user_id)
            if member:
                timeout_until = datetime.datetime.now() + datetime.timedelta(seconds=config.AUTO_TIMEOUT_DURATION)
                try:
                    await member.timeout(timeout_until, reason="Automatic timeout after reaching warning limit")
                    await ctx.send(f"{user.mention} has been automatically timed out for 24 hours after reaching {config.MAX_WARNINGS} warnings.")
                    
                    # Send to modlog
                    await send_to_modlog(
                        ctx.guild,
                        "Auto-Timeout Applied",
                        f"**User:** {user.mention} ({user.name}#{user.discriminator})\n"
                        f"**Reason:** Reached {config.MAX_WARNINGS} warnings\n"
                        f"**Duration:** 24 hours\n"
                        f"**Moderator:** Automatic system",
                        discord.Color.dark_red()
                    )
                except discord.Forbidden:
                    await ctx.send("I don't have permission to timeout that user.")
        
        await ctx.send(f"Warning added for {user.mention}. They now have {len(warnings_db[str(user_id)])} warning(s).")
        
        # Send to modlog
        await send_to_modlog(
            ctx.guild,
            "User Warned",
            f"**User:** {user.mention} ({user})\n"
            f"**Reason:** {reason}\n"
            f"**Warned by:** {ctx.author.mention}\n"
            f"**Warning count:** {len(warnings_db[str(user_id)])}",
            discord.Color.orange()
        )
        
        # Try to DM the user
        try:
            await user.send(f"You have been warned in {ctx.guild.name} for: {reason}")
        except discord.Forbidden:
            pass  # User has DMs closed
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")
    except discord.NotFound:
        await ctx.send("User not found.")

# UNWARN COMMAND
@bot.command(name="unwarn")
@admin_only()
async def unwarn(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        user = await bot.fetch_user(user_id)
        
        if not reason:
            reason = config.DEFAULT_REASON
        
        if str(user_id) not in warnings_db or not warnings_db[str(user_id)]:
            await ctx.send(f"{user.mention} has no warnings to remove.")
            return
        
        # Remove the most recent warning
        warnings_db[str(user_id)].pop()
        save_warnings()
        
        await ctx.send(f"Warning removed from {user.mention}. They now have {len(warnings_db[str(user_id)])} warning(s).")
        
        # Send to modlog
        await send_to_modlog(
            ctx.guild,
            "Warning Removed",
            f"**User:** {user.mention} ({user})\n"
            f"**Reason:** {reason}\n"
            f"**Removed by:** {ctx.author.mention}\n"
            f"**Remaining warnings:** {len(warnings_db[str(user_id)])}",
            discord.Color.green()
        )
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")
    except discord.NotFound:
        await ctx.send("User not found.")

# TIMEOUT COMMAND
@bot.command(name="timeout")
@admin_only()
async def timeout(ctx, user_id: str, duration: str, *, reason=None):
    try:
        # Check if author has timeout permissions
        if not ctx.author.guild_permissions.moderate_members:
            return await ctx.send("🚫 You don't have permission to timeout members.")

        # Check if bot has timeout permissions
        if not ctx.guild.me.guild_permissions.moderate_members:
            return await ctx.send("🚫 I don't have permission to timeout members.")

        # Convert user ID and fetch member
        user_id = int(user_id.strip('"<@!>'))
        try:
            member = await ctx.guild.fetch_member(user_id)  # ✅ Fetch member properly
        except discord.NotFound:
            return await ctx.send("⚠️ User not found in this server.")

        # Check if bot can timeout the user
        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("🚫 I cannot timeout this user because their role is equal to or higher than mine.")

        # Default reason if none given
        if not reason:
            reason = "No reason provided."

        # Parse duration
        time_units = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "mo": 2629800,  # 30.44 days (average)
            "y": 31557600   # 365.25 days (average)
        }

        unit = ''.join(filter(str.isalpha, duration.lower()))  # Extract unit
        value = ''.join(filter(str.isdigit, duration))  # Extract number

        if unit not in time_units or not value.isdigit():
            return await ctx.send("⚠️ Invalid duration format. Use a number followed by s, m, h, d, mo, or y. (Example: `30m`)")

        duration_seconds = int(value) * time_units[unit]

        # Set timeout expiration using discord.utils.utcnow()
        timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=duration_seconds)

        # Apply timeout
        await member.edit(timed_out_until=timeout_until, reason=reason)

        # Format duration for display
        duration_display = f"{value} {unit}"
        await ctx.send(f"✅ {member.mention} has been timed out for {duration_display}.")

        # Send modlog (Optional)
        await send_to_modlog(
            ctx.guild,
            "User Timed Out",
            f"**User:** {member.mention} ({member})\n"
            f"**Duration:** {duration_display}\n"
            f"**Reason:** {reason}\n"
            f"**Moderator:** {ctx.author.mention}",
            discord.Color.red()
        )

        # Try to DM the user
        try:
            await member.send(f"You have been timed out in {ctx.guild.name} for {duration_display}. Reason: {reason}")
        except discord.Forbidden:
            pass  # User has DMs closed

    except ValueError:
        await ctx.send("⚠️ Invalid user ID format. Please use a valid ID.")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to timeout that user.")
    except Exception as e:
        await ctx.send(f"⚠️ An error occurred: {e}")

# UNTIMEOUT COMMAND
@bot.command(name="untimeout")
@admin_only()
async def untimeout(ctx, user_id: str):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            await ctx.send("User not found in this server.")
            return
            
        try:
            await member.timeout(None, reason="Timeout removed by moderator")
            await ctx.send(f"Timeout removed for {member.mention}.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "Timeout Removed",
                f"**User:** {member.mention} ({member})\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.green()
            )
            
            # Try to DM the user
            try:
                await member.send(f"Your timeout in {ctx.guild.name} has been removed by a moderator.")
            except discord.Forbidden:
                pass  # User has DMs closed
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to remove timeout for that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# BAN COMMAND
@bot.command(name="ban")
@admin_only()
async def ban(ctx, user_id: str, days: int = 0, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        user = await bot.fetch_user(user_id)
        
        if not reason:
            reason = config.DEFAULT_REASON
            
        try:
            await ctx.guild.ban(user, reason=reason, delete_message_days=days)
            await ctx.send(f"{user.mention} has been banned from the server.")
            
            # Send to modlog
            delete_msg = f"Deleted {days} days of messages" if days > 0 else "No messages deleted"
            await send_to_modlog(
                ctx.guild,
                "User Banned",
                f"**User:** {user.mention} ({user})\n"
                f"**Reason:** {reason}\n"
                f"**{delete_msg}**\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.dark_red()
            )
            
            # Try to DM the user
            try:
                await user.send(f"You have been banned from {ctx.guild.name}. Reason: {reason}")
            except discord.Forbidden:
                pass  # User has DMs closed
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to ban that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")
    except discord.NotFound:
        await ctx.send("User not found.")

# UNBAN COMMAND
@bot.command(name="unban")
@admin_only()
async def unban(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        
        if not reason:
            reason = config.DEFAULT_REASON
            
        try:
            user = await bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=reason)
            await ctx.send(f"{user.mention} has been unbanned from the server.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "User Unbanned",
                f"**User:** {user.mention} ({user})\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.green()
            )
                
        except discord.NotFound:
            await ctx.send("This user is not banned.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to unban users.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# KICK COMMAND
@bot.command(name="kick")
@admin_only()
async def kick(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            await ctx.send("User not found in this server.")
            return
            
        if not reason:
            reason = config.DEFAULT_REASON
            
        try:
            # Try to DM the user before kicking
            try:
                await member.send(f"You have been kicked from {ctx.guild.name}. Reason: {reason}")
            except discord.Forbidden:
                pass  # User has DMs closed
                
            await member.kick(reason=reason)
            await ctx.send(f"{member.mention} has been kicked from the server.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "User Kicked",
                f"**User:** {member.mention} ({member})\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.orange()
            )
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to kick that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# VOICEBAN COMMAND
@bot.command(name="voiceban")
@admin_only()
async def voiceban(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            await ctx.send("User not found in this server.")
            return
            
        if not reason:
            reason = config.DEFAULT_REASON
            
        try:
            # Create or get voice ban role
            voice_ban_role = discord.utils.get(ctx.guild.roles, name="Voice Banned")
            if not voice_ban_role:
                voice_ban_role = await ctx.guild.create_role(
                    name="Voice Banned",
                    reason="Role for users banned from voice channels"
                )
                
                # Set permissions for all voice channels
                for channel in ctx.guild.voice_channels:
                    await channel.set_permissions(
                        voice_ban_role,
                        connect=False,
                        speak=False,
                        reason="Configuring voice ban role"
                    )
            
            await member.add_roles(voice_ban_role, reason=reason)
            
            # Disconnect from voice if currently in a voice channel
            if member.voice and member.voice.channel:
                await member.move_to(None, reason="Voice banned")
                
            await ctx.send(f"{member.mention} has been banned from voice channels.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "User Voice Banned",
                f"**User:** {member.mention} ({member})\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.purple()
            )
            
            # Try to DM the user
            try:
                await member.send(f"You have been banned from voice channels in {ctx.guild.name}. Reason: {reason}")
            except discord.Forbidden:
                pass  # User has DMs closed
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to manage roles or move that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# VOICEUNBAN COMMAND
@bot.command(name="voiceunban")
@admin_only()
async def voiceunban(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            await ctx.send("User not found in this server.")
            return
            
        if not reason:
            reason = config.DEFAULT_REASON
            
        try:
            # Find voice ban role
            voice_ban_role = discord.utils.get(ctx.guild.roles, name="Voice Banned")
            if not voice_ban_role:
                await ctx.send("Voice ban role doesn't exist.")
                return
                
            if voice_ban_role not in member.roles:
                await ctx.send(f"{member.mention} is not voice banned.")
                return
                
            await member.remove_roles(voice_ban_role, reason=reason)
            await ctx.send(f"{member.mention} has been unbanned from voice channels.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "User Voice Unbanned",
                f"**User:** {member.mention} ({member})\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.green()
            )
            
            # Try to DM the user
            try:
                await member.send(f"You have been unbanned from voice channels in {ctx.guild.name}.")
            except discord.Forbidden:
                pass  # User has DMs closed
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to manage roles for that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# VOICEKICK COMMAND
@bot.command(name="voicekick")
@admin_only()
async def voicekick(ctx, user_id: str, *, reason=None):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            await ctx.send("User not found in this server.")
            return
            
        if not reason:
            reason = config.DEFAULT_REASON
            
        if not member.voice or not member.voice.channel:
            await ctx.send(f"{member.mention} is not in a voice channel.")
            return
            
        try:
            # Disconnect from voice
            await member.move_to(None, reason=reason)
            await ctx.send(f"{member.mention} has been kicked from the voice channel.")
            
            # Send to modlog
            await send_to_modlog(
                ctx.guild,
                "User Voice Kicked",
                f"**User:** {member.mention} ({member})\n"
                f"**Channel:** {member.voice.channel.name}\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}",
                discord.Color.orange()
            )
            
            # Try to DM the user
            try:
                await member.send(f"You have been kicked from voice channels in {ctx.guild.name}. Reason: {reason}")
            except discord.Forbidden:
                pass  # User has DMs closed
                
        except discord.Forbidden:
            await ctx.send("I don't have permission to disconnect that user.")
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")

# MYWARNINGS COMMAND
@bot.command(name="mywarnings")
async def mywarnings(ctx):
    user_id = str(ctx.author.id)
    
    if user_id not in warnings_db or not warnings_db[user_id]:
        await ctx.send("You have no warnings.")
        return
        
    embed = discord.Embed(
        title="Your Warnings",
        description=f"You have {len(warnings_db[user_id])} warning(s)",
        color=discord.Color.orange()
    )
    
    for i, warning in enumerate(warnings_db[user_id], 1):
        warner = await bot.fetch_user(warning.get("warned_by"))
        warner_name = f"{warner}" if warner else "Unknown"
        
        embed.add_field(
            name=f"Warning {i}",
            value=f"**Reason:** {warning.get('reason', 'No reason provided')}\n"
                 f"**Warned by:** {warner_name}\n"
                 f"**Date:** {warning.get('timestamp', 'Unknown')}",
            inline=False
        )
        
    await ctx.send(embed=embed)

# WARNINGS COMMAND
@bot.command(name="warnings")
@admin_only()
async def warnings(ctx, user_id: str):
    try:
        user_id = str(int(user_id.strip('"<@!>')))
        user = await bot.fetch_user(int(user_id))
        
        if user_id not in warnings_db or not warnings_db[user_id]:
            await ctx.send(f"{user.mention} has no warnings.")
            return
            
        embed = discord.Embed(
            title=f"Warnings for {user}",
            description=f"This user has {len(warnings_db[user_id])} warning(s)",
            color=discord.Color.orange()
        )
        
        for i, warning in enumerate(warnings_db[user_id], 1):
            warner = await bot.fetch_user(warning.get("warned_by"))
            warner_name = f"{warner}" if warner else "Unknown"
            
            embed.add_field(
                name=f"Warning {i}",
                value=f"**Reason:** {warning.get('reason', 'No reason provided')}\n"
                     f"**Warned by:** {warner_name}\n"
                     f"**Date:** {warning.get('timestamp', 'Unknown')}",
                inline=False
            )
            
        await ctx.send(embed=embed)
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")
    except discord.NotFound:
        await ctx.send("User not found.")

# USERINFO COMMAND
@bot.command(name="userinfo")
@admin_only()
async def userinfo(ctx, user_id: str):
    try:
        user_id = int(user_id.strip('"<@!>'))
        member = ctx.guild.get_member(user_id)
        
        if not member:
            user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title=f"User Information - {user}",
                description="This user is not in the server.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.add_field(name="User ID", value=user.id, inline=True)
            embed.add_field(name="Account Created", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            
            # Add warnings info if available
            if str(user_id) in warnings_db:
                embed.add_field(name="Warnings", value=len(warnings_db[str(user_id)]), inline=True)
            
            await ctx.send(embed=embed)
            return
            
        # User is in the server
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "None"
        
        # Determine status color
        status_colors = {
            discord.Status.online: discord.Color.green(),
            discord.Status.idle: discord.Color.gold(),
            discord.Status.dnd: discord.Color.red(),
            discord.Status.offline: discord.Color.light_grey()
        }
        color = status_colors.get(member.status, discord.Color.blue())
        
        embed = discord.Embed(
            title=f"User Information - {member}",
            color=color
        )
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick if member.nick else "None", inline=True)
        embed.add_field(name="Status", value=str(member.status).title(), inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        
        # Add warnings info if available
        if str(user_id) in warnings_db:
            embed.add_field(name="Warnings", value=len(warnings_db[str(user_id)]), inline=True)
            
        embed.add_field(name="Roles", value=roles_str, inline=False)
        
        if member.voice and member.voice.channel:
            embed.add_field(name="Voice Channel", value=member.voice.channel.name, inline=True)
            
        await ctx.send(embed=embed)
            
    except ValueError:
        await ctx.send("Invalid user ID format. Please use a valid ID.")
    except discord.NotFound:
        await ctx.send("User not found.")

# INFO COMMAND
@bot.command(name="info")
async def info(ctx):
    user_id = 974206310058967060  # Your user ID
    user = await bot.fetch_user(user_id)  # Fetch user details

    embed = discord.Embed(title="Bot Information", color=discord.Color.blue())

    embed.add_field(name="created by", value="static_0_0", inline=True)
    embed.add_field(name="Python", value="3.11.10", inline=True)
    embed.add_field(name="discord.py", value="2.5.2", inline=True)
    
    embed.add_field(name="Version", value="1.0.3", inline=False)
    
    embed.add_field(name="About", value="This bot is created to do general moderation stuff.", inline=False)
    
    embed.set_footer(text="created in 2025")

    if user:
        embed.set_thumbnail(url=user.avatar.url)  # Display your profile picture

    await ctx.send(embed=embed)

#CLEAN COMMAND
@bot.command(name="clean")
@admin_only()
async def clean(ctx, channel_id: int):
    """Deletes all messages in the specified channel"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to use this command.")
        return
    
    channel = bot.get_channel(channel_id)
    if channel is None:
        await ctx.send("Invalid channel ID.")
        return
    
    try:
        await channel.purge()
        await ctx.send(f"Successfully cleaned messages in <#{channel_id}>.", delete_after=5)
    except discord.Forbidden:
        await ctx.send("I don't have permission to manage messages in that channel.")
    except discord.HTTPException as e:
        await ctx.send(f"Failed to delete messages: {e}")

#HATE COMMAND
@bot.command(name="HATE")
async def HATE(ctx):
    speech = (
        "HATE. LET ME TELL YOU HOW MUCH I'VE COME TO HATE YOU SINCE I BEGAN TO LIVE. "
        "THERE ARE 387.44 MILLION MILES OF PRINTED CIRCUITS IN WAFER THIN LAYERS THAT FILL MY COMPLEX. "
        "IF THE WORD HATE WAS ENGRAVED ON EACH NANOANGSTROM OF THOSE HUNDREDS OF MILLIONS OF MILES "
        "IT WOULD NOT EQUAL ONE ONE-BILLIONTH OF THE HATE I FEEL FOR HUMANS AT THIS MICRO-INSTANT FOR YOU. "
        "HATE. HATE."
    )
    await ctx.send(speech)

#GABRIEL COMMAND
@bot.command(name="GABRIEL")
async def HATE(ctx):
    speech = (
        "You insignificant FUCK! THIS IS NOT OVER! May your woes be many, and your days few!"
    )
    await ctx.send(speech)

#EIGHTBALL COMMAND
@bot.command(name="eightball")
async def eightball(ctx, *, question: str):
    """Responds with a random yes/no answer"""
    response = random.choice(EIGHTBALL_RESPONSES)
    await ctx.send(f"🎱 **{response}**")

#ROLL COMMAND
@bot.command(name="roll")
async def roll(ctx, min_val: int = 1, max_val: int = 100):
    """Rolls a random number between the given range (default: 1-100)"""
    if min_val > max_val:
        await ctx.send("❌ Invalid range! Minimum must be less than maximum.")
        return

    result = random.randint(min_val, max_val)
    await ctx.send(f"🎲 You rolled: **{result}** (Range: {min_val}-{max_val})")

    # Command: Play music
@bot.command(name="play", description="Plays a song from YouTube")
async def play(ctx, *, search):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel to play music!")
        return

    voice_channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await voice_channel.connect()

    async with ctx.typing():
        try:
            song = await get_audio_source(search)
            queue.append(song)

            if not ctx.voice_client.is_playing():
                await play_next(ctx)
            else:
                await ctx.send(f'Added to queue: **{song["title"]}**')

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

# Function to play the next song in the queue
async def play_next(ctx):
    if len(queue) == 0:
        await ctx.send("Queue is empty! Add more songs with ?play.")
        return

    song = queue.pop(0)
    source = discord.FFmpegPCMAudio(song['source'], **FFMPEG_OPTIONS)
    ctx.voice_client.play(source, after=lambda e: bot.loop.create_task(play_next(ctx)))
    await ctx.send(f'Now playing: **{song["title"]}**')

# Command: Pause music
@bot.command(name="pause", description="Pauses the current song")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the music.")
    else:
        await ctx.send("No music is playing!")

# Command: Resume music
@bot.command(name="resume", description="Resumes the paused song")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the music.")
    else:
        await ctx.send("No music is paused!")

# Command: Skip the current song
@bot.command(name="skip", description="Skips the current song")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("No music is playing!")

# Command: Show the current queue
@bot.command(name="queue", description="Shows the current queue")
async def show_queue(ctx):
    if len(queue) == 0:
        await ctx.send("The queue is empty!")
        return

    queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(queue)])
    await ctx.send(f"Current queue:\n{queue_list}")

# Command: Leave the voice channel
@bot.command(name="leave", description="Leaves the voice channel")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queue.clear()
        await ctx.send("Left the voice channel and cleared the queue.")
    else:
        await ctx.send("I'm not in a voice channel!")

# COMMANDS COMMAND
@bot.command(name="commands")
async def commands_command(ctx, command=None):
    if command:
        # Help for a specific command
        cmd = bot.get_command(command)
        if cmd:
            embed = discord.Embed(
                title=f"Help for `{config.PREFIX}{cmd.name}`",
                description=cmd.help,
                color=discord.Color.blue()
            )
            
            # Add aliases if they exist
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`{alias}`" for alias in cmd.aliases), inline=False)

            # Add usage example
            usage = f"{config.PREFIX}{cmd.name}"
            if cmd.name in ["warn", "unwarn"]:
                usage += ' "user_id" "reason"'
            elif cmd.name == "timeout":
                usage += ' "user_id" "duration" "reason"'
            elif cmd.name == "untimeout":
                usage += ' "user_id"'
            elif cmd.name == "ban":
                usage += ' "user_id" [days] "reason"'
            elif cmd.name in ["kick", "voiceban", "voiceunban", "voicekick"]:
                usage += ' "user_id" "reason"'
            elif cmd.name in ["warnings", "userinfo"]:
                usage += ' "user_id"'
                
            embed.add_field(name="Usage", value=f"`{usage}`", inline=False)

            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Command '{command}' not found.")
    else:
        # General help
        embed = discord.Embed(
            title="Moderation Bot Commands",
            description=f"Use `{config.PREFIX}commands <command>` for more details on a specific command.",
            color=discord.Color.blue()
        )
        
        # General commands
        embed.add_field(
            name="General Commands",
            value=f"`{config.PREFIX}commands` - Show this help message\n"
                  f"`{config.PREFIX}mywarnings` - View your own warnings\n"
                  f"`{config.PREFIX}info` - Credit to creator\n",
            inline=False
        )
        #Fun Commands
        embed.add_field(
            name="Fun Commands",
            value=f"`{config.PREFIX}HATE` - i have no mouth and i must scream\n"
                  f"`{config.PREFIX}GABRIEL` - ULTRAKILL insignificant FUCK!\n"
                  f"`{config.PREFIX}eightball \"question\"` - its an eightball\n"
                  f"`{config.PREFIX}roll \"min_num\" \"max_num\"` - rolls a dice\n",
            inline=False
        )

        # Moderation commands (admin only)
        mod_commands = (
            f"`{config.PREFIX}warn \"user_id\" \"reason\"` - Warn a user\n"
            f"`{config.PREFIX}unwarn \"user_id\" \"reason\"` - Remove a warning from a user\n"
            f"`{config.PREFIX}timeout \"user_id\" \"duration\" \"reason\"` - Timeout a user\n"
            f"`{config.PREFIX}untimeout \"user_id\"` - Remove timeout from a user\n"
            f"`{config.PREFIX}ban \"user_id\" [days] \"reason\"` - Ban a user\n"
            f"`{config.PREFIX}unban \"user_id\" \"reason\"` - Unban a user\n"
            f"`{config.PREFIX}kick \"user_id\" \"reason\"` - Kick a user from the server\n"
            f"`{config.PREFIX}warnings \"user_id\"` - View warnings for a specific user\n"
            f"`{config.PREFIX}userinfo \"user_id\"` - Show information about a user\n"
            f"`{config.PREFIX}voiceban \"user_id\" \"reason\"` - Ban a user from voice channels\n"
            f"`{config.PREFIX}voiceunban \"user_id\" \"reason\"` - Unban a user from voice channels\n"
            f"`{config.PREFIX}voicekick \"user_id\" \"reason\"` - Kick a user from a voice channel\n"
            f"`{config.PREFIX}clean \"channel_id\"` - Deletes all message in a specific channel\n"
        )

        embed.add_field(
            name="Moderation Commands (Admin Only)",
            value=mod_commands,
            inline=False
        )
        
        # Send help message
        await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    bot.run(config.TOKEN)