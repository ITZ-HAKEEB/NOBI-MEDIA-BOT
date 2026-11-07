import os
import re
import html
import asyncio
import logging
import tempfile

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery
)

from motor.motor_asyncio import AsyncIOMotorClient
import yt_dlp
import config


# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================================
# DATABASE
# ==========================================================

db_client = AsyncIOMotorClient(config.MONGO_DB_URI)

db = db_client["all_downloader_bot"]

users_col = db["users"]


# ==========================================================
# BOT
# ==========================================================

app = Client(
    "AllDownloaderBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)


# ==========================================================
# WELCOME MESSAGE
# ==========================================================

DEFAULT_WELCOME_TEXT = """
<blockquote>
<b>✦ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ɴᴏʙɪ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ✦</b>

ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴍᴇᴅɪᴀ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴀssɪsᴛᴀɴᴛ!

━━━━━━━━━━━━━━━━━━

✧ sᴜᴘᴘᴏʀᴛᴇᴅ ᴘʟᴀᴛғᴏʀᴍs:

• ɪɴsᴛᴀɢʀᴀᴍ
• ғᴀᴄᴇʙᴏᴏᴋ
• ʏᴏᴜᴛᴜʙᴇ

━━━━━━━━━━━━━━━━━━

⚡ ғᴀsᴛ ᴘʀᴏᴄᴇssɪɴɢ
🎬 ʜɪɢʜ Qᴜᴀʟɪᴛʏ ᴠɪᴅᴇᴏs
🔒 sɪᴍᴘʟᴇ & ᴇᴀsʏ ᴛᴏ ᴜsᴇ

<b>➥ sᴇɴᴅ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʟɪɴᴋ!</b>
</blockquote>
"""

WELCOME_TEXT = (
    getattr(config, "WELCOME_TEXT", None)
    or DEFAULT_WELCOME_TEXT
)


# ==========================================================
# FORCE SUBSCRIPTION
# ==========================================================

def normalize_channel(value):

    if not value:
        return None

    value = str(value).strip()

    value = value.replace("https://t.me/", "")
    value = value.replace("http://t.me/", "")
    value = value.replace("t.me/", "")
    value = value.split("/")[0].split("?")[0]

    if not value:
        return None

    if value.lstrip("-").isdigit():
        return int(value)

    return value if value.startswith("@") else f"@{value}"


def get_channel_candidates():

    candidates = []

    channel_id = normalize_channel(
        getattr(config, "CHANNEL_ID", None)
    )

    channel_username = normalize_channel(
        getattr(config, "CHANNEL_USERNAME", None)
    )

    if channel_id is not None:
        candidates.append(channel_id)

    if (
        channel_username is not None
        and channel_username not in candidates
    ):
        candidates.append(channel_username)

    return candidates


def get_join_url():

    username = normalize_channel(
        getattr(config, "CHANNEL_USERNAME", None)
    )

    if not username or isinstance(username, int):
        return None

    return f"https://t.me/{username.lstrip('@')}"


def get_join_keyboard():

    buttons = []

    join_url = get_join_url()

    if join_url:
        buttons.append([
            InlineKeyboardButton(
                "📢 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ",
                url=join_url
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔄 ᴠᴇʀɪғʏ & ᴄᴏɴᴛɪɴᴜᴇ",
            callback_data="check_sub"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def is_subscribed(client, user_id):

    candidates = get_channel_candidates()

    if not candidates:
        logger.warning("Force subscription channel not configured")
        return True

    for channel in candidates:

        try:

            member = await client.get_chat_member(
                channel,
                user_id
            )

            status = member.status

            status_name = getattr(status, "name", None)

            if not status_name:
                status_name = str(status).split(".")[-1]

            status_name = status_name.lower()

            if status_name in (
                "member",
                "administrator",
                "owner",
                "creator"
            ):

                logger.info(
                    "User %s verified in %s",
                    user_id,
                    channel
                )

                return True

        except Exception:

            logger.exception(
                "Membership check failed for channel %s",
                channel
            )

    return False


async def send_join_message(message):

    await message.reply_text(
        """
<blockquote>
<b>🔐 ᴄʜᴀɴɴᴇʟ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ</b>

ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ, ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴏᴜʀ ᴏғғɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟ.

➜ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ.
➜ ᴄʟɪᴄᴋ ᴠᴇʀɪғʏ & ᴄᴏɴᴛɪɴᴜᴇ.

✦ ᴀʟʀᴇᴀᴅʏ ᴀ ᴍᴇᴍʙᴇʀ?
ᴊᴜsᴛ ᴄʟɪᴄᴋ ᴠᴇʀɪғʏ!
</blockquote>
        """,
        reply_markup=get_join_keyboard()
    )


# ==========================================================
# START
# ==========================================================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):

    user = message.from_user
    user_id = user.id

    user_doc = await users_col.find_one(
        {"user_id": user_id}
    )

    if not user_doc:

        await users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "first_name": user.first_name,
                    "username": user.username
                }
            },
            upsert=True
        )

        log_channel = getattr(
            config,
            "LOG_CHANNEL",
            None
        )

        if log_channel:

            name = html.escape(user.first_name or "Unknown")

            username = (
                f"@{html.escape(user.username)}"
                if user.username else "None"
            )

            try:

                await client.send_message(
                    log_channel,
                    (
                        "<b>👤 ɴᴇᴡ ᴜsᴇʀ</b>\n\n"
                        f"• ɴᴀᴍᴇ: {name}\n"
                        f"• ᴜsᴇʀɴᴀᴍᴇ: {username}\n"
                        f"• ɪᴅ: <code>{user_id}</code>"
                    )
                )

            except Exception:
                logger.exception("New user log failed")

    else:

        await users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "first_name": user.first_name,
                    "username": user.username
                }
            }
        )

    if not await is_subscribed(client, user_id):

        await send_join_message(message)
        return

    await message.reply_text(WELCOME_TEXT)


# ==========================================================
# VERIFY BUTTON
# ==========================================================

@app.on_callback_query(filters.regex(r"^check_sub$"))
async def check_subscription_callback(client, callback):

    user_id = callback.from_user.id

    subscribed = await is_subscribed(
        client,
        user_id
    )

    if not subscribed:

        await callback.answer(
            "❌ Join the correct channel first!",
            show_alert=True
        )

        return

    await callback.answer(
        "✅ Verification successful!"
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.reply_text(
        """
<blockquote>
<b>🎉 ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!</b>

✦ ʏᴏᴜ ᴀʀᴇ ɴᴏᴡ ᴠᴇʀɪғɪᴇᴅ.
✦ ᴇɴᴊᴏʏ ᴏᴜʀ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ!
</blockquote>
        """
    )

    await callback.message.reply_text(
        WELCOME_TEXT
    )


# ==========================================================
# STATISTICS
# ==========================================================

@app.on_message(
    filters.command("statistics")
    & filters.private
    & filters.user(config.OWNER_ID)
)
async def statistics_command(client, message):

    total_users = await users_col.count_documents({})

    await message.reply_text(
        f"""
<blockquote>
<b>📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs</b>

👥 ᴛᴏᴛᴀʟ ᴜsᴇʀs:
<code>{total_users}</code>

✦ ᴅᴀᴛᴀʙᴀsᴇ: ᴍᴏɴɢᴏᴅʙ
✦ sᴛᴀᴛᴜs: ᴀᴄᴛɪᴠᴇ
</blockquote>
        """
    )


# ==========================================================
# BROADCAST
# ==========================================================

@app.on_message(
    filters.command("broadcast")
    & filters.private
    & filters.user(config.OWNER_ID)
)
async def broadcast_command(client, message):

    if not message.reply_to_message:

        await message.reply_text(
            "⚠️ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ."
        )

        return

    broadcast_msg = message.reply_to_message

    total_users = await users_col.count_documents({})

    status_msg = await message.reply_text(
        f"🚀 ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀʀᴛᴇᴅ!\nᴛᴏᴛᴀʟ: <code>{total_users}</code>"
    )

    success = 0
    failed = 0

    async for user in users_col.find({}):

        try:

            await broadcast_msg.copy(
                chat_id=user["user_id"]
            )

            success += 1

            await asyncio.sleep(0.1)

        except Exception:

            failed += 1

            logger.exception(
                "Broadcast failed for %s",
                user["user_id"]
            )

    await status_msg.edit_text(
        f"""
<blockquote>
<b>✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>

👥 ᴛᴏᴛᴀʟ: <code>{total_users}</code>
✅ sᴜᴄᴄᴇss: <code>{success}</code>
❌ ғᴀɪʟᴇᴅ: <code>{failed}</code>
</blockquote>
        """
    )


# ==========================================================
# YT-DLP COOKIE CONFIGURATION
# ==========================================================

def get_ytdlp_cookie_file():

    # Optional cookie contents supplied through Heroku Config Vars.
    # Use only your own account's cookies and keep them private.

    cookie_data = os.getenv("YTDLP_COOKIES", "").strip()

    if cookie_data:

        cookie_path = "/tmp/nobi_instagram_cookies.txt"

        with open(cookie_path, "w", encoding="utf-8") as file:
            file.write(cookie_data)

        return cookie_path

    # Alternatively, use a securely provided cookie file path.

    cookie_path = os.getenv(
        "YTDLP_COOKIES_FILE",
        ""
    ).strip()

    if cookie_path and os.path.isfile(cookie_path):
        return cookie_path

    return None


# ==========================================================
# DOWNLOAD FUNCTION
# ==========================================================

def download_media(url, download_dir):

    cookie_file = get_ytdlp_cookie_file()

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(
            download_dir,
            "%(id)s.%(ext)s"
        ),
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        }
    }

    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        if not info:
            raise Exception("No downloadable media found.")

        file_path = ydl.prepare_filename(info)

        if not os.path.isfile(file_path):

            # Handle a possible alternate extension.
            base = os.path.splitext(file_path)[0]

            matches = [
                os.path.join(download_dir, name)
                for name in os.listdir(download_dir)
                if os.path.splitext(name)[0] == os.path.basename(base)
            ]

            if matches:
                file_path = matches[0]

        if not os.path.isfile(file_path):
            raise Exception("Downloaded file was not found.")

        return file_path


# ==========================================================
# ERROR MESSAGE HELPER
# ==========================================================

def get_download_error(error):

    error = str(error)

    lower_error = error.lower()

    if any(word in lower_error for word in (
        "rate-limit",
        "rate limit",
        "login required",
        "cookies",
        "requested content is not available"
    )):

        return (
            "Instagram is requiring login or has temporarily "
            "restricted this request.\n\n"
            "Please try again later. If the content requires "
            "login, configure your own authorized cookies securely."
        )

    if "private" in lower_error:

        return (
            "This content is private or unavailable to this account."
        )

    if "unsupported url" in lower_error:

        return (
            "This link is not supported by the current downloader."
        )

    if "ffmpeg" in lower_error:

        return (
            "The media requires FFmpeg. Please check your Heroku build."
        )

    return error[:1200]


# ==========================================================
# DOWNLOADER HANDLER
# ==========================================================

@app.on_message(
    filters.text
    & filters.private
    & ~filters.command([
        "start",
        "broadcast",
        "statistics"
    ])
)
async def downloader_handler(client, message):

    if not message.from_user:
        return

    user_id = message.from_user.id

    url = message.text.strip()

    url_pattern = re.compile(
        r"^https?://[^\s]+$",
        re.IGNORECASE
    )

    if not url_pattern.match(url):
        return

    # Subscription check

    if not await is_subscribed(client, user_id):

        await send_join_message(message)
        return

    # Processing status

    status_msg = await message.reply_text(
        """
<blockquote>
📥 <b>ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴠɪᴅᴇᴏ...</b>

✦ ʟɪɴᴋ ᴄʜᴇᴄᴋɪɴɢ
✦ ᴍᴇᴅɪᴀ ᴘʀᴏᴄᴇssɪɴɢ

ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ!
</blockquote>
        """
    )

    try:
        await message.react("👀")
    except Exception:
        pass

    download_dir = "downloads"

    os.makedirs(
        download_dir,
        exist_ok=True
    )

    file_path = None

    try:

        loop = asyncio.get_running_loop()

        file_path = await loop.run_in_executor(
            None,
            download_media,
            url,
            download_dir
        )

        if not file_path or not os.path.isfile(file_path):

            raise Exception("Download file not found.")

        await status_msg.edit_text(
            "📤 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ᴠɪᴅᴇᴏ...</b>"
        )

        await message.reply_video(
            video=file_path,
            caption=(
                "✅ <b>ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                "✦ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ɴᴏʙɪ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ"
            )
        )

        await status_msg.delete()

    except Exception as e:

        logger.exception(
            "Media download failed for user %s",
            user_id
        )

        friendly_error = html.escape(
            get_download_error(e)
        )

        try:

            await status_msg.edit_text(
                "❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ!</b>\n\n"
                f"<blockquote>{friendly_error}</blockquote>"
            )

        except Exception:
            logger.exception("Could not edit download status")

    finally:

        if file_path and os.path.isfile(file_path):

            try:
                os.remove(file_path)
            except Exception:
                logger.exception("Could not remove downloaded file")


# ==========================================================
# BOT START
# ==========================================================

if __name__ == "__main__":

    print("Nobi Downloader Bot is starting...")

    app.run()
