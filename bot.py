import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Configuration Variables
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Apna naya Bot Token yahan dalein
ADMIN_USERNAME = "your_admin_username"  # Apna Telegram username bina '@' ke dalein

# Image aur Video URLs (Direct image/video links ya file_id)
WELCOME_BANNER_URL = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800"
QR_CODE_30_DAYS = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa=yourupi@bank%26pn=Admin%26am=199"
QR_CODE_90_DAYS = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa=yourupi@bank%26pn=Admin%26am=499"
DEMO_VIDEO_URL = "https://www.w3schools.com/html/mov_bbb.mp4"  # Sample Video Link


# /start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 30 Days Plan - ₹199", callback_data="plan_30")],
        [InlineKeyboardButton("⚡ 90 Days Plan - ₹499", callback_data="plan_90")],
        [InlineKeyboardButton("🎬 Watch Demo Video", callback_data="send_demo")],
        [
            InlineKeyboardButton(
                "📞 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption_text = (
        "🔥 **Welcome!**\n\n"
        "You are joining: **Virals-Unseen VIP**\n\n"
        "Please select a subscription plan below to get access:"
    )

    # Sending photo with banner image and options
    await update.message.reply_photo(
        photo=WELCOME_BANNER_URL,
        caption=caption_text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


# Callback Query Handler for Buttons
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "plan_30":
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ I Have Paid", callback_data="paid_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}"
                )
            ],
        ]
        caption = (
            "📌 **Plan Selected: 30 Days - ₹199**\n\n"
            "Scan the QR code below to complete payment via UPI.\n"
            "After payment, click **'I Have Paid'** and send screenshot to Admin."
        )
        await query.message.reply_photo(
            photo=QR_CODE_30_DAYS,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "plan_90":
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ I Have Paid", callback_data="paid_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}"
                )
            ],
        ]
        caption = (
            "📌 **Plan Selected: 90 Days - ₹499**\n\n"
            "Scan the QR code below to complete payment via UPI.\n"
            "After payment, click **'I Have Paid'** and send screenshot to Admin."
        )
        await query.message.reply_photo(
            photo=QR_CODE_90_DAYS,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data == "send_demo":
        caption = "🎥 **Here is the preview demo video:**"
        await query.message.reply_video(
            video=DEMO_VIDEO_URL, caption=caption, parse_mode="Markdown"
        )

    elif query.data == "paid_confirm":
        await query.message.reply_text(
            f"Thank you! Please send your payment screenshot directly to @{ADMIN_USERNAME} for approval."
        )


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers Add Karen
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Bot Start Karein
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
