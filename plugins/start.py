import asyncio
import os
import random
import secrets
import sys
import time
import urllib.parse
from datetime import datetime, timedelta

import requests
from bot import Bot
from config import *
from database.database import *
from helper_func import *
from helper_func import get_next_image
from pyrogram import Client, __version__, filters
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.types import (
    CallbackQuery,
    ChatInviteLink,
    ChatPrivileges,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

BAN_SUPPORT = f"{BAN_SUPPORT}"

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔ You are banned from using this bot.</b>\n\n"
            "<i>If you believe this is a mistake, please contact support.</i>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT, style="success")]]
            )
        )
    if not await is_subscribed(client, user_id):
        return await not_joined(client, message)

    FILE_AUTO_DELETE = await db.get_del_timer()

    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except Exception:
            pass

    # Check if returning from verification: /start verify_<token>
    if len(message.text.split()) > 1 and message.text.split()[1].startswith("verify_"):
        token = message.text.split()[1].split("verify_", 1)[1]
        token_doc = await db.get_verify_token(token)
        if token_doc:
            expire_sec = await db.get_config_val("VERIFY_EXPIRE_SECONDS", 86400)
            await db.set_user_verified(
                user_id,
                duration_seconds=int(expire_sec),
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or ""
            )
            await db.mark_verify_token_used(token)

            user_mention = message.from_user.mention
            readable_duration = get_readable_time(int(expire_sec))

            verified_success_text = (
                f"🎉 <b>{user_mention} VERIFIED FOR {readable_duration}!</b>\n\n"
                f"✨ <b>Congratulations!</b> Your verification is successful.\n"
                f"🔓 <b>Full Access Unlocked:</b> <code>{readable_duration}</code>\n\n"
                f"<i>Enjoy unlimited seamless access to all files and media!</i> 🚀"
            )
            await message.reply_text(verified_success_text)

            payload = token_doc.get("payload", "")
            if payload and payload != "verify-extend":
                message.text = f"/start {payload}"
                message.command = ["start", payload]
                return await start_command(client, message)
            else:
                return
        else:
            return await message.reply_text("<b>❌ Verification link invalid or expired. Please try again.</b>")

    # Enforce Shortener Verification if enabled (Bypassed for Premium users)
    if not await db.is_premium_user(user_id):
        verify_enabled = await db.get_config_val("VERIFY_ENABLED", False)
        if verify_enabled and len(message.text.split()) > 1:
            if not await db.is_user_verified(user_id):
                import uuid
                payload = message.text.split(maxsplit=1)[1]
                hex_payload = payload.encode().hex()

                token_uid = f"__________{user_id}_sb_{uuid.uuid4()}__________"
                long_random_buf = secrets.token_urlsafe(4096)
                long_payload_token = f"{hex_payload}.{long_random_buf}"

                full_token_key = f"{token_uid}/{long_payload_token}"

                # Base64 urlsafe start parameter mapping for Telegram deep link (strictly <= 64 chars)
                short_token_id = secrets.token_urlsafe(24)

                sess_exp = await db.get_config_val("SESSION_EXPIRE_SECONDS", 3000)
                await db.save_verify_token(full_token_key, user_id, payload, expiry_seconds=int(sess_exp))
                await db.save_verify_token(short_token_id, user_id, payload, expiry_seconds=int(sess_exp))

                base_url = await db.get_config_val("BASE_URL", "https://filestoreproby-9qm4.onrender.com")
                base_url = base_url.rstrip("/")

                verify_link = f"{base_url}/v/{full_token_key}?st={short_token_id}"

                btn = [[InlineKeyboardButton("🚀 Verify Access Now", url=verify_link, style="primary")]]
                return await message.reply_text(
                    f"<b>🛡️ Verification Required</b>\n\n"
                    f"<i>Click the button below to verify and unlock your content.</i>",
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_web_page_preview=True
                )

    text = message.text
    if len(text) > 7:
        try:
            base64_string = text.split(" ", 1)[1]
        except IndexError:
            return

        try:
            string = await decode(base64_string)
        except ValueError:
            return await message.reply_text("<b>❌ Invalid or corrupted file payload token. Please check the link and try again.</b>")

        argument = string.split("-")

        ids = []
        target_db_channel = getattr(client, "db_channel", None)
        target_db_id = target_db_channel.id if target_db_channel else CHANNEL_ID

        clones = await db.get_all_clones()
        clone_cids = [c['db_channel_id'] for c in clones if c.get('db_channel_id')]

        all_candidate_channels = [target_db_id, CHANNEL_ID] + await db.get_db_channels() + clone_cids

        if len(argument) in (2, 3):
            val1 = int(argument[1])
            val2 = int(argument[2]) if len(argument) == 3 else val1

            matched_channel_id = None
            for cid in all_candidate_channels:
                if cid and val1 % abs(cid) == 0:
                    matched_channel_id = cid
                    break

            if not matched_channel_id:
                matched_channel_id = target_db_id

            divisor = abs(matched_channel_id)
            start_id = int(val1 / divisor)
            end_id = int(val2 / divisor)
            ids = range(start_id, end_id + 1) if start_id <= end_id else list(range(start_id, end_id - 1, -1))

            if not hasattr(client, "db_channel") or not client.db_channel:
                class ChannelObj:
                    def __init__(self, cid): self.id = cid
                client.db_channel = ChannelObj(matched_channel_id)
            else:
                client.db_channel.id = matched_channel_id

        temp_msg = await message.reply("<b><blockquote>⏳ Please wait a moment while I prepare your requested files...</blockquote></b>")
        try:
            raw_messages = await get_messages(client, ids, chat_id=matched_channel_id)
            messages = [m for m in raw_messages if m and not getattr(m, "empty", False) and getattr(m, "id", None)]
        except Exception as e:
            await message.reply_text(f"<b><blockquote>❌ An error occurred while retrieving files: {e}</blockquote></b>")
            print(f"Error getting messages: {e}")
            return
        finally:
            await temp_msg.delete()

        from copy_engine import copy_video
        codeflix_msgs = []

        if not messages:
            await message.reply_text("<b>❌ Could not retrieve requested messages from the channel or the requested content has been deleted.</b>")
            return

        cust_name = await db.get_config_val("CUSTOM_BUTTON_NAME", None)
        cust_url = await db.get_config_val("CUSTOM_BUTTON_URL", None)
        if cust_url and not (cust_url.startswith("http://") or cust_url.startswith("https://") or cust_url.startswith("t.me/")):
            cust_url = "https://" + cust_url

        async def send_single_msg(msg):
            if not msg:
                return None
            original_caption = msg.caption.html if (msg.caption and hasattr(msg.caption, "html")) else (msg.caption or "")
            caption = f"{original_caption}\n\n{CUSTOM_CAPTION}" if CUSTOM_CAPTION else original_caption
            reply_markup = msg.reply_markup if DISABLE_CHANNEL_BUTTON else None

            if cust_name and cust_url:
                try:
                    custom_inline_btn = InlineKeyboardButton(cust_name, url=cust_url, style="primary")
                    if reply_markup and hasattr(reply_markup, "inline_keyboard") and reply_markup.inline_keyboard:
                        buttons_matrix = [list(row) for row in reply_markup.inline_keyboard]
                        buttons_matrix.append([custom_inline_btn])
                        reply_markup = InlineKeyboardMarkup(buttons_matrix)
                    else:
                        reply_markup = InlineKeyboardMarkup([[custom_inline_btn]])
                except Exception as b_err:
                    print(f"Error constructing custom button markup: {b_err}")

            try:
                if msg.video:
                    return await copy_video(
                        pyrogram_bot=client,
                        chat_id=message.from_user.id,
                        from_chat_id=client.db_channel.id,
                        message_id=msg.id,
                        caption=caption,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
                else:
                    return await msg.copy(
                        chat_id=message.from_user.id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        protect_content=PROTECT_CONTENT
                    )
            except FloodWait as e:
                await asyncio.sleep(e.x)
                try:
                    if msg.video:
                        return await copy_video(
                            pyrogram_bot=client,
                            chat_id=message.from_user.id,
                            from_chat_id=client.db_channel.id,
                            message_id=msg.id,
                            caption=caption,
                            reply_markup=reply_markup,
                            protect_content=PROTECT_CONTENT
                        )
                    else:
                        return await msg.copy(
                            chat_id=message.from_user.id,
                            caption=caption,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup,
                            protect_content=PROTECT_CONTENT
                        )
                except Exception as fw_err:
                    print(f"Failed retry after FloodWait: {fw_err}")
            except Exception as e:
                print(f"Error sending message {msg.id}: {e}")
                try:
                    return await msg.copy(
                        chat_id=message.from_user.id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        protect_content=PROTECT_CONTENT
                    )
                except Exception as fb_err:
                    print(f"Fallback send failed: {fb_err}")
            return None

        chunk_size = 5
        for i in range(0, len(messages), chunk_size):
            chunk = messages[i:i + chunk_size]
            results = await asyncio.gather(*[send_single_msg(m) for m in chunk])
            for res in results:
                if res:
                    codeflix_msgs.append(res)

        if FILE_AUTO_DELETE > 0:
            notification_msg = await message.reply(
                f"<b><blockquote>⏳ Attention: Your files will automatically vanish in {get_exp_time(FILE_AUTO_DELETE)}. Save or forward them now!</blockquote></b>"
            )

            await asyncio.sleep(FILE_AUTO_DELETE)

            for snt_msg in codeflix_msgs:    
                if snt_msg:
                    try:    
                        await snt_msg.delete()  
                    except Exception as e:
                        print(f"Error deleting message {snt_msg.id}: {e}")

            try:
                retrieve_active = await db.get_retrieve_status()
                if retrieve_active:
                    reload_url = (
                        f"https://telegram.me/{await get_bot_username(client)}?start={message.command[1]}"
                        if message.command and len(message.command) > 1
                        else None
                    )
                    keyboard = InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔄 Get File Again", url=reload_url, style="success")]]
                    ) if reload_url else None

                    await notification_msg.edit(
                        CUSTOM_DELETE_ALERT,
                        reply_markup=keyboard
                    )
                else:
                    await notification_msg.delete()
            except Exception as e:
                print(f"Error updating or deleting notification message: {e}")
    else:
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton('📢 Main Channel', url='https://telegram.me/anizoneflix', style="primary"),
                InlineKeyboardButton('💬 Support', url='https://telegram.me/anizoneflix', style="primary")],
                [InlineKeyboardButton('ℹ️ About', callback_data='about', style="primary"),
                InlineKeyboardButton('📜 Help', callback_data='help', style="primary")],
                [InlineKeyboardButton("🚀 Join Updates Channel", url='https://telegram.me/anizoneflix', style="success")]
            ]
        )
        caption = START_MSG
        if "{first}" in caption: caption = caption.replace("{first}", message.from_user.first_name or "")
        if "{last}" in caption: caption = caption.replace("{last}", message.from_user.last_name or "")
        if "{username}" in caption: caption = caption.replace("{username}", "" if not message.from_user.username else '@' + message.from_user.username)
        if "{mention}" in caption: caption = caption.replace("{mention}", message.from_user.mention or "")
        if "{id}" in caption: caption = caption.replace("{id}", str(message.from_user.id))

        await client.send_photo(
            chat_id=message.chat.id,
            photo=get_next_image(message.chat.id),
            caption=caption,
            reply_markup=reply_markup,
            has_spoiler=True,
            message_effect_id=5104841245755180586
        )
        
        return

chat_data_cache = {}

async def not_joined(client: Client, message: Message):
    temp = await message.reply("<b><blockquote>⏳ Checking channel subscriptions... Please wait!</blockquote></b>")

    user_id = message.from_user.id
    buttons = []
    count = 0

    try:
        all_channels = await db.show_channels()
        for total, chat_id in enumerate(all_channels, start=1):
            mode = await db.get_channel_mode(chat_id)

            if not await is_sub(client, user_id, chat_id):
                try:
                    if chat_id in chat_data_cache:
                        data = chat_data_cache[chat_id]
                    else:
                        data = await client.get_chat(chat_id)
                        chat_data_cache[chat_id] = data

                    name = data.title

                    if mode == "on":
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            creates_join_request=True,
                            name=f"FSub_Req_{user_id}_{int(time.time())}",
                            expire_date=datetime.now(timezone.utc) + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link
                    else:
                        invite = await client.create_chat_invite_link(
                            chat_id=chat_id,
                            member_limit=1,
                            name=f"FSub_User_{user_id}_{int(time.time())}",
                            expire_date=datetime.now(timezone.utc) + timedelta(seconds=FSUB_LINK_EXPIRY) if FSUB_LINK_EXPIRY else None
                        )
                        link = invite.invite_link

                    buttons.append([InlineKeyboardButton(text=f"{name}", url=link, style="primary")])
                    count += 1

                except Exception as e:
                    print(f"Error with chat {chat_id}: {e}")
                    return await temp.edit(
                        f"<b><i>! Error: Please contact support to resolve issues: @anizoneflix</i></b>\n"
                        f"<blockquote expandable><b>Reason:</b> {e}</blockquote>"
                    )

        try:
            buttons.append([
                InlineKeyboardButton(
                    text='🔄 Try Again',
                    url=f"https://telegram.me/{await get_bot_username(client)}?start={message.command[1]}",
                    style="success"
                )
            ])
        except IndexError:
            pass

        caption = FORCE_MSG
        if "{first}" in caption: caption = caption.replace("{first}", message.from_user.first_name or "")
        if "{last}" in caption: caption = caption.replace("{last}", message.from_user.last_name or "")
        if "{username}" in caption: caption = caption.replace("{username}", "" if not message.from_user.username else '@' + message.from_user.username)
        if "{mention}" in caption: caption = caption.replace("{mention}", message.from_user.mention or "")
        if "{id}" in caption: caption = caption.replace("{id}", str(message.from_user.id))

        await message.reply_photo(
            photo=get_next_image(message.chat.id),
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            has_spoiler=True
        )

    except Exception as e:
        print(f"Final Error: {e}")
        await temp.edit(
            f"<b><i>! Eʀʀᴏʀ, Cᴏɴᴛᴀᴄᴛ ᴅᴇᴠᴇʟᴏᴘᴇʀ ᴛᴏ sᴏʟᴠᴇ ᴛʜᴇ ɪssᴜᴇs @anizoneflix</i></b>\n"
            f"<blockquote expandable><b>Rᴇᴀsᴏɴ:</b> {e}</blockquote>"
        )

@Bot.on_message(filters.command('commands') & filters.private & admin)
async def bcmd(bot: Bot, message: Message):        
    reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close", style="danger")]])
    await message.reply(text=CMD_TXT, reply_markup=reply_markup, quote=True)

@Bot.on_message(filters.command('verify') & filters.private)
async def verify_command(client: Client, message: Message):
    user_id = message.from_user.id
    import uuid
    is_ver = await db.is_user_verified(user_id)

    rem_time_str = "None"
    if is_ver:
        v_doc = await db.get_verified_user(user_id)
        if v_doc and v_doc.get("expire_at"):
            exp_at = v_doc["expire_at"]
            now_utc = datetime.now(timezone.utc)
            if hasattr(exp_at, "tzinfo") and exp_at.tzinfo is None:
                exp_at = exp_at.replace(tzinfo=timezone.utc)
            rem_sec = int((exp_at - now_utc).total_seconds())
            if rem_sec > 0:
                rem_time_str = get_readable_time(rem_sec)

    token_uid = f"__________{user_id}_sb_{uuid.uuid4()}__________"
    hex_payload = "verify-extend".encode().hex()
    long_random_buf = secrets.token_urlsafe(4096)
    full_token_key = f"{token_uid}/{hex_payload}.{long_random_buf}"

    short_token_id = secrets.token_urlsafe(24)

    sess_exp = await db.get_config_val("SESSION_EXPIRE_SECONDS", 3000)
    await db.save_verify_token(full_token_key, user_id, "verify-extend", expiry_seconds=int(sess_exp))
    await db.save_verify_token(short_token_id, user_id, "verify-extend", expiry_seconds=int(sess_exp))

    base_url = await db.get_config_val("BASE_URL", "https://filestoreproby-9qm4.onrender.com")
    base_url = base_url.rstrip("/")

    verify_link = f"{base_url}/v/{full_token_key}?st={short_token_id}"

    btn = [[InlineKeyboardButton("🚀 Verify / Extend Access Now", url=verify_link, style="primary")]]
    status_text = f"🟢 Currently Verified (Remaining: <code>{rem_time_str}</code>)" if is_ver else "🔴 Not Verified"
    await message.reply_text(
        f"<b>🛡️ Verification Center</b>\n\n"
        f"<b>• Your Status:</b> {status_text}\n\n"
        "<i>Click the button below to verify or extend your active access period!</i>",
        reply_markup=InlineKeyboardMarkup(btn),
        disable_web_page_preview=True
    )
