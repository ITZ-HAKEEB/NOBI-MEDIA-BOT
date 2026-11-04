import os

# Telegram API Credentials
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Database & Owner
MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Logger Group/Channel ID (Where new user logs will be sent)
LOG_CHANNEL = os.environ.get("LOG_CHANNEL", "")
if LOG_CHANNEL:
    try:
        LOG_CHANNEL = int(LOG_CHANNEL)
    except ValueError:
        pass

# Force Subscription Settings
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # e.g., -100xxxxxxxxxx or @channelname
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "")  # e.g., my_channel (without @)

# Customizable Welcome Message
WELCOME_TEXT = os.environ.get(
    "WELCOME_TEXT",
    "👋 **Welcome to the Ultimate Media Downloader Bot!**\n\n"
    "✨ **Supported Platforms:**\n"
    "• Instagram (Reels, Videos, Posts, Stories)\n"
    "• Facebook (Videos, Reels, Posts, Stories)\n"
    "• YouTube (Shorts & Long Videos)\n\n"
    "🚀 **How to use:**\n"
    "Just send any valid media link here, and I will download and send it to you in HD quality instantly!"
)
