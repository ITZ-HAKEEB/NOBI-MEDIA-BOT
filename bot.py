import os
import re
import html
import asyncio
import logging
import tempfile
import shutil

from urllib.parse import urlparse

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton
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

db_client = AsyncIOMotorClient(
    config.MONGO_DB_URI,
    serverSelectionTimeoutMS=10000
)

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
# SETTINGS
# ==========================================================

MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024
MAX_VIDEO_HEIGHT = 1080

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)

SUPPORTED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "fb.watch"
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
🎬 ᴜᴘ ᴛᴏ 1080ᴘ ᴠɪᴅᴇᴏ
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
                return True

        except Exception:

            logger.exception(
                "Membership check failed for %s",
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

    await callback.message.reply_text(WELCOME_TEXT)


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
# COOKIE CONFIGURATION
# ==========================================================

def get_ytdlp_cookie_file():

    cookie_data = os.getenv(
        "YTDLP_COOKIES",
        ""
    ).strip()

    if cookie_data:

        cookie_path = "/tmp/nobi_cookies.txt"

        with open(
            cookie_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(cookie_data)

        return cookie_path

    cookie_path = os.getenv(
        "YTDLP_COOKIES_FILE",
        ""
    ).strip()

    if cookie_path and os.path.isfile(cookie_path):
        return cookie_path

    return None


# ==========================================================
# URL VALIDATION
# ==========================================================

def is_supported_url(url):

    try:

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        hostname = (parsed.hostname or "").lower()

        return any(
            hostname == domain
            or hostname.endswith("." + domain)
            for domain in SUPPORTED_DOMAINS
        )

    except Exception:

        return False


# ==========================================================
# DOWNLOAD FUNCTION
# ==========================================================

def download_media(url, download_dir):

    cookie_file = get_ytdlp_cookie_file()

    ydl_opts = {

        # HD video + best available audio
        "format": (
            "bestvideo[height<=1080][ext=mp4]"
            "+bestaudio[ext=m4a]"
            "/best[height<=1080][ext=mp4]"
            "/best[height<=1080]"
            "/best"
        ),

        "format_sort": [
            "res:1080",
            "vcodec:h264",
            "acodec:m4a"
        ],

        # Merge video and audio into MP4
        "merge_output_format": "mp4",

        # Download speed
        "concurrent_fragment_downloads": 4,

        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,

        "socket_timeout": 30,

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "ignoreerrors": False,

        "overwrites": True,

        "continuedl": True,

        "outtmpl": os.path.join(
            download_dir,
            "%(id)s.%(ext)s"
        ),

        "http_headers": {

            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
        },

        "postprocessor_args": [],

        "windowsfilenames": False
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

        # Prefer the final merged file path.
        file_path = info.get("filepath")

        if file_path and os.path.isfile(file_path):
            return file_path

        # Find the downloaded file by media ID.
        media_id = info.get("id")

        if media_id:

            matches = []

            for name in os.listdir(download_dir):

                full_path = os.path.join(
                    download_dir,
                    name
                )

                if (
                    os.path.isfile(full_path)
                    and name.startswith(str(media_id) + ".")
                ):

                    matches.append(full_path)

            if matches:

                mp4_files = [
                    path for path in matches
                    if path.lower().endswith(".mp4")
                ]

                return (
                    mp4_files[0]
                    if mp4_files
                    else matches[0]
                )

        raise Exception("Downloaded file was not found.")


# ==========================================================
# ERROR HANDLER
# ==========================================================

def get_download_error(error):

    error = str(error)
    lower_error = error.lower()

    if "private" in lower_error:

        return "This video is private or unavailable."

    if any(word in lower_error for word in (
        "sign in",
        "login required",
        "cookies",
        "authentication"
    )):

        return (
            "This content requires authorized access. "
            "Please check that the video is publicly accessible."
        )

    if any(word in lower_error for word in (
        "rate-limit",
        "rate limit",
        "too many requests",
        "http error 429"
    )):

        return (
            "The platform has temporarily limited requests. "
            "Please try again later."
        )

    if "unsupported url" in lower_error:

        return "This link is not supported."

    if any(word in lower_error for word in (
        "ffmpeg",
        "ffprobe",
        "merger"
    )):

        return (
            "FFmpeg is missing or not configured correctly. "
            "Please check your Heroku build."
        )

    if any(word in lower_error for word in (
        "nsig",
        "javascript",
        "challenge",
        "signature"
    )):

        return (
            "YouTube extraction needs an updated yt-dlp "
            "and a supported JavaScript runtime. "
            "Please update the deployment dependencies."
        )

    if "disk" in lower_error or "no space" in lower_error:

        return "Server storage is full. Please try again later."

    return error[:1000]


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

    if not is_supported_url(url):

        await message.reply_text(
            "❌ Please send a valid YouTube, Instagram or Facebook link."
        )

        return

    if not await is_subscribed(client, user_id):

        await send_join_message(message)
        return

    status_msg = await message.reply_text(
        """
<blockquote>
📥 <b>ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴠɪᴅᴇᴏ...</b>

✦ ʟɪɴᴋ ᴄʜᴇᴄᴋɪɴɢ
✦ ʜᴅ ᴍᴇᴅɪᴀ ᴘʀᴏᴄᴇssɪɴɢ

⚡ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ!
</blockquote>
        """
    )

    try:

        await message.react("👀")

    except Exception:
        pass

    file_path = None

    try:

        async with DOWNLOAD_SEMAPHORE:

            # Each download gets its own temporary directory.
            with tempfile.TemporaryDirectory(
                prefix="nobi_"
            ) as download_dir:

                loop = asyncio.get_running_loop()

                file_path = await loop.run_in_executor(
                    None,
                    download_media,
                    url,
                    download_dir
                )

                if not file_path or not os.path.isfile(file_path):

                    raise Exception("Download file not found.")

                file_size = os.path.getsize(file_path)

                if file_size > MAX_VIDEO_SIZE:

                    raise Exception(
                        "Video is too large to upload through this bot."
                    )

                if not file_path.lower().endswith(
                    (".mp4", ".mkv", ".webm", ".mov")
                ):

                    raise Exception(
                        "Downloaded format is not supported for video upload."
                    )

                await status_msg.edit_text(
                    "📤 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ʜᴅ ᴠɪᴅᴇᴏ...</b>"
                )

                await message.reply_video(
                    video=file_path,
                    caption=(
                        "✅ <b>ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                        "🎬 <b>Quality:</b> Best available up to 1080p\n"
                        "✦ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ɴᴏʙɪ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ"
                    ),
                    supports_streaming=True
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

            logger.exception(
                "Could not edit download status"
            )


# ==========================================================
# BOT START
# ==========================================================

if __name__ == "__main__":

    print("Nobi Downloader Bot is starting...")

    app.run()
