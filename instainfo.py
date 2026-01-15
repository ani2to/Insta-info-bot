import os
import requests
import telebot
from flask import Flask
from threading import Thread
from telebot import types
import time
from user_agent import generate_user_agent
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('BOT_TOKEN')
MONGODB_URL = os.getenv('MONGODB_URL')
INSTAGRAM_INFO_API = os.getenv('INSTAGRAM_INFO_API')

CHANNEL_1 = '@Aniredirect'
CHANNEL_2 = '@SPBotz'
ADMIN_ID = 6302016869
LOG_CHANNEL_ID = -1003315919144

bot = telebot.TeleBot(token)

client = MongoClient(MONGODB_URL)
db = client.insta_info_bot
users_collection = db.users

user_last_request = {}

def can_make_request(user_id):
    current_time = time.time()
    if user_id in user_last_request:
        last_request_time = user_last_request[user_id]
        if current_time - last_request_time < 10:
            return False
    user_last_request[user_id] = current_time
    return True

def save_user(user_id, first_name, username):
    user_data = {
        'user_id': user_id,
        'first_name': first_name,
        'username': username if username else None,
        'joined_at': datetime.now(),
        'last_active': datetime.now()
    }
    
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': user_data, '$setOnInsert': {'total_checks': 0}},
        upsert=True
    )

def update_user_activity(user_id):
    users_collection.update_one(
        {'user_id': user_id},
        {'$set': {'last_active': datetime.now()}, '$inc': {'total_checks': 1}}
    )

def get_total_users():
    return users_collection.count_documents({})

def get_active_users():
    cutoff_date = datetime.now() - timedelta(days=30)
    return users_collection.count_documents({'last_active': {'$gte': cutoff_date}})

def check_membership(user_id):
    try:
        member1 = bot.get_chat_member(CHANNEL_1, user_id)
        member2 = bot.get_chat_member(CHANNEL_2, user_id)
        return member1.status in ['member', 'administrator', 'creator'] and member2.status in ['member', 'administrator', 'creator']
    except:
        return False

def send_log(message_text):
    try:
        bot.send_message(LOG_CHANNEL_ID, message_text, parse_mode='HTML')
    except:
        pass

def show_loading_animation(chat_id, username, loading_msg_id):
    progress_frames = [
        "▰▱▱▱▱▱▱▱▱▱ 10%",
        "▰▰▱▱▱▱▱▱▱▱ 20%",
        "▰▰▰▱▱▱▱▱▱▱ 30%",
        "▰▰▰▰▱▱▱▱▱▱ 40%",
        "▰▰▰▰▰▱▱▱▱▱ 50%",
        "▰▰▰▰▰▰▱▱▱▱ 60%",
        "▰▰▰▰▰▰▰▱▱▱ 70%",
        "▰▰▰▰▰▰▰▰▱▱ 80%",
        "▰▰▰▰▰▰▰▰▰▱ 90%",
        "▰▰▰▰▰▰▰▰▰▰ 100%"
    ]
    
    messages = [
        f"🔍 Searching for @{username}...",
        "📡 Connecting to Instagram API...",
        "📥 Fetching profile data...",
        "🖼️ Downloading profile picture...",
        "📊 Processing statistics...",
        "✨ Finalizing results..."
    ]
    
    for i in range(len(progress_frames)):
        if i < len(messages):
            text = f"{progress_frames[i]}\n{messages[i]}"
        else:
            text = f"{progress_frames[i]}\n✨ Almost done..."
        
        try:
            bot.edit_message_text(text, chat_id, loading_msg_id)
        except:
            pass
        time.sleep(0.3)
        
def fetch_instagram_data(username):
    if not INSTAGRAM_INFO_API:
        return {"success": False}

    url = f"{INSTAGRAM_INFO_API}{username}"

    for _ in range(2):
        try:
            response = requests.get(url, timeout=(5, 15))
            if response.status_code != 200:
                raise Exception()

            raw = response.json()
            data = raw.get("data", {})

            return {
                'profile_pic_url': data.get('profile_image_hd'),
                'username': data.get('username'),
                'name': data.get('full_name', 'N/A'),
                'bio': data.get('bio', 'No bio'),
                'user_id': data.get('id', 'N/A'),
                'followers': data.get('followers', 0),
                'following': data.get('following', 0),
                'posts': data.get('posts', 0),
                'is_private': data.get('is_private', False),
                'is_verified': data.get('is_verified', False),
                'is_business': data.get('is_business_account', False),
                'is_professional': data.get('is_professional_account', False),
                'is_new': data.get('is_new_to_instagram', False),
                'meta_verified_eligible': data.get('is_eligible_for_meta_verified_label', False),
                'account_created_year': data.get('account_created_year'),
                'success': True
            }

        except:
            time.sleep(1)

    return {"success": False}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username if message.from_user.username else "No username"
    
    save_user(user_id, first_name, username)
    
    log_message = f"""🆕 New user started the Insta info bot

👤 <b>Name:</b> {first_name}
🆔 <b>User ID:</b> <code>{user_id}</code>
📛 <b>Username:</b> @{username}
📩 <b>Message:</b> The user has started the bot."""
    send_log(log_message)
    
    if not check_membership(user_id):
        markup = types.InlineKeyboardMarkup()
        channel1_btn = types.InlineKeyboardButton("📢 Channel 1", url=f"https://t.me/{CHANNEL_1[1:]}")
        channel2_btn = types.InlineKeyboardButton("🤖 Channel 2", url=f"https://t.me/{CHANNEL_2[1:]}")
        check_btn = types.InlineKeyboardButton("✅ Check Membership", callback_data="check_membership")
        markup.add(channel1_btn, channel2_btn)
        markup.add(check_btn)
        
        welcome_msg = f"""✨ Welcome {first_name}!

📌 To use this bot, you must join our channels:

⚠️ After joining, click the "✅ Check Membership" button below.
➡️ Then use /check to get Instagram information."""
        
        bot.send_message(message.chat.id, welcome_msg, reply_markup=markup, parse_mode='HTML')
        return
    
    welcome_msg = f"""👋 Welcome {first_name}!

🤖 I'm Instagram Information Bot
📸 I can fetch Instagram profile details

📌 Available Commands:
/check - Get Instagram account info
/help - How to use bot

✨ Simply use /check and send me the Instagram username!"""
    
    bot.send_message(message.chat.id, welcome_msg)

@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership_callback(call):
    user_id = call.from_user.id
    if check_membership(user_id):
        bot.answer_callback_query(call.id, "✅ Membership verified! Now use /check command.")
        bot.send_message(call.message.chat.id, "✅ Great! You're now a member.\n\n➡️ Use /check to get Instagram information.")
    else:
        bot.answer_callback_query(call.id, "❌ Please join both channels first!", show_alert=True)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """📚 Quick Guide:

🤖 How to use this bot:

1️⃣ Use /check command
2️⃣ Send me the Instagram username (without @)
3️⃣ Wait while I fetch the data
4️⃣ Receive the profile info with photo

📌 Example:
/check
Then send: instagram

⚠️ Note:
• Works with public and private accounts
• Don't add @ symbol before username
• Make sure username is correct

🎯 Available Commands:
/start - Start the bot
/check - Check Instagram info
/help - This guide

🤖 BY - @SudeepHu"""
    
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['check'])
def check_command(message):
    user_id = message.from_user.id
    if not check_membership(user_id):
        markup = types.InlineKeyboardMarkup()
        channel1_btn = types.InlineKeyboardButton(
            "📢 Channel 1", url=f"https://t.me/{CHANNEL_1[1:]}"
        )
        channel2_btn = types.InlineKeyboardButton(
            "🤖 Channel 2", url=f"https://t.me/{CHANNEL_2[1:]}"
        )
        check_btn = types.InlineKeyboardButton(
            "✅ Verify", callback_data="check_membership"
        )
        markup.add(channel1_btn, channel2_btn)
        markup.add(check_btn)
        bot.send_message(
            message.chat.id,
            "❌ Please join both channels first to use this bot!",
            reply_markup=markup
        )
        return
    msg = bot.send_message(
        message.chat.id,
        "👤 Please send me the Instagram username (without @):"
    )
    bot.register_next_step_handler(msg, process_username)

def process_username(message):
    user_id = message.from_user.id
    
    if not can_make_request(user_id):
        bot.send_message(message.chat.id, "⏳ Please wait 10 seconds before making another request!")
        return
    
    if message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Please send a valid Instagram username, not a command.")
        return
    
    username = message.text.strip()
    
    loading_msg = bot.send_message(message.chat.id, "🔄 Starting process...")
    
    loading_thread = Thread(
    target=show_loading_animation,
    args=(message.chat.id, username, loading_msg.message_id),
    daemon=True
    )
    loading_thread.start()
    
    data = fetch_instagram_data(username)
    
    try:
        bot.delete_message(message.chat.id, loading_msg.message_id)
    except:
        pass
    
    if not data.get('success'):
        error_msg = f"❌ Error: Could not fetch data for @{username}\n\n⚠️ Please check:\n1. Username is correct\n2. Account exists\n3. Try again later\n\nError: {data.get('error', 'Unknown error')}"
        bot.send_message(message.chat.id, error_msg)
        return
    
    update_user_activity(user_id)
    
    bio_text = data.get('bio') or "No bio"
    followers_formatted = f"{(data.get('followers') or 0):,}"
    following_formatted = f"{(data.get('following') or 0):,}"
    posts_formatted = f"{(data.get('posts') or 0):,}"
    
    private_emoji = "✅" if data.get('is_private') else "❌"
    verified_emoji = "✅" if data.get('is_verified') else "❌"
    business_emoji = "✅" if data.get('is_business') else "❌"
    professional_emoji = "✅" if data.get('is_professional') else "❌"
    new_emoji = "✅" if data.get('is_new') else "❌"
    meta_verified_emoji = "✅" if data.get('meta_verified_eligible') else "❌"
    
    caption = f"""📊 Info for @{username}

👤 Username: @{username}
📛 Name: {data['name']}
🆔 ID: {data['user_id']}
📝 Bio: {bio_text}
👥 Followers: {followers_formatted}
👤 Following: {following_formatted}
📸 Posts: {posts_formatted}
🔒 Private: {private_emoji}
✅ Verified: {verified_emoji}
💼 Business Acc: {business_emoji}
👨‍💻 Professional Acc: {professional_emoji}
🆕 New to Instagram: {new_emoji}
🔷 Meta Verified Eligible: {meta_verified_emoji}
📅 Account Created Year: {data['account_created_year']}

🔗 Link: https://instagram.com/{username}

🤖 BY - @SudeepHu"""
    try:
        if data['profile_pic_url']:
            img_response = requests.get(data['profile_pic_url'], timeout=10)
            if img_response.status_code == 200:
                bot.send_photo(
                    message.chat.id, 
                    data['profile_pic_url'], 
                    caption=caption
                )
            else:
                bot.send_message(message.chat.id, caption)
        else:
            bot.send_message(message.chat.id, caption)
    except Exception as e:
        error_caption = caption + f"\n\n⚠️ Note: Profile picture could not be loaded."
        bot.send_message(message.chat.id, error_caption)

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Access denied!")
        return
    
    msg = bot.send_message(message.chat.id, "📢 Send the broadcast message:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    broadcast_msg = message.text
    total_users = get_total_users()
    bot.send_message(message.chat.id, f"📤 Broadcasting to {total_users} users...")
    
    success = 0
    failed = 0
    
    all_users = users_collection.find({})
    for user in all_users:
        try:
            bot.send_message(user['user_id'], f"📢 ANNOUNCEMENT:\n\n{broadcast_msg}")
            success += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ Broadcast completed!\n\n📊 Stats:\n✅ Success: {success}\n❌ Failed: {failed}")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Access denied!")
        return
    
    total_users = get_total_users()
    active_users = get_active_users()
    
    top_users = users_collection.find().sort('total_checks', -1).limit(5)
    top_users_text = ""
    for i, user in enumerate(top_users, 1):
        username_display = f"@{user['username']}" if user.get('username') else "No username"
        top_users_text += f"{i}. {user['first_name']} ({username_display}) - {user.get('total_checks', 0)} checks\n"
    
    stats_text = f"""📊 BOT STATISTICS

👥 Total Users: {total_users}
👤 Active Users (30 days): {active_users}

👨‍💻 Admin: #𝐒𝐏</>
🆔 Admin ID: {ADMIN_ID}
💾 Database: MongoDB
⚡ Status: Running"""
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ Unknown command. Use /help to see available commands.")
    else:
        bot.send_message(message.chat.id, "🤖 Please use /check to get Instagram information or /help for guide.")

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 insta info Bot is running healthy!"

@app.route('/health')
def health():
    total_users = get_total_users()
    active_users = get_active_users()
    return {"status": "healthy", "total_users": total_users, "active_users": active_users, "timestamp": datetime.now().isoformat()}

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def run_bot():
    while True:
        try:
            print("🤖 Starting Telegram Bot...")
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Bot crashed: {e}")
            print("🔄 Restarting bot in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("🚀 insta info Bot...")
    run_bot()
