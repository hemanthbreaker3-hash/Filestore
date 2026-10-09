import os
from os import environ, getenv
import logging
from dotenv import load_dotenv

load_dotenv()
from logging.handlers import RotatingFileHandler

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "8672264237:AAGEGqUMNVoDHQb6eypnvZpmNMznSp_7xFs")
APP_ID = int(os.environ.get("APP_ID", "22266643"))
API_HASH = os.environ.get("API_HASH", "7d0b85b4146034511b8776ed7ff99de4")

CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
OWNER = os.environ.get("OWNER", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
PORT = os.environ.get("PORT", "8001")
DB_URI = os.environ.get("DATABASE_URL", "")

if not TG_BOT_TOKEN:
    logging.warning("TG_BOT_TOKEN is not set!")
if APP_ID == 0:
    logging.warning("APP_ID is not set!")
if not API_HASH:
    logging.warning("API_HASH is not set!")
if not DB_URI:
    logging.warning("DATABASE_URL is not set!")
DB_NAME = os.environ.get("DB_NAME", "AniZoneFlix")
FSUB_LINK_EXPIRY = int(os.getenv("FSUB_LINK_EXPIRY", "10"))
BAN_SUPPORT = os.environ.get("BAN_SUPPORT", "https://t.me/anizoneflix")
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "200"))
START_PIC = os.environ.get("START_PIC", "https://graph.org/file/0591ce5558c3ec8fe7612-263292508134daf3e1.jpg")
FORCE_PIC = os.environ.get("FORCE_PIC", "https://graph.org/file/fdc4357abfaba23255e98-24d1bbfa3888cdfcfe.jpg")

HELP_TXT = "<b>✨ AniZoneFlix Help Directory</b>\n\n<b><blockquote>Welcome to AniZoneFlix! Explore and manage files, verification settings, shorteners, clone bots, and custom commands with ease. Use the interactive menu below or type /help to browse all commands.</blockquote></b>\n\n<b>• Main Channel:</b> @anizoneflix"

ABOUT_TXT = """<b>🤖 AniZoneFlix FileStore Bot — About</b>\n\n<b><blockquote>⚡ Status: Online 24/7\n🚀 Features: Direct File Access, Batch Links, Shorteners & Multi-DB Channels\n🔗 Updates Channel: @anizoneflix</blockquote></b>\n\n<b><blockquote>◈ Creator & Developer: <a href="https://t.me/anizoneflix">AniZoneFlix</a></blockquote></b>"""
START_MSG = os.environ.get("START_MESSAGE", "<b>👋 Hello {first}!</b>\n\n<b><blockquote>Welcome to AniZoneFlix FileStore Bot! I store files securely and deliver them instantly via secure shareable links.</blockquote></b>\n\n<b><blockquote>📢 Please join our updates channel to stay informed!</blockquote></b>")
FORCE_MSG = os.environ.get("FORCE_SUB_MESSAGE", "<b>🚨 Channel Subscription Required!</b>\n\n<b><blockquote>To access your requested files, please join our required channels listed below. Once joined, click 'Try Again' to proceed.</blockquote></b>\n\n<b><blockquote>💡 Use /help if you need assistance!</blockquote></b>")

CMD_TXT = """<b><blockquote>⚙️ Admin Commands Directory:</blockquote></b>\n<b>• /delete :</b> Delete content from DB channel\n<b>• /dlt_time :</b> Set auto-delete duration\n<b>• /check_dlt_time :</b> View active auto-delete timer\n<b>• /dbroadcast :</b> Broadcast document/video to users\n<b>• /ban :</b> Ban a user\n<b>• /unban :</b> Unban a user\n<b>• /banlist :</b> List all banned users\n<b>• /addchnl :</b> Add Force Subscription channel\n<b>• /delchnl :</b> Remove Force Subscription channel\n<b>• /listchnl :</b> List Force Subscription channels\n<b>• /fsub_mode :</b> Toggle Force Subscription mode\n<b>• /pbroadcast :</b> Broadcast photo to all users\n<b>• /add_admin :</b> Add a new admin\n<b>• /deladmin :</b> Remove an admin\n<b>• /admins :</b> List active admins"""
CUSTOM_CAPTION = os.environ.get("CUSTOM_CAPTION", "<b>• By @anizoneflix</b>")
CUSTOM_DELETE_ALERT = os.environ.get("CUSTOM_DELETE_ALERT", "<b><blockquote>⚠️ Your file has been automatically deleted for security. Click below to request access again.</blockquote></b>")
PROTECT_CONTENT = True if os.environ.get('PROTECT_CONTENT', "False") == "True" else False 
DISABLE_CHANNEL_BUTTON = os.environ.get("DISABLE_CHANNEL_BUTTON", None) == 'True'
BOT_STATS_TEXT = "<b>📊 AniZoneFlix Bot Statistics:</b>\n\n<b><blockquote>• Uptime: <code>{uptime}</code>\n• CPU Usage: <code>{cpu}%</code>\n• RAM Usage: <code>{ram}%</code>\n• Total Users: <code>{users}</code></blockquote></b>"
USER_REPLY_TEXT = "<b><blockquote>⚠️ Access Denied: You do not have permission to use this command.</blockquote></b>"
USER_ROAST_TEXT = "<b><blockquote>⚠️ Unauthorized Action: Admin privileges are required.</blockquote></b>"

LOG_FILE_NAME = "filesharingbot.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
