# =====================================================================================##
#
#  ██╗░░██╗███╗░░██╗██████╗░░█████╗░████████╗███████╗██████╗░
#  ██║░░██║████╗░██║██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
#  ██║░░██║██╔██╗██║██████╔╝███████║░░░██║░░░█████╗░░██║░░██║
#  ██║░░██║██║╚████║██╔══██╗██╔══██║░░░██║░░░██╔══╝░░██║░░██║
#  ╚██████╔╝██║░╚███║██║░░██║██║░░██║░░░██║░░░███████╗██████╔╝
#  ░╚═════╝░╚═╝░░╚══╝╚═╝░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═════╝░
#
#  ░██████╗░██████╗░██████╗░███████╗██████╗░
#  ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
#  ██║░░░░░██║░░░██║██║░░██║█████╗░░██████╔╝
#  ██║░░░░░██║░░░██║██║░░██║██╔══╝░░██╔══██╗
#  ╚██████╗╚██████╔╝██████╔╝███████╗██║░░██║
#  ░╚═════╝░╚═════╝░╚═════╝░╚══════╝╚═╝░░╚═╝
#
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://telegram.me/anizoneflix
#=====================================================================================##

import asyncio
import os
import random
import sys
import time
from pyrogram import Client, filters, __version__
from pyrogram.enums import ParseMode, ChatAction, ChatMemberStatus, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, ChatMemberUpdated, ChatPermissions
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant, InviteHashEmpty, ChatAdminRequired, PeerIdInvalid, UserIsBlocked, InputUserDeactivated, UserNotParticipant
from bot import Bot
from config import *
from helper_func import *
from database.database import *
from plugins.anizoneflix import check_admin_or_owner

@Bot.on_message(filters.command('fsub_mode') & filters.private)
async def change_force_sub_mode(client, message):
    if not await check_admin_or_owner(message):
        return

    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>", quote=True)
    channels = await db.show_channels()

    if not channels:
        return await temp.edit("<b>❌ No force-sub channels found.</b>")

    buttons = []
    for ch_id in channels:
        try:
            chat = await client.get_chat(ch_id)
            mode = await db.get_channel_mode(ch_id)
            status = "🟢" if mode == "on" else "🔴"
            buttons.append([InlineKeyboardButton(f"{status} {chat.title}", callback_data=f"rfs_ch_{ch_id}", style="primary")])
        except:
            buttons.append([InlineKeyboardButton(f"⚠️ {ch_id} (Unavailable)", callback_data=f"rfs_ch_{ch_id}", style="danger")])

    buttons.append([InlineKeyboardButton("Close ✖️", callback_data="close", style="danger")])
    await temp.edit(
        "<b>⚡ Select a channel to toggle Force-Sub Mode:</b>",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

@Bot.on_chat_member_updated()
async def handle_chat_members(client, chat_member_updated: ChatMemberUpdated):
    chat_id = chat_member_updated.chat.id

    if await db.reqChannel_exist(chat_id):
        old_member = chat_member_updated.old_chat_member
        if not old_member:
            return
        if old_member.status == ChatMemberStatus.MEMBER:
            user_id = old_member.user.id
            if await db.req_user_exist(chat_id, user_id):
                await db.del_req_user(chat_id, user_id)

@Bot.on_chat_join_request()
async def handle_join_request(client, chat_join_request):
    chat_id = chat_join_request.chat.id
    user_id = chat_join_request.from_user.id

    if await db.reqChannel_exist(chat_id):
        if not await db.req_user_exist(chat_id, user_id):
            await db.req_user(chat_id, user_id)

@Bot.on_message(filters.command('addchnl') & filters.private)
async def add_force_sub(client, message):
    if not await check_admin_or_owner(message):
        return

    temp = await message.reply("Wait a sec...", quote=True)
    args = message.text.split(maxsplit=1)
    if len(args) != 2:
        return await temp.edit("Usage:\n<code>/addchnl -100xxxxxxxxxx</code>")

    try:
        chat_id = int(args[1])
    except ValueError:
        return await temp.edit("❌ Invalid chat ID!")

    all_chats = await db.show_channels()
    if chat_id in [c if isinstance(c, int) else c[0] for c in all_chats]:
        return await temp.edit(f"Already exists:\n<code>{chat_id}</code>")

    try:
        chat = await client.get_chat(chat_id)
        if chat.type not in [ChatType.CHANNEL, ChatType.SUPERGROUP]:
            return await temp.edit("❌ Only channels/supergroups allowed.")

        bot_member = await client.get_chat_member(chat.id, "me")
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await temp.edit("❌ Bot must be admin in that chat.")

        try:
            link = await client.export_chat_invite_link(chat.id)
        except Exception:
            link = f"https://telegram.me/{chat.username}" if chat.username else f"https://telegram.me/c/{str(chat.id)[4:]}"

        if await db.add_channel(chat_id):
            return await temp.edit(
                f"✅ Added Successfully!\n\n"
                f"<b>Name:</b> <a href='{link}'>{chat.title}</a>\n"
                f"<b>ID:</b> <code>{chat_id}</code>",
                disable_web_page_preview=True
            )
        else:
            return await temp.edit("❌ Failed to add channel to database. Check if DATABASE_URL is correct.")

    except Exception as e:
        return await temp.edit(f"❌ Failed to add chat:\n<code>{chat_id}</code>\n\n<i>{e}</i>")

@Bot.on_message(filters.command('delchnl') & filters.private)
async def del_force_sub(client, message):
    if not await check_admin_or_owner(message):
        return

    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>", quote=True)
    args = message.text.split(maxsplit=1)
    all_channels = await db.show_channels()

    if len(args) != 2:
        return await temp.edit("<b>Usage:</b> <code>/delchnl <channel_id | all></code>")

    if args[1].lower() == "all":
        if not all_channels:
            return await temp.edit("<b>❌ No force-sub channels found.</b>")
        for ch_id in all_channels:
            await db.del_channel(ch_id)
        return await temp.edit("<b>✅ All force-sub channels have been removed.</b>")

    try:
        ch_id = int(args[1])
    except ValueError:
        return await temp.edit("<b>❌ Invalid Channel ID</b>")

    if ch_id in all_channels:
        await db.rem_channel(ch_id)
        return await temp.edit(f"<b>✅ Channel removed:</b> <code>{ch_id}</code>")
    else:
        return await temp.edit(f"<b>❌ Channel not found in force-sub list:</b> <code>{ch_id}</code>")

@Bot.on_message(filters.command('listchnl') & filters.private)
async def list_force_sub_channels(client, message):
    if not await check_admin_or_owner(message):
        return

    temp = await message.reply("<b><i>ᴡᴀɪᴛ ᴀ sᴇᴄ..</i></b>", quote=True)
    channels = await db.show_channels()

    if not channels:
        return await temp.edit("<b>❌ No force-sub channels found.</b>")

    result = "<b>⚡ Force-sub Channels:</b>\n\n"
    for ch_id in channels:
        try:
            chat = await client.get_chat(ch_id)
            link = chat.invite_link or await client.export_chat_invite_link(chat.id)
            result += f"<b>•</b> <a href='{link}'>{chat.title}</a> [<code>{ch_id}</code>]\n"
        except Exception:
            result += f"<b>•</b> <code>{ch_id}</code> — <i>Unavailable</i>\n"

    await temp.edit(
        result,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Close ✖️", callback_data="close", style="danger")]])
    )

# =====================================================================================##
#                         ✨ MADE BY ANIZONEFLIX ✨
#                  Join Updates Channel: https://telegram.me/anizoneflix
#====================================================================================##
