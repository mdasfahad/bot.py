import asyncio
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)

# --- CONFIGURATION ---
BOT_TOKEN = "8686418799:AAE8dI47h-kE_HotH7yy9FQLKDZ83AzVMxw"
OWNER_ID = 8289191009

# Global States
bot_active = True
admins = {OWNER_ID}
blocked_users = set()
all_users = set()
active_signal_users = set()
user_states = {}  # Broadcast / Block ইনপুট ট্র্যাকিং

# Channel Config
REQUIRED_CHANNEL = "@your_channel_username" 
CHANNEL_LINK = "https://t.me/+8UAIuuTjL4RlY2U1"

MAINTENANCE_MSG = (
    "⚠️ <b>বট সাময়িকভাবে বন্ধ আছে!</b>\n\n"
    "আমাদের বটের কারিগরি কাজ চলছে। "
    "খুব দ্রুতই সার্ভিস আবার চালু হবে।"
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

# --- SUBSCRIPTION CHECKER ---
async def is_user_subscribed(bot, user_id):
    if not REQUIRED_CHANNEL.startswith("@") or REQUIRED_CHANNEL == "@your_channel_username":
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True

# --- KEYBOARDS ---
def get_user_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 JOIN TELEGRAM CHANNEL", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ VERIFY & START", callback_data="check_join")],
        [InlineKeyboardButton("🚀 START VIP SIGNAL", callback_data="start_signal")],
        [InlineKeyboardButton("🛑 STOP SIGNAL", callback_data="stop_signal")]
    ])

def get_admin_keyboard():
    status_btn = "🔴 Turn OFF Bot" if bot_active else "🟢 Turn ON Bot"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(status_btn, callback_data="toggle_bot")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 Block User", callback_data="admin_block"), InlineKeyboardButton("✅ Unblock User", callback_data="admin_unblock")],
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔄 Refresh Panel", callback_data="admin_refresh")]
    ])

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        return

    if not bot_active and user_id not in admins:
        await update.message.reply_text(MAINTENANCE_MSG, parse_mode="HTML")
        return

    all_users.add(user_id)

    if user_id in admins:
        welcome_text = (
            "<b>👑 ADMIN CONTROL PANEL 👑</b>\n\n"
            "নিচের বাটনগুলো ব্যবহার করে সম্পূর্ণ বট নিয়ন্ত্রণ করুন:"
        )
        await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    else:
        welcome_text = (
            "<b>🚦 VIP SIGNAL HACK BOT 🚦</b>\n\n"
            "Welcome to the official Signal Auto Bot!\n"
            "<i>Note: You must join our channel to receive VIP signals.</i>"
        )
        await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_user_keyboard())

# --- BUTTON CLICK HANDLER ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active  # ফিক্সড: ফাংশনের শুরুতেই গ্লোবাল ডিক্লেয়ার করা হয়েছে
    query = update.callback_query
    user_id = query.from_user.id

    if user_id in blocked_users:
        return

    await query.answer()

    if not bot_active and user_id not in admins:
        await query.message.reply_text(MAINTENANCE_MSG, parse_mode="HTML")
        return

    data = query.data

    # USER BUTTONS
    if data == "check_join":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if subscribed:
            await query.message.reply_text("✅ Verification successful! Click 'START VIP SIGNAL'.")
        else:
            await query.message.reply_text("⚠️ You haven't joined the channel yet! Please join first.")

    elif data == "start_signal":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if not subscribed:
            await query.message.reply_text("⚠️ Must join channel first!", quote=True)
            return

        if user_id not in active_signal_users:
            active_signal_users.add(user_id)
            await query.message.reply_text("✅ <b>VIP Signal Started!</b>\nYou will now receive live signals every 30 seconds.", parse_mode="HTML")
            asyncio.create_task(send_live_signals(user_id, context))
        else:
            await query.message.reply_text("⚠️ Signals are already running for you!")

    elif data == "stop_signal":
        if user_id in active_signal_users:
            active_signal_users.remove(user_id)
            await query.message.reply_text("🛑 <b>VIP Signal Stopped.</b>", parse_mode="HTML")

    # ADMIN BUTTONS
    elif user_id in admins:
        if data == "toggle_bot":
            bot_active = not bot_active
            if not bot_active:
                active_signal_users.clear()
            msg = "🔴 Bot is now OFF (Maintenance Mode)" if not bot_active else "🟢 Bot is now ONLINE!"
            await query.edit_message_reply_markup(reply_markup=get_admin_keyboard())
            await query.message.reply_text(msg)

        elif data == "admin_stats":
            stats_text = (
                f"📊 <b>Bot Statistics:</b>\n\n"
                f"👥 Total Users: {len(all_users)}\n"
                f"⚡ Active Signal Users: {len(active_signal_users)}\n"
                f"🚫 Blocked Users: {len(blocked_users)}\n"
                f"🟢 Status: {'Online' if bot_active else 'Maintenance'}"
            )
            await query.message.reply_text(stats_text, parse_mode="HTML")

        elif data == "admin_broadcast":
            user_states[user_id] = "AWAITING_BROADCAST"
            await query.message.reply_text("📢 ব্রডকাস্ট করার মেসেজটি লিখে পাঠান:")

        elif data == "admin_block":
            user_states[user_id] = "AWAITING_BLOCK"
            await query.message.reply_text("🚫 যে ইউজারকে ব্লক করতে চান তার Telegram User ID লিখে পাঠান:")

        elif data == "admin_unblock":
            user_states[user_id] = "AWAITING_UNBLOCK"
            await query.message.reply_text("✅ যে ইউজারকে আনব্লক করতে চান তার Telegram User ID লিখে পাঠান:")

        elif data == "admin_refresh":
            await query.edit_message_reply_markup(reply_markup=get_admin_keyboard())

# --- TEXT INPUTS FOR ADMIN ---
async def handle_admin_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admins:
        return

    state = user_states.get(user_id)
    text = update.message.text

    if state == "AWAITING_BROADCAST":
        del user_states[user_id]
        count = 0
        for uid in list(all_users):
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 <b>ANNOUNCEMENT:</b>\n\n{text}", parse_mode="HTML")
                count += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে।")

    elif state == "AWAITING_BLOCK":
        del user_states[user_id]
        if text.isdigit():
            target_id = int(text)
            blocked_users.add(target_id)
            active_signal_users.discard(target_id)
            await update.message.reply_text(f"🚫 User {target_id} ব্লক করা হয়েছে।")
        else:
            await update.message.reply_text("⚠️ সঠিক ID পাঠাননি।")

    elif state == "AWAITING_UNBLOCK":
        del user_states[user_id]
        if text.isdigit():
            target_id = int(text)
            blocked_users.discard(target_id)
            await update.message.reply_text(f"✅ User {target_id} আনব্লক করা হয়েছে।")
        else:
            await update.message.reply_text("⚠️ সঠিক ID পাঠাননি।")

# --- LIVE SIGNAL SENDER ---
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

# --- MAIN RUNNER ---
def main():
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_inputs))
    
    print("Bot is running...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
