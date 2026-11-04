
import os
import asyncio
import re
import html
import logging

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
# DATABASE INITIALIZATION
# ==========================================================

db_client = AsyncIOMotorClient(config.MONGO_DB_URI)

db = db_client["all_downloader_bot"]
users_col = db["users"]


# ==========================================================
# BOT INITIALIZATION
# ==========================================================

app = Client(
    "AllDownloaderBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    parse_mode=enums.ParseMode.HTML
)


# ==========================================================
# STYLISH WELCOME MESSAGE
# ==========================================================

DEFAULT_WELCOME_TEXT = """
<blockquote>
<b>✦ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ɴᴏʙɪ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ ✦</b>

ʏᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ ᴍᴇᴅɪᴀ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ᴀssɪsᴛᴀɴᴛ!

━━━━━━━━━━━━━━━━━━

✧ sᴇɴᴅ ᴀ ᴠɪᴅᴇᴏ ʟɪɴᴋ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ.

✧ sᴜᴘᴘᴏʀᴛᴇᴅ ᴘʟᴀᴛғᴏʀᴍs:
• ɪɴsᴛᴀɢʀᴀᴍ
• ғᴀᴄᴇʙᴏᴏᴋ
• ʏᴏᴜᴛᴜʙᴇ

━━━━━━━━━━━━━━━━━━

⚡ ғᴀsᴛ ᴘʀᴏᴄᴇssɪɴɢ
🎬 ʜɪɢʜ Qᴜᴀʟɪᴛʏ ᴠɪᴅᴇᴏs
🔒 sɪᴍᴘʟᴇ & ᴇᴀsʏ ᴛᴏ ᴜsᴇ

<b>➥ ɴᴏᴡ sᴇɴᴅ ʏᴏᴜʀ ʟɪɴᴋ!</b>
</blockquote>
"""

WELCOME_TEXT = getattr(config, "WELCOME_TEXT", None) or DEFAULT_WELCOME_TEXT


# ==========================================================
# FORCE SUBSCRIPTION SETTINGS
# ==========================================================

def get_join_url():
    username = str(config.CHANNEL_USERNAME).strip().replace("@", "")

    if username:
        return f"https://t.me/{username}"

    return None


def get_join_keyboard():
    join_url = get_join_url()

    buttons = []

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


async def is_subscribed(client: Client, user_id: int) -> bool:

    channel_id = getattr(config, "CHANNEL_ID", None)

    if not channel_id:
        return True

    try:
        member = await client.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )

        status = member.status

        # Handle Pyrogram enum and string statuses
        status_name = getattr(status, "name", None)
        status_value = getattr(status, "value", None)

        if status_name:
            status_name = str(status_name).lower()

        elif status_value:
            status_name = str(status_value).lower()

        else:
            status_name = str(status).lower().split(".")[-1]

        allowed_statuses = {
            "member",
            "administrator",
            "owner",
            "creator"
        }

        if status_name in allowed_statuses:
            logger.info(
                "User %s subscription verified: %s",
                user_id,
                status_name
            )
            return True

        logger.info(
            "User %s is not subscribed. Status: %s",
            user_id,
            status_name
        )

        return False

    except Exception as e:
        logger.error(
            "Subscription check failed for user %s: %s",
            user_id,
            e
        )

        return False


async def send_join_message(message: Message):

    await message.reply_text(
        """
<blockquote>
<b>🔐 ᴄʜᴀɴɴᴇʟ ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ</b>

ᴜsᴇ ᴏғ ᴛʜɪs ʙᴏᴛ ʀᴇǫᴜɪʀᴇs ᴏᴜʀ ᴏғғɪᴄɪᴀʟ ᴄʜᴀɴɴᴇʟ ᴍᴇᴍʙᴇʀsʜɪᴘ.

➜ ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ.
➜ ᴄʟɪᴄᴋ ᴠᴇʀɪғʏ & ᴄᴏɴᴛɪɴᴜᴇ.

✦ ɪғ ʏᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴀ ᴍᴇᴍʙᴇʀ, ᴊᴜsᴛ ᴄʟɪᴄᴋ ᴠᴇʀɪғʏ!
</blockquote>
        """,
        reply_markup=get_join_keyboard()
    )


# ==========================================================
# START COMMAND
# ==========================================================

@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):

    user = message.from_user

    user_id = user.id
    user_name = html.escape(user.first_name or "Unknown")
    username = user.username

    username_str = f"@{html.escape(username)}" if username else "None"

    # Register user in MongoDB

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
                    "username": username
                }
            },
            upsert=True
        )

        # New user log

        if config.LOG_CHANNEL:

            log_msg = (
                "<b>👤 ɴᴇᴡ ᴜsᴇʀ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ!</b>\n\n"
                f"• <b>ɴᴀᴍᴇ:</b> {user_name}\n"
                f"• <b>ᴜsᴇʀɴᴀᴍᴇ:</b> {username_str}\n"
                f"• <b>ᴜsᴇʀ ɪᴅ:</b> <code>{user_id}</code>"
            )

            try:
                await client.send_message(
                    config.LOG_CHANNEL,
                    log_msg
                )

            except Exception as e:
                logger.error("New user log failed: %s", e)

    else:

        await users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "first_name": user.first_name,
                    "username": username
                }
            },
            upsert=True
        )

    # Check subscription

    if not await is_subscribed(client, user_id):

        await send_join_message(message)
        return

    # Send welcome menu

    await message.reply_text(WELCOME_TEXT)


# ==========================================================
# FORCE SUBSCRIPTION CALLBACK
# ==========================================================

@app.on_callback_query(filters.regex(r"^check_sub$"))
async def check_subscription_callback(
    client: Client,
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    # Recheck channel membership every time button is clicked

    subscribed = await is_subscribed(
        client,
        user_id
    )

    if subscribed:

        await callback.answer(
            "✅ Verification Successful!",
            show_alert=False
        )

        try:
            await callback.message.delete()
        except Exception:
            pass

        success_text = """
<blockquote>
<b>🎉 ᴠᴇʀɪғɪᴄᴀᴛɪᴏɴ sᴜᴄᴄᴇssғᴜʟ!</b>

✦ ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ᴠᴇʀɪғɪᴇᴅ.

✦ ɴᴏᴡ ʏᴏᴜ ᴄᴀɴ ᴜsᴇ ᴛʜᴇ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ.

➥ sᴇɴᴅ ʏᴏᴜʀ ᴠɪᴅᴇᴏ ʟɪɴᴋ ɴᴏᴡ!
</blockquote>
"""

        await callback.message.reply_text(
            success_text
        )

    else:

        await callback.answer(
            "❌ You haven't joined the channel yet! Join first and try again.",
            show_alert=True
        )


# ==========================================================
# STATISTICS COMMAND - OWNER ONLY
# ==========================================================

@app.on_message(
    filters.command("statistics")
    & filters.private
    & filters.user(config.OWNER_ID)
)
async def statistics_command(
    client: Client,
    message: Message
):

    total_users = await users_col.count_documents({})

    await message.reply_text(
        f"""
<blockquote>
<b>📊 ʙᴏᴛ sᴛᴀᴛɪsᴛɪᴄs</b>

👥 ᴛᴏᴛᴀʟ ᴜsᴇʀs:
<code>{total_users}</code>

✦ ᴅᴀᴛᴀʙᴀsᴇ: ᴄᴏɴɴᴇᴄᴛᴇᴅ
✦ sᴛᴀᴛᴜs: ᴀᴄᴛɪᴠᴇ
</blockquote>
        """
    )


# ==========================================================
# BROADCAST COMMAND - OWNER ONLY
# ==========================================================

@app.on_message(
    filters.command("broadcast")
    & filters.private
    & filters.user(config.OWNER_ID)
)
async def broadcast_command(
    client: Client,
    message: Message
):

    if not message.reply_to_message:

        await message.reply_text(
            "⚠️ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ."
        )
        return

    broadcast_msg = message.reply_to_message

    users_cursor = users_col.find({})

    total_users = await users_col.count_documents({})

    status_msg = await message.reply_text(
        f"🚀 ʙʀᴏᴀᴅᴄᴀsᴛ sᴛᴀʀᴛᴇᴅ!\n\nᴛᴏᴛᴀʟ ᴜsᴇʀs: <code>{total_users}</code>"
    )

    success = 0
    failed = 0

    async for user in users_cursor:

        uid = user["user_id"]

        try:

            await broadcast_msg.copy(chat_id=uid)

            success += 1

            await asyncio.sleep(0.1)

        except Exception as e:

            failed += 1

            logger.warning(
                "Broadcast failed for %s: %s",
                uid,
                e
            )

    await status_msg.edit_text(
        f"""
<blockquote>
<b>✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!</b>

👥 ᴛᴏᴛᴀʟ: <code>{total_users}</code>

✅ sᴜᴄᴄᴇss: <code>{success}</code>

❌ ғᴀɪʟᴇᴅ: <code>{failed}</code>
</blockquote>
        """
    )


# ==========================================================
# LINK HANDLER - MEDIA DOWNLOADER
# ==========================================================

@app.on_message(
    filters.text
    & filters.private
    & ~filters.command(["start", "broadcast", "statistics"])
)
async def downloader_handler(
    client: Client,
    message: Message
):

    user_id = message.from_user.id

    url = message.text.strip()

    # URL validation

    url_pattern = re.compile(
        r"^https?://[^\s]+$",
        re.IGNORECASE
    )

    if not url_pattern.match(url):
        return

    # Check force subscription dynamically

    if not await is_subscribed(client, user_id):

        await send_join_message(message)
        return

    # Processing message

    status_msg = await message.reply_text(
        "📥 <b>ᴘʀᴏᴄᴇssɪɴɢ ʏᴏᴜʀ ᴠɪᴅᴇᴏ...</b>\n\n"
        "✦ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ."
    )

    # Eyes reaction

    try:
        await message.react("👀")
    except Exception:
        pass

    download_dir = "downloads"

    os.makedirs(
        download_dir,
        exist_ok=True
    )

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": f"{download_dir}/%(id)s.%(ext)s",
        "socket_timeout": 30,
        "noplaylist": True,
    }

    try:

        loop = asyncio.get_running_loop()

        def download():

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )

                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(
            None,
            download
        )

        if file_path and os.path.exists(file_path):

            await status_msg.edit_text(
                "📤 <b>ᴜᴘʟᴏᴀᴅɪɴɢ ᴠɪᴅᴇᴏ...</b>\n\n"
                "✦ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ."
            )

            await message.reply_video(
                video=file_path,
                caption=(
                    "✅ <b>ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                    "✦ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ɴᴏʙɪ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ"
                )
            )

            await status_msg.delete()

            try:
                os.remove(file_path)
            except Exception:
                pass

        else:

            await status_msg.edit_text(
                "❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ғᴀɪʟᴇᴅ!</b>\n\n"
                "ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ᴛʜᴇ ʟɪɴᴋ ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ."
            )

    except Exception as e:

        logger.exception("Downloader error")

        error_text = html.escape(str(e))

        await status_msg.edit_text(
            "❌ <b>ᴅᴏᴡɴʟᴏᴀᴅ ᴇʀʀᴏʀ!</b>\n\n"
            f"<code>{error_text[:2500]}</code>"
        )


# ==========================================================
# BOT START
# ==========================================================

if __name__ == "__main__":

    print("Nobi Downloader Bot is starting...")

    app.run()
