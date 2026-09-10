import asyncio
import random
from datetime import datetime, timezone
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# --- FLASK WEB SERVER FOR KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive & Running 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- CONFIGURATION ---
BOT_TOKEN = "8686418799:AAE8dI47h-kE_HotH7yy9FQLKDZ83AzVMxw"
OWNER_ID = 8289191009

# Global States & Stores
bot_active = True  # Maintenance Mode Toggle
admins = {OWNER_ID}
blocked_users = set()
all_users = set()
active_signal_users = set()

# Channel Config
REQUIRED_CHANNEL = "@your_channel_username" 
CHANNEL_LINK = "https://t.me/+8UAIuuTjL4RlY2U1"

# Maintenance Message
MAINTENANCE_MSG = (
    "⚠️ <b>বট সাময়িকভাবে বন্ধ আছে!</b>\n\n"
    "আমাদের বটের কিছু কারিগরি কাজ (Maintenance) চলছে। "
    "সাধারণত ২৪ থেকে ৪৮ ঘণ্টার মধ্যে সিস্টেম ঠিক হয়ে যাবে।\n"
    "ধৈর্য ধরার জন্য ধন্যবাদ।"
)

# --- SIGNAL GENERATOR ---
def get_signal_data():
    now = datetime.now(timezone.utc)
    year_str = now.strftime("%Y%m%d")
    total_seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    period_index = (total_seconds_today // 30) + 1
    period_number = f"{year_str}10005{period_index:04d}"
    
    selected_num = random.choice(list(range(10)))
    sig_type = "🟢 BIG" if selected_num >= 5 else "🔴 SMALL"
        
    return period_number[-4:], sig_type, selected_num

# --- FORCE JOIN CHECKER ---
async def is_user_subscribed(bot, user_id):
    if not REQUIRED_CHANNEL.startswith("@"):
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        return True
    return False

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # 1. Blocked User Check (No Response)
    if user_id in blocked_users:
        return

    # 2. Maintenance Mode Check
    if not bot_active and user_id not in admins:
        await update.message.reply_text(MAINTENANCE_MSG, parse_mode="HTML")
        return

    all_users.add(user_id)

    keyboard = [
        [InlineKeyboardButton("📢 JOIN TELEGRAM CHANNEL", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ VERIFY & START", callback_data="check_join")],
        [InlineKeyboardButton("🚀 START VIP SIGNAL", callback_data="start_signal")],
        [InlineKeyboardButton("🛑 STOP SIGNAL", callback_data="stop_signal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "<b>🚦 VIP SIGNAL HACK BOT 🚦</b>\n\n"
        "Welcome to the official Signal Auto Bot!\n"
        "<i>Note: You must join our channel to receive VIP signals.</i>"
    )
    
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    # 1. Blocked User Check (No Response)
    if user_id in blocked_users:
        return

    await query.answer()

    # 2. Maintenance Mode Check
    if not bot_active and user_id not in admins:
        await query.message.reply_text(MAINTENANCE_MSG, parse_mode="HTML")
        return

    if query.data == "check_join":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if subscribed:
            await query.message.reply_text("✅ Verification successful! Click 'START VIP SIGNAL'.")
        else:
            await query.message.reply_text("⚠️ You haven't joined the channel yet! Please join first.")

    elif query.data == "start_signal":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if not subscribed:
            await query.message.reply_text("⚠️ Must join channel first!", quote=True)
            return

        if user_id not in active_signal_users:
            active_signal_users.add(user_id)
            await query.edit_message_text(
                "✅ <b>VIP Signal Started!</b>\nYou will now receive live signals every 30 seconds.",
                parse_mode="HTML"
            )
            asyncio.create_task(send_live_signals(user_id, context))
        else:
            await query.message.reply_text("⚠️ Signals are already running for you!")

    elif query.data == "stop_signal":
        if user_id in active_signal_users:
            active_signal_users.remove(user_id)
            await query.edit_message_text("🛑 <b>VIP Signal Stopped.</b>", parse_mode="HTML")

# --- SIGNAL SENDER ---
async def send_live_signals(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    while user_id in active_signal_users and user_id not in blocked_users and bot_active:
        now = datetime.now(timezone.utc)
        remaining_seconds = 30 - (now.second % 30)
        
        await asyncio.sleep(remaining_seconds)
        
        if user_id not in active_signal_users or user_id in blocked_users or not bot_active:
            break

        prd, sig_type, num = get_signal_data()
        
        msg = (
            f"<b>🚦 VIP LIVE SIGNAL 🚦</b>\n\n"
            f"<b>📌 PRD:</b> <code>{prd}</code>\n"
            f"<b>🎯 RESULT:</b> <b>{sig_type}</b>\n"
            f"<b>🎲 NUMBER:</b> <code>{num}</code>\n\n"
            f"⏳ <i>Next signal in 30 seconds...</i>"
        )
        
        try:
            await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
        except Exception:
            active_signal_users.discard(user_id)
            break

# --- ADMIN PANEL COMMANDS ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins: return

    status_str = "🟢 ONLINE" if bot_active else "🔴 OFF (Maintenance)"

    admin_msg = (
        f"<b>🛠 ADMIN PANEL COMMANDS 🛠</b>\n"
        f"<b>Current Bot Status:</b> {status_str}\n\n"
        "🔴 <code>/bot-off</code> - Turn OFF bot (Show Maintenance Notice)\n"
        "🟢 <code>/bot-on</code> - Turn ON bot\n"
        "📢 <code>/setchannel <url> <@username></code> - Change Join Channel\n"
        "✉️ <code>/broadcast <text></code> - Send notice to all users\n"
        "🚫 <code>/block <user_id></code> - Block user (No Response)\n"
        "✅ <code>/unblock <user_id></code> - Unblock user\n"
        "👑 <code>/addadmin <user_id></code> - Add new admin\n"
        "🔄 <code>/transferowner <user_id></code> - Transfer ownership\n"
        "📊 <code>/stats</code> - Show total bot users"
    )
    await update.message.reply_text(admin_msg, parse_mode="HTML")

async def toggle_bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if update.effective_user.id not in admins: return
    bot_active = False
    active_signal_users.clear()
    await update.message.reply_text("🔴 <b>Bot Maintenance Mode ENABLED!</b> Users will now see the maintenance notice.", parse_mode="HTML")

async def toggle_bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if update.effective_user.id not in admins: return
    bot_active = True
    await update.message.reply_text("🟢 <b>Bot is now ONLINE!</b> Users can use the bot normally.", parse_mode="HTML")

async def set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHANNEL_LINK, REQUIRED_CHANNEL
    if update.effective_user.id not in admins: return
    if len(context.args) >= 2:
        CHANNEL_LINK = context.args[0]
        REQUIRED_CHANNEL = context.args[1]
        await update.message.reply_text(f"✅ Channel Updated:\nLink: {CHANNEL_LINK}\nHandle: {REQUIRED_CHANNEL}")
    else:
        await update.message.reply_text("Usage: /setchannel <link> <@channel_username>")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins: return
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("Usage: /broadcast <your message>")
        return

    count = 0
    for uid in list(all_users):
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>ADMIN ANNOUNCEMENT:</b>\n\n{msg_text}", parse_mode="HTML")
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Notice sent to {count} users.")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins: return
    if context.args:
        uid = int(context.args[0])
        blocked_users.add(uid)
        active_signal_users.discard(uid)
        await update.message.reply_text(f"🚫 User {uid} blocked! They will receive no response from now on.")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins: return
    if context.args:
        uid = int(context.args[0])
        blocked_users.discard(uid)
        await update.message.reply_text(f"✅ User {uid} unblocked.")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    if context.args:
        uid = int(context.args[0])
        admins.add(uid)
        await update.message.reply_text(f"👑 Added {uid} as Admin.")

async def transfer_ownership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    if update.effective_user.id != OWNER_ID: return
    if context.args:
        new_owner = int(context.args[0])
        OWNER_ID = new_owner
        admins.add(new_owner)
        await update.message.reply_text(f"🔄 Ownership transferred to {new_owner}.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in admins: return
    await update.message.reply_text(
        f"📊 <b>Bot Statistics:</b>\n\n"
        f"👥 Total Users: {len(all_users)}\n"
        f"⚡ Active Signals: {len(active_signal_users)}\n"
        f"🚫 Blocked Users: {len(blocked_users)}\n"
        f"🟢 Bot Active Status: {bot_active}",
        parse_mode="HTML"
    )

# --- MAIN ENGINE ---
def main():
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()
    
    # User Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))

    # Admin Handlers
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("bot-off", toggle_bot_off))
    app.add_handler(CommandHandler("bot-on", toggle_bot_on))
    app.add_handler(CommandHandler("setchannel", set_channel))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("transferowner", transfer_ownership))
    app.add_handler(CommandHandler("stats", stats))
    
    print("Bot Starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
