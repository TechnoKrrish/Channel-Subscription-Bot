import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import certifi  # SSL Handshake Error फ़िक्स करने के लिए
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): 
    return "Bot is running and healthy!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web).start()

# --- CONFIGURATION (Environment Variables) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
UPI_ID = os.getenv('UPI_ID')
CONTACT_USERNAME = os.getenv('CONTACT_USERNAME')

bot = telebot.TeleBot(BOT_TOKEN)

# SSL Certificate verification fix added via certifi
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['sub_management']
channels_col = db['channels']
users_col = db['users']

# Custom Default Caption / Message
DEFAULT_CAPTION = (
    "🔥 *Premium Video Pack*\n\n"
    "✅ One Time Payment\n"
    "✅ Lifetime Access\n"
    "✅ Instant Delivery\n\n"
    "💎 *What You Get:*\n"
    "• Full HD Quality Videos\n"
    "• Regular New Updates\n"
    "• 24×7 Support\n\n"
    "👇 *Choose an option*"
)

# --- ADMIN LOGIC ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    text = message.text.split()

    # User entry via Deep Link
    if len(text) > 1:
        try:
            ch_id = int(text[1])
            ch_data = channels_col.find_one({"channel_id": ch_id})
            if ch_data:
                markup = InlineKeyboardMarkup()
                # Display Custom Name Plans
                for idx, plan in enumerate(ch_data['plans']):
                    btn_text = f"🛒 {plan['name']} — ₹{plan['price']}"
                    markup.add(InlineKeyboardButton(btn_text, callback_data=f"select_{ch_id}_{idx}"))
                
                markup.add(InlineKeyboardButton("📸 PROOF / CONTACT", url=f"https://t.me/{CONTACT_USERNAME}"))
                
                bot.send_message(
                    message.chat.id, 
                    DEFAULT_CAPTION, 
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                return
        except Exception as e: 
            pass

    # Admin Panel Greeting
    if user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "✅ Admin Panel Active!\n\n/add - Add/Edit Channel & Custom Plans\n/channels - Manage Existing Channels\n\n📌 *To Broadcast:* Send any Photo or Video directly to this bot.")
    else:
        bot.send_message(message.chat.id, "Welcome! To join a channel, please use the link provided by the Admin.")

@bot.message_handler(commands=['channels'], func=lambda m: m.from_user.id == ADMIN_ID)
def list_channels(message):
    markup = InlineKeyboardMarkup()
    cursor = channels_col.find({"admin_id": ADMIN_ID})
    count = 0
    for ch in cursor:
        markup.add(InlineKeyboardButton(f"Channel: {ch['name']}", callback_data=f"manage_{ch['channel_id']}"))
        count += 1
    
    markup.add(InlineKeyboardButton("➕ Add New Channel", callback_data="add_new"))
    
    if count == 0:
        bot.send_message(ADMIN_ID, "No channels found. Click below to add one.", reply_markup=markup)
    else:
        bot.send_message(ADMIN_ID, "Your Managed Channels:", reply_markup=markup)

@bot.message_handler(commands=['add'], func=lambda m: m.from_user.id == ADMIN_ID)
def add_channel_start(message):
    msg = bot.send_message(ADMIN_ID, "Please ensure the bot is an Admin in your channel, then FORWARD any message from that channel here.")
    bot.register_next_step_handler(msg, get_plans)

@bot.callback_query_handler(func=lambda call: call.data == "add_new")
def cb_add_new(call):
    bot.answer_callback_query(call.id)
    msg = bot.send_message(ADMIN_ID, "Please FORWARD any message from your channel here.")
    bot.register_next_step_handler(msg, get_plans)

def get_plans(message):
    if message.forward_from_chat:
        ch_id = message.forward_from_chat.id
        ch_name = message.forward_from_chat.title
        
        instruction = (
            f"Channel Detected: *{ch_name}*\n\n"
            "Enter plans in format:\n"
            "`Button Text : Price : Minutes` (separated by comma)\n\n"
            "*Example:*\n"
            "`BUY PACK 1 : 69 : 525600, BUY SNAPCHAT : 79 : 525600, BUY ALL GROUPS : 149 : 525600`\n\n"
            "*(Note: 525600 minutes = 1 Year/Lifetime)*"
        )
        msg = bot.send_message(ADMIN_ID, instruction, parse_mode="Markdown")
        bot.register_next_step_handler(msg, finalize_channel, ch_id, ch_name)
    else:
        bot.send_message(ADMIN_ID, "❌ Error: Message was not forwarded. Use /add to try again.")

def finalize_channel(message, ch_id, ch_name):
    try:
        raw_text = message.text.strip()
        plans_list = []
        
        for item in raw_text.split(','):
            parts = item.split(':')
            if len(parts) == 3:
                p_name = parts[0].strip()
                p_price = parts[1].strip()
                p_mins = parts[2].strip()
                if p_price.isdigit() and p_mins.isdigit():
                    plans_list.append({
                        "name": p_name,
                        "price": p_price,
                        "mins": int(p_mins)
                    })

        if not plans_list:
            bot.send_message(ADMIN_ID, "❌ Invalid format. Use `Name : Price : Minutes`. Use /add to retry.")
            return
        
        channels_col.update_one(
            {"channel_id": int(ch_id)}, 
            {"$set": {"name": str(ch_name), "plans": plans_list, "admin_id": int(ADMIN_ID)}}, 
            upsert=True
        )
        
        bot_username = bot.get_me().username
        bot.send_message(ADMIN_ID, f"✅ Setup Successful!\n\nInvite Link for users:\n`https://t.me/{bot_username}?start={ch_id}`", parse_mode="Markdown")
    
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}\n\nPlease use /add to retry.")

# --- BROADCAST MEDIA TO CHANNEL ---

@bot.message_handler(content_types=['photo', 'video'], func=lambda m: m.from_user.id == ADMIN_ID)
def broadcast_media(message):
    ch_data = channels_col.find_one({"admin_id": ADMIN_ID})
    
    if not ch_data:
        bot.send_message(ADMIN_ID, "❌ No channel found! Please add a channel first using /add command.")
        return

    ch_id = ch_data['channel_id']
    bot_username = bot.get_me().username

    markup = InlineKeyboardMarkup()
    btn_sub = InlineKeyboardButton("🛒 Buy Subscription / Join Channel", url=f"https://t.me/{bot_username}?start={ch_id}")
    markup.add(btn_sub)

    caption = message.caption if message.caption else DEFAULT_CAPTION

    try:
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            bot.send_photo(ch_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'video':
            file_id = message.video.file_id
            bot.send_video(ch_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")

        bot.send_message(ADMIN_ID, f"✅ Content successfully broadcasted to channel: *{ch_data['name']}*", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Broadcast Error: {str(e)}")

# --- USER: PAYMENT FLOW ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def user_pays(call):
    _, ch_id, plan_idx = call.data.split('_')
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    plan = ch_data['plans'][int(plan_idx)]
    
    price = plan['price']
    p_name = plan['name']
    mins = plan['mins']
    
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}%26am={price}%26cu=INR"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{ch_id}_{plan_idx}"))
    markup.add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    
    bot.send_photo(call.message.chat.id, qr_url, 
                   caption=f"📦 *Selected:* {p_name}\n💵 *Price:* ₹{price}\n💳 *UPI ID:* `{UPI_ID}`\n\nPlease complete the payment and click 'I Have Paid'.", 
                   reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def admin_notify(call):
    _, ch_id, plan_idx = call.data.split('_')
    user = call.from_user
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    plan = ch_data['plans'][int(plan_idx)]
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{ch_id}_{plan['mins']}"))
    markup.add(InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}"))
    
    bot.send_message(ADMIN_ID, f"🔔 *Payment Verification Required!*\n\nUser: {user.first_name}\nChannel: {ch_data['name']}\nPlan: {plan['name']}\nPrice: ₹{plan['price']}", 
                     reply_markup=markup, parse_mode="Markdown")
    
    u_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    bot.send_message(call.message.chat.id, "✅ Your payment request has been sent. Please wait for Admin approval.", reply_markup=u_markup)

# --- APPROVAL & EXPIRY ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve_now(call):
    _, u_id, ch_id, mins = call.data.split('_')
    u_id, ch_id, mins = int(u_id), int(ch_id), int(mins)
    
    try:
        expiry_datetime = datetime.now() + timedelta(minutes=mins)
        expiry_ts = int(expiry_datetime.timestamp())

        link = bot.create_chat_invite_link(ch_id, member_limit=1, expire_date=expiry_ts)
        
        users_col.update_one({"user_id": u_id, "channel_id": ch_id}, {"$set": {"expiry": expiry_datetime.timestamp()}}, upsert=True)
        
        bot.send_message(u_id, f"🥳 *Payment Approved!*\n\nJoin Link: {link.invite_link}\n\n⚠ Note: This link is one-time use.", parse_mode="Markdown")
        bot.edit_message_text(f"✅ Approved user {u_id}.", call.message.chat.id, call.message.message_id)
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_'))
def manage_ch(call):
    ch_id = int(call.data.split('_')[1])
    ch_data = channels_col.find_one({"channel_id": ch_id})
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={ch_id}"
    
    bot.edit_message_text(f"Settings for: *{ch_data['name']}*\n\nYour Link: `{link}`\n\nTo edit plans/prices, use /add and forward a message from this channel again.", 
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# Automate Kicking
def kick_expired_users():
    now = datetime.now().timestamp()
    expired_users = users_col.find({"expiry": {"$lte": now}})
    bot_username = bot.get_me().username

    for user in expired_users:
        try:
            bot.ban_chat_member(user['channel_id'], user['user_id'])
            bot.unban_chat_member(user['channel_id'], user['user_id'])
            
            rejoin_url = f"https://t.me/{bot_username}?start={user['channel_id']}"
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔄 Re-join / Renew", url=rejoin_url))
            
            bot.send_message(user['user_id'], "⚠️ Your subscription has expired.\n\nTo join again or renew, please click the button below:", reply_markup=markup)
            users_col.delete_one({"_id": user['_id']})
        except: 
            pass

# --- STARTUP ---
if __name__ == '__main__':
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired_users, 'interval', minutes=1)
    scheduler.start()
    bot.remove_webhook()
    print("Bot is running...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
