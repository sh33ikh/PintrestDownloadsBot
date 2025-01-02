import logging
import aiohttp
from datetime import datetime
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    ParseMode,
    ChatAction
)
from telegram.ext import (
    Updater,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)
from urllib.parse import quote
from cachetools import TTLCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot_logs.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# Load environment variables
load_dotenv()

# Bot Configuration from environment
TOKEN = os.getenv('BOT_TOKEN')
REQUIRED_CHANNEL = os.getenv('REQUIRED_CHANNEL')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
CHANNEL_INVITE = os.getenv('CHANNEL_INVITE')
SUPPORT_GROUP = os.getenv('SUPPORT_GROUP')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST')

# Initialize caches and stats
user_cache = TTLCache(maxsize=100, ttl=3600)
download_stats = {}

async def fetch_content(url: str) -> dict:
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://{RAPIDAPI_HOST}/pinterest?url={quote(url)}", headers=headers) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        logger.error(f"API Error: {e}")
    return None

def get_stats_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Bot Stats", callback_data="stats"),
            InlineKeyboardButton("📢 Channel", url=CHANNEL_INVITE)
        ],
        [
            InlineKeyboardButton("💡 Help", callback_data="help"),
            InlineKeyboardButton("⭐️ Rate Us", callback_data="rate")
        ]
    ])

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    welcome_message = (
        f"Welcome to @PintrestDownloadsBot! 🚀\n\n"
        "🔥 Advanced Features:\n"
        "• High-Quality Media Downloads\n"
        "• Bulk Download Support\n"
        "• Real-time Processing\n"
        "• Statistics Tracking\n\n"
        f"📢  {user.first_name}, Join {CHANNEL_USERNAME} for updates!\n\n"
        "Send Pinterest URLs to begin! 🎯"
    )
    
    context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    update.message.reply_animation(
        animation="https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
        caption=welcome_message,
        reply_markup=get_stats_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

def is_member(user_id: int, context: CallbackContext) -> bool:
    try:
        member = context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    message = update.message.text.strip()
    
    if not is_member(user_id, context):
        update.message.reply_text(
            f"❌ Please join {CHANNEL_USERNAME} to use this bot!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Join Now 📢", url=CHANNEL_INVITE)
            ]])
        )
        return

    if not message.startswith(("https://pin.it", "https://www.pinterest.com")):
        update.message.reply_text(
            "❌ Invalid URL! Please send a valid Pinterest link.",
            reply_markup=get_stats_keyboard()
        )
        return

    status_msg = update.message.reply_text("⚡️ Processing your request...")
    
    try:
        response = context.dispatcher.run_async(fetch_content, message).result()
        
        if not response or "data" not in response:
            status_msg.edit_text("❌ Failed to fetch content! Please try again.")
            return

        # Update statistics
        if user_id not in download_stats:
            download_stats[user_id] = {"downloads": 0, "last_download": None}
        
        download_stats[user_id]["downloads"] += 1
        download_stats[user_id]["last_download"] = datetime.now()

        # Format caption with title and channel info
        title = response.get("data", {}).get("title", "No title available")
        caption = (
            f"📌 *{title}*\n\n"
            f"💫 Quality: High Definition\n"
            f"🔄 Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🤖 Downloaded via {CHANNEL_USERNAME}\n\n"
            f"📢 Join us for more updates!"
        )

        # Create response keyboard
        response_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_INVITE),
                InlineKeyboardButton("📊 Stats", callback_data="stats")
            ],
            [
                InlineKeyboardButton("⭐️ Rate Bot", callback_data="rate"),
                InlineKeyboardButton("🔄 Share", switch_inline_query=message)
            ]
        ])

        if response.get("type") == "video":
            update.message.reply_video(
                response["data"]["url"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=response_keyboard
            )
        else:
            update.message.reply_photo(
                response["data"]["url"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=response_keyboard
            )
        
        status_msg.delete()
    
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        status_msg.edit_text(
            "❌ An error occurred while processing your request!\n"
            "Please try again or contact support."
        )

def callback_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "stats":
        stats = download_stats.get(user_id, {"downloads": 0, "last_download": None})
        stats_text = (
            "📊 Your Statistics:\n"
            f"Total Downloads: {stats['downloads']}\n"
            f"Last Download: {stats['last_download'].strftime('%Y-%m-%d %H:%M') if stats['last_download'] else 'Never'}\n\n"
            f"Join {CHANNEL_USERNAME} for more updates!"
        )
        query.edit_message_text(stats_text, reply_markup=get_stats_keyboard())

    elif query.data == "help":
        help_text = (
            "📖 Advanced Usage Guide:\n\n"
            "1. Join our channel\n"
            "2. Send Pinterest URL\n"
            "3. Get high-quality content\n\n"
            "🔍 Supported URLs:\n"
            "• pin.it links\n"
            "• pinterest.com links\n\n"
            f"📢 Updates: {CHANNEL_USERNAME}"
        )
        query.edit_message_text(help_text, reply_markup=get_stats_keyboard())

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(callback_handler))

    logger.info(f"Bot started! Channel: {CHANNEL_USERNAME}")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
