import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# --- RENDER KEEP-ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): 
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web).start()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
UPI_ID = os.getenv('UPI_ID')
CONTACT_USERNAME = os.getenv('CONTACT_USERNAME')

bot = telebot.TeleBot(BOT_TOKEN)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['sub_management']
channels_col = db['channels']
users_col = db['users']

# --- YOUR CUSTOM DASHBOARD / CAPTION ---
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

# --- START & DASHBOARD ---

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    text = message.text.split()

    # User Deep Link Entry
    if len(text) > 1:
        try:
            ch_id = int(text[1])
            ch_data = channels_col.find_one({"channel_id": ch_id})
            if ch_data:
                markup = InlineKeyboardMarkup()
                
                # Show Custom Named Buttons
                for idx, plan in enumerate(ch_data['plans']):
                    btn_text = f"🛒 {plan['name']} — ₹{plan['price']}"
                    markup.add(InlineKeyboardButton(btn_text, callback_data=f"select_{ch_id}_{idx}"))
                
                # Proof / Contact Button
                markup.add(InlineKeyboardButton("📸 PROOF / CONTACT", url=f"https://t.me/{CONTACT_USERNAME}"))
                
                # Send Exact Template Message
                bot.send_message(
                    message.chat.id, 
                    DEFAULT_CAPTION, 
                    reply_markup=markup, 
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            pass

    # Admin Control Panel
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("➕ Add New Channel", callback_data="add_new_ch"))
        markup.add(InlineKeyboardButton("📋 Manage All Channels", callback_data="list_all_ch"))
        
        bot.send_message(
            message.chat.id, 
            "⚙️ *Admin Dashboard*\n\nAap yahan se multiple channels manage kar sakte hain:", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "Welcome! To join our premium channel, use the link from channel.")

# --- MULTIPLE CHANNELS MANAGEMENT ---

@bot.callback_query_handler(func=lambda call: call.data == "list_all_ch")
def list_channels_cb(call):
    markup = InlineKeyboardMarkup()
    cursor = channels_col.find({"admin_id": ADMIN_ID})
    count = 0
    for ch in cursor:
        markup.add(InlineKeyboardButton(f"📢 {ch['name']}", callback_data=f"manage_{ch['channel_id']}"))
        count += 1
    
    markup.add(InlineKeyboardButton("➕ Add Another Channel", callback_data="add_new_ch"))
    
    if count == 0:
        bot.edit_message_text("Koi bhi channel added nahi hai. Niche click karke add karein:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        bot.edit_message_text("Aapke saare active channels:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.message_handler(commands=['add'])
def add_cmd(message):
    if message.from_user.id == ADMIN_ID:
        start_add_process(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "add_new_ch")
def add_cb(call):
    bot.answer_callback_query(call.id)
    start_add_process(call.message.chat.id)

def start_add_process(chat_id):
    msg = bot.send_message(chat_id, "Pehle bot ko apne Channel me Admin banayein, phir us channel se koi bhi message yahan **FORWARD** karein.")
    bot.register_next_step_handler(msg, get_channel_forward)

def get_channel_forward(message):
    if message.forward_from_chat:
        ch_id = message.forward_from_chat.id
        ch_name = message.forward_from_chat.title
        
        instruction = (
            f"✅ Channel Detected: *{ch_name}*\n\n"
            "Ab apne plans is format me likhe (comma se separate karke):\n"
            "`Button Text : Price : Days`\n\n"
            "*Example:*\n"
            "`BUY PACK 1 : 69 : 365, BUY SNAPCHAT : 79 : 365, BUY ALL GROUPS : 149 : 365`"
        )
        msg = bot.send_message(ADMIN_ID, instruction, parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_channel_plans, ch_id, ch_name)
    else:
        bot.send_message(ADMIN_ID, "❌ Message forward nahi tha. Dubara `/add` try karein.")

def save_channel_plans(message, ch_id, ch_name):
    try:
        raw_text = message.text.strip()
        plans_list = []
        
        for item in raw_text.split(','):
            parts = item.split(':')
            if len(parts) == 3:
                p_name = parts[0].strip()
                p_price = parts[1].strip()
                p_days = parts[2].strip()
                if p_price.isdigit() and p_days.isdigit():
                    plans_list.append({
                        "name": p_name,
                        "price": p_price,
                        "days": int(p_days)
                    })

        if not plans_list:
            bot.send_message(ADMIN_ID, "❌ Invalid format. Correct format: `Name : Price : Days`. Dubara `/add` karein.")
            return
        
        channels_col.update_one(
            {"channel_id": int(ch_id)}, 
            {"$set": {"name": str(ch_name), "plans": plans_list, "admin_id": int(ADMIN_ID)}}, 
            upsert=True
        )
        
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start={ch_id}"
        bot.send_message(ADMIN_ID, f"🎉 *Channel Setup Complete!*\n\n📢 *Channel:* {ch_name}\n🔗 *Invite Link:* `{link}`", parse_mode="Markdown")
    
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Error: {str(e)}")

# --- AUTO BROADCAST WITH DASHBOARD CAPTION ---

@bot.message_handler(content_types=['photo', 'video'], func=lambda m: m.from_user.id == ADMIN_ID)
def broadcast_to_channel(message):
    cursor = list(channels_col.find({"admin_id": ADMIN_ID}))
    
    if not cursor:
        bot.send_message(ADMIN_ID, "❌ Koi channel set nahi hai. Pehle `/add` se channel add karein.")
        return

    # If only 1 channel, send directly. If multiple, send to latest or all.
    ch_data = cursor[-1] 
    ch_id = ch_data['channel_id']
    bot_username = bot.get_me().username

    markup = InlineKeyboardMarkup()
    btn_sub = InlineKeyboardButton("🛒 Buy Subscription / Join", url=f"https://t.me/{bot_username}?start={ch_id}")
    markup.add(btn_sub)

    caption = message.caption if message.caption else DEFAULT_CAPTION

    try:
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            bot.send_photo(ch_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")
        elif message.content_type == 'video':
            file_id = message.video.file_id
            bot.send_video(ch_id, file_id, caption=caption, reply_markup=markup, parse_mode="Markdown")

        bot.send_message(ADMIN_ID, f"✅ Photo/Video successfully *{ch_data['name']}* channel me bhej diya gaya hai!", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Broadcast Error: {str(e)}")

# --- PAYMENT FLOW ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def user_pays(call):
    _, ch_id, plan_idx = call.data.split('_')
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    plan = ch_data['plans'][int(plan_idx)]
    
    price = plan['price']
    p_name = plan['name']
    
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}%26am={price}%26cu=INR"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ I Have Paid", callback_data=f"paid_{ch_id}_{plan_idx}"))
    markup.add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    
    bot.send_photo(call.message.chat.id, qr_url, 
                   caption=f"📦 *Selected:* {p_name}\n💵 *Price:* ₹{price}\n💳 *UPI ID:* `{UPI_ID}`\n\nPayment karke 'I Have Paid' button dabaayein.", 
                   reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def admin_notify(call):
    _, ch_id, plan_idx = call.data.split('_')
    user = call.from_user
    ch_data = channels_col.find_one({"channel_id": int(ch_id)})
    plan = ch_data['plans'][int(plan_idx)]
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{ch_id}_{plan['days']}"))
    markup.add(InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}"))
    
    bot.send_message(ADMIN_ID, f"🔔 *Payment Verification Request!*\n\nUser: {user.first_name}\nChannel: {ch_data['name']}\nPlan: {plan['name']}\nPrice: ₹{plan['price']}", 
                     reply_markup=markup, parse_mode="Markdown")
    
    u_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 Contact Admin", url=f"https://t.me/{CONTACT_USERNAME}"))
    bot.send_message(call.message.chat.id, "✅ Aapka payment request Admin ko bhej diya gaya hai. Thoda wait karein.", reply_markup=u_markup)

# --- APPROVAL & AUTO-KICK ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve_user(call):
    _, u_id, ch_id, days = call.data.split('_')
    u_id, ch_id, days = int(u_id), int(ch_id), int(days)
    
    try:
        expiry_datetime = datetime.now() + timedelta(days=days)
        expiry_ts = int(expiry_datetime.timestamp())

        link = bot.create_chat_invite_link(ch_id, member_limit=1, expire_date=expiry_ts)
        
        users_col.update_one({"user_id": u_id, "channel_id": ch_id}, {"$set": {"expiry": expiry_datetime.timestamp()}}, upsert=True)
        
        bot.send_message(u_id, f"🥳 *Payment Approved!*\n\nChannel Join Link: {link.invite_link}\n\n⚠️ Note: Yeh link 1 baar hi kaam karega.", parse_mode="Markdown")
        bot.edit_message_text(f"✅ Approved User ID: {u_id}", call.message.chat.id, call.message.message_id)
        
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Approval Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('rej_'))
def reject_user(call):
    u_id = int(call.data.split('_')[1])
    bot.send_message(u_id, "❌ Aapka payment verify nahi ho paya. Kripya Admin se sampark karein.")
    bot.edit_message_text(f"❌ Rejected User ID: {u_id}", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_'))
def manage_single_ch(call):
    ch_id = int(call.data.split('_')[1])
    ch_data = channels_col.find_one({"channel_id": ch_id})
    bot_username = bot.get_me().username
    link = f"https://t.me/{bot_username}?start={ch_id}"
    
    bot.edit_message_text(f"📢 *Channel:* {ch_data['name']}\n\n🔗 *Invite Link:* `{link}`\n\nNaye plans/prices add karne ke liye dubara `/add` use karein.", 
                          call.message.chat.id, call.message.message_id, parse_mode="Markdown")

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
            
            bot.send_message(user['user_id'], "⚠️ Aapki channel subscription khatam ho gayi hai.\n\nRenew karne ke liye niche button par click karein:", reply_markup=markup)
            users_col.delete_one({"_id": user['_id']})
        except:
            pass

# --- MAIN RUNNER ---
if __name__ == '__main__':
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired_users, 'interval', minutes=1)
    scheduler.start()
    bot.remove_webhook()
    print("Bot started...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
