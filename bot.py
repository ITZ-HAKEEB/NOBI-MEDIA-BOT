import os
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
import yt_dlp
import config

# Database Initialization
db_client = AsyncIOMotorClient(config.MONGO_DB_URI)
db = db_client["all_downloader_bot"]
users_col = db["users"]

app = Client(
    "AllDownloaderBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

# Helper function to check Force Subscription
async def is_subscribed(client, user_id):
    if not config.CHANNEL_ID:
        return True
    try:
        user = await client.get_chat_member(config.CHANNEL_ID, user_id)
        if user.status in ["member", "administrator", "creator"]:
            return True
    except Exception:
        pass
    return False

# Start Command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    username = message.from_user.username
    username_str = f"@{username}" if username else "None"
    
    # Check if user is new, save to DB, and send log to logger group
    user_doc = await users_col.find_one({"user_id": user_id})
    if not user_doc:
        await users_col.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)
        if config.LOG_CHANNEL:
            log_msg = (
                f"👤 **New User Started The Bot!**\n\n"
                f"• **Full Name:** {user_name}\n"
                f"• **Username:** {username_str}\n"
                f"• **User ID:** <code>{user_id}</code>"
            )
            try:
                await client.send_message(config.LOG_CHANNEL, log_msg)
            except Exception as e:
                print(f"Failed to send log to logger group: {e}")
    else:
        await users_col.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

    # Check subscription
    if not await is_subscribed(client, user_id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{config.CHANNEL_USERNAME}")],
            [InlineKeyboardButton("🔄 Verify & Start", callback_data="check_sub")]
        ])
        await message.reply_text(
            "<b>Please join our channel first to use this bot!</b>\n\n"
            "After joining, click the **Verify & Start** button below.",
            reply_markup=buttons
        )
        return

    # Welcome Menu using Config Variable
    await message.reply_text(config.WELCOME_TEXT)

# Callback query for Force Sub verification
@app.on_callback_query(filters.regex("check_sub"))
async def check_subscription_callback(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_subscribed(client, user_id):
        await callback.message.delete()
        success_text = (
            "🎉 **Verification Successful!**\n\n"
            "You can now send any Instagram, Facebook, or YouTube link to download videos in HD quality!"
        )
        await callback.message.reply_text(success_text)
    else:
        await callback.answer("❌ You haven't joined the channel yet! Please join first.", show_alert=True)

# Statistics Command (For Owner Only)
@app.on_message(filters.command("statistics") & filters.private & filters.user(config.OWNER_ID))
async def statistics_command(client: Client, message: Message):
    total_users = await users_col.count_documents({})
    await message.reply_text(
        f"📊 **Bot Statistics**\n\n"
        f"• **Total Users in Database:** <code>{total_users}</code>"
    )

# Broadcast Command (For Owner Only)
@app.on_message(filters.command("broadcast") & filters.private & filters.user(config.OWNER_ID))
async def broadcast_command(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("⚠️ Please reply to a message to broadcast it to all users.")
        return
    
    broadcast_msg = message.reply_to_message
    users_cursor = users_col.find({})
    total_users = await users_col.count_documents({})
    
    status_msg = await message.reply_text(f"🚀 **Broadcast started! Total users:** {total_users}")
    
    success = 0
    failed = 0
    
    async for user in users_cursor:
        uid = user["user_id"]
        try:
            await broadcast_msg.copy(chat_id=uid)
            success += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed += 1
            
    await status_msg.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"• **Total Users:** {total_users}\n"
        f"• **Successful:** {success}\n"
        f"• **Failed:** {failed}"
    )

# Link Handler for Downloading Media
@app.on_message(filters.text & filters.private & ~filters.command(["start", "broadcast", "statistics"]))
async def downloader_handler(client: Client, message: Message):
    user_id = message.from_user.id
    url = message.text.strip()

    # URL Validation check
    url_pattern = re.compile(r'https?://(?:www\.)?.+')
    if not url_pattern.match(url):
        return

    # Check Force Subscription dynamically on every request
    if not await is_subscribed(client, user_id):
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{config.CHANNEL_USERNAME}")],
            [InlineKeyboardButton("🔄 Verify & Start", callback_data="check_sub")]
        ])
        await message.reply_text(
            "⚠️ **Channel Left Alert!**\n\n"
            "You have left our update channel. Please join back and verify to continue using the bot.",
            reply_markup=buttons
        )
        return

    # Fast processing message & Eyes reaction (👀)
    status_msg = await message.reply_text("📥 **Processing your video. Please wait a just a second.**")
    try:
        await message.react("👀")
    except Exception:
        pass

    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': f'{download_dir}/%(id)s.%(ext)s',
        'socket_timeout': 30,
        'noplaylist': True,
    }

    try:
        loop = asyncio.get_running_loop()
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        file_path = await loop.run_in_executor(None, download)

        if file_path and os.path.exists(file_path):
            await status_msg.edit_text("📤 **Uploading video in HD quality...**")
            await message.reply_video(
                video=file_path,
                caption="✅ **Downloaded successfully via your bot!**"
            )
            await status_msg.delete()
            try:
                os.remove(file_path)
            except Exception:
                pass
        else:
            await status_msg.edit_text("❌ **Failed to download the video. Please check the link and try again.**")

    except Exception as e:
        await status_msg.edit_text(f"❌ **An error occurred:**\n<code>{str(e)}</code>")

if __name__ == "__main__":
    print("Nobi Bot is starting...")
    app.run()
  
