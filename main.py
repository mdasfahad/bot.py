import asyncio
import random
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)

# --- CONFIGURATION ---
BOT_TOKEN = "8686418799:AAE8dI47h-kE_HotH7yy9FQLKDZ83AzVMxw"
OWNER_ID = 8289191009

# Global Data Stores
bot_active = True
admins = {OWNER_ID}
blocked_users = set()
all_users = set()
active_signal_users = {}  # {user_id: interval_seconds}
user_states = {}          # State management
support_username = "your_admin_username"  # Default without @

# Channel Config
REQUIRED_CHANNEL = "@your_channel_username" 
CHANNEL_LINK = "https://t.me/+8UAIuuTjL4RlY2U1"

# License Store: {game_id: {"pass": "1234", "expiry": datetime_obj, "bound_user": user_id_or_None}}
licenses = {}

# User Session Store: {user_id: {"game_id": "12345", "logged_in": True}}
user_sessions = {}

MAINTENANCE_MSG = (
    "⚠️ <b>বট সাময়িকভাবে বন্ধ আছে!</b>\n\n"
    "আমাদের বটের কারিগরি কাজ চলছে। খুব দ্রুতই সার্ভিস আবার চালু হবে।"
)

# --- SIGNAL GENERATOR ---
def get_signal_data(interval_sec=30):
    now = datetime.now(timezone.utc)
    year_str = now.strftime("%Y%m%d")
    total_seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    period_index = (total_seconds_today // interval_sec) + 1
    
    code = "10005" if interval_sec == 30 else "10001"
    period_number = f"{year_str}{code}{period_index:04d}"
    
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
        [InlineKeyboardButton("🚀 START HACK (VIP)", callback_data="start_hack")],
        [InlineKeyboardButton("🛑 STOP SIGNAL", callback_data="stop_signal")],
        [InlineKeyboardButton("💬 SUPPORT", url=f"https://t.me/{support_username}?text=Hello,%20I%20need%20help")]
    ])

def get_market_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ 30 SECONDS MARKET", callback_data="mode_30")],
        [InlineKeyboardButton("⏱️ 1 MINUTE MARKET", callback_data="mode_60")],
        [InlineKeyboardButton("🚪 LOGOUT", callback_data="user_logout")]
    ])

def get_admin_keyboard():
    status_btn = "🔴 Turn OFF Bot" if bot_active else "🟢 Turn ON Bot"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(status_btn, callback_data="toggle_bot")],
        [InlineKeyboardButton("🔑 Create License", callback_data="admin_gen_lic"), InlineKeyboardButton("🗑️ Delete License", callback_data="admin_del_lic")],
        [InlineKeyboardButton("📜 View All Licenses", callback_data="admin_view_lic")],
        [InlineKeyboardButton("⚙️ Set Support Link", callback_data="admin_set_support")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 Block User", callback_data="admin_block"), InlineKeyboardButton("✅ Unblock User", callback_data="admin_unblock")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"), InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")]
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
        welcome_text = "<b>👑 ADMIN CONTROL PANEL 👑</b>\n\nনিচের বাটন ব্যবহার করে কাজ করুন:"
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
    global bot_active, support_username
    query = update.callback_query
    user_id = query.from_user.id

    if user_id in blocked_users:
        return

    await query.answer()

    if not bot_active and user_id not in admins:
        await query.message.reply_text(MAINTENANCE_MSG, parse_mode="HTML")
        return

    data = query.data

    # --- USER BUTTON ACTIONS ---
    if data == "check_join":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if subscribed:
            await query.message.reply_text("✅ Verification successful! Click 'START HACK (VIP)'.")
        else:
            await query.message.reply_text("⚠️ You haven't joined the channel yet! Please join first.")

    elif data == "start_hack":
        subscribed = await is_user_subscribed(context.bot, user_id)
        if not subscribed:
            await query.message.reply_text("⚠️ Must join channel first!", quote=True)
            return

        # Check existing login session
        session = user_sessions.get(user_id)
        if session and session.get("logged_in"):
            game_id = session.get("game_id")
            lic = licenses.get(game_id)
            if lic and datetime.now(timezone.utc) < lic["expiry"]:
                await query.message.reply_text("🎯 <b>Select Market Mode:</b>", parse_mode="HTML", reply_markup=get_market_keyboard())
                return
            else:
                user_sessions.pop(user_id, None)

        user_states[user_id] = {"step": "AWAITING_GAME_ID"}
        await query.message.reply_text("🔑 <b>আপনার Game ID দিন:</b>", parse_mode="HTML")

    elif data in ["mode_30", "mode_60"]:
        interval = 30 if data == "mode_30" else 60
        active_signal_users[user_id] = interval
        sec_text = "30 Seconds" if interval == 30 else "1 Minute"
        await query.message.reply_text(f"✅ <b>{sec_text} Market Signal Started!</b>\nYou will receive live signals.", parse_mode="HTML")
        asyncio.create_task(send_live_signals(user_id, context))

    elif data == "stop_signal":
        if user_id in active_signal_users:
            del active_signal_users[user_id]
            await query.message.reply_text("🛑 <b>VIP Signal Stopped.</b>", parse_mode="HTML")

    elif data == "user_logout":
        session = user_sessions.pop(user_id, None)
        if session:
            g_id = session.get("game_id")
            if g_id in licenses and licenses[g_id].get("bound_user") == user_id:
                licenses[g_id]["bound_user"] = None
        active_signal_users.pop(user_id, None)
        await query.message.reply_text("🚪 <b>লগআউট সফল হয়েছে!</b>", parse_mode="HTML")

    # --- ADMIN BUTTON ACTIONS ---
    elif user_id in admins:
        if data == "toggle_bot":
            bot_active = not bot_active
            if not bot_active:
                active_signal_users.clear()
            msg = "🔴 Bot is OFF (Maintenance)" if not bot_active else "🟢 Bot is ONLINE!"
            await query.edit_message_reply_markup(reply_markup=get_admin_keyboard())
            await query.message.reply_text(msg)

        elif data == "admin_gen_lic":
            user_states[user_id] = {"step": "ADMIN_ADD_LIC"}
            await query.message.reply_text(
                "🔑 <b>নতুন লাইসেন্স তৈরি করুন:</b>\n\n"
                "ফরম্যাট লিখে পাঠান: <code>GameID Password Days</code>\n"
                "উদাহরণ: <code>102030 pass123 7</code>", parse_mode="HTML"
            )

        elif data == "admin_del_lic":
            user_states[user_id] = {"step": "ADMIN_DEL_LIC"}
            await query.message.reply_text("🗑️ মুছে ফেলার জন্য <b>Game ID</b> টি লিখে পাঠান:", parse_mode="HTML")

        elif data == "admin_view_lic":
            if not licenses:
                await query.message.reply_text("📜 কোনো লাইসেন্স পাওয়া যায়নি।")
                return
            msg = "📜 <b>ACTIVE LICENSES:</b>\n\n"
            now = datetime.now(timezone.utc)
            for gid, data_item in licenses.items():
                rem_days = (data_item["expiry"] - now).days
                bound = data_item["bound_user"] if data_item["bound_user"] else "Free"
                msg += f"🆔 <b>ID:</b> <code>{gid}</code> | 🔑 <b>Pass:</b> <code>{data_item['pass']}</code> | ⏳ <b>Days:</b> {rem_days} | 📱 <b>Used:</b> {bound}\n"
            await query.message.reply_text(msg, parse_mode="HTML")

        elif data == "admin_set_support":
            user_states[user_id] = {"step": "ADMIN_SET_SUPPORT"}
            await query.message.reply_text("⚙️ সাপোর্টের জন্য Telegram Username পাঠান (@ ছাড়া):")

        elif data == "admin_stats":
            stats_text = (
                f"📊 <b>Bot Statistics:</b>\n\n"
                f"👥 Total Users: {len(all_users)}\n"
                f"🔑 Active Licenses: {len(licenses)}\n"
                f"⚡ Live Signal Users: {len(active_signal_users)}\n"
                f"🚫 Blocked Users: {len(blocked_users)}\n"
                f"🟢 Status: {'Online' if bot_active else 'Maintenance'}"
            )
            await query.message.reply_text(stats_text, parse_mode="HTML")

        elif data == "admin_broadcast":
            user_states[user_id] = {"step": "ADMIN_BROADCAST"}
            await query.message.reply_text("📢 ব্রডকাস্ট করার মেসেজটি লিখে পাঠান:")

        elif data == "admin_block":
            user_states[user_id] = {"step": "ADMIN_BLOCK"}
            await query.message.reply_text("🚫 ব্লক করতে চাওয়া User ID পাঠান:")

        elif data == "admin_unblock":
            user_states[user_id] = {"step": "ADMIN_UNBLOCK"}
            await query.message.reply_text("✅ আনব্লক করতে চাওয়া User ID পাঠান:")

        elif data == "admin_refresh":
            await query.edit_message_reply_markup(reply_markup=get_admin_keyboard())

# --- TEXT MESSAGE HANDLER ---
async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global support_username
    user_id = update.effective_user.id
    text = update.message.text.strip()

    state_info = user_states.get(user_id)

    if not state_info:
        return

    step = state_info.get("step")

    # --- USER LOGIN PROCESS ---
    if step == "AWAITING_GAME_ID":
        game_id = text
        lic = licenses.get(game_id)
        
        if not lic:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 পাসওয়ার্ড কিনতে চান? ক্লিক করুন", url=f"https://t.me/{support_username}?text=Hello,%20I%20want%20to%20buy%20a%20password")]
            ])
            await update.message.reply_text("❌ <b>ভুল Game ID দিয়েছেন!</b>\nসঠিক Game ID দিন বা পাসওয়ার্ড কিনতে যোগাযোগ করুন।", parse_mode="HTML", reply_markup=keyboard)
            return

        if datetime.now(timezone.utc) > lic["expiry"]:
            await update.message.reply_text("⚠️ <b>আপনার লাইসেন্সের মেয়াদ শেষ হয়ে গেছে!</b>", parse_mode="HTML")
            del user_states[user_id]
            return

        user_states[user_id] = {"step": "AWAITING_PASSWORD", "game_id": game_id}
        await update.message.reply_text("🔐 <b>আপনার Password দিন:</b>", parse_mode="HTML")

    elif step == "AWAITING_PASSWORD":
        game_id = state_info.get("game_id")
        lic = licenses.get(game_id)

        if not lic or text != lic["pass"]:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 পাসওয়ার্ড কিনতে যোগাযোগ করুন", url=f"https://t.me/{support_username}?text=Hello,%20I%20want%20to%20buy%20a%20password")]
            ])
            await update.message.reply_text("❌ <b>ভুল পাসওয়ার্ড দিয়েছেন!</b>", parse_mode="HTML", reply_markup=keyboard)
            return

        # Double Device Check
        if lic["bound_user"] is not None and lic["bound_user"] != user_id:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Support-এ কথা বলুন", url=f"https://t.me/{support_username}?text=My%20ID%20is%20already%20logged%20in%20another%20device")]
            ])
            await update.message.reply_text("⚠️ <b>এই আইডি এবং পাসওয়ার্ড দিয়ে ইতিমধ্যেই অন্য ডিভাইসে লগইন করা আছে!</b>", parse_mode="HTML", reply_markup=keyboard)
            del user_states[user_id]
            return

        # Bind user and save session
        lic["bound_user"] = user_id
        user_sessions[user_id] = {"game_id": game_id, "logged_in": True}
        del user_states[user_id]

        await update.message.reply_text("✅ <b>লগইন সফল হয়েছে!</b>\n\nমার্কেট নির্বাচন করুন:", parse_mode="HTML", reply_markup=get_market_keyboard())

    # --- ADMIN PROCESSES ---
    elif user_id in admins:
        if step == "ADMIN_ADD_LIC":
            del user_states[user_id]
            try:
                parts = text.split()
                gid, pwd, days = parts[0], parts[1], int(parts[2])
                exp_date = datetime.now(timezone.utc) + timedelta(days=days)
                licenses[gid] = {"pass": pwd, "expiry": exp_date, "bound_user": None}
                await update.message.reply_text(f"✅ <b>লাইসেন্স তৈরি হয়েছে!</b>\n🆔 ID: <code>{gid}</code>\n🔑 Pass: <code>{pwd}</code>\n⏳ Validity: {days} Days", parse_mode="HTML")
            except Exception:
                await update.message.reply_text("⚠️ ফরম্যাট সঠিক নয়! সঠিক নিয়ম: `GameID Password Days` (যেমন: 102030 pass123 7)")

        elif step == "ADMIN_DEL_LIC":
            del user_states[user_id]
            if text in licenses:
                del licenses[text]
                await update.message.reply_text(f"✅ License <code>{text}</code> সফলভাবে মুছে ফেলা হয়েছে।", parse_mode="HTML")
            else:
                await update.message.reply_text("⚠️ এই Game ID টি পাওয়া যায়নি।")

        elif step == "ADMIN_SET_SUPPORT":
            del user_states[user_id]
            support_username = text.replace("@", "")
            await update.message.reply_text(f"✅ সাপোর্ট ইউজারনেম আপডেট হয়েছে: @{support_username}")

        elif step == "ADMIN_BROADCAST":
            del user_states[user_id]
            count = 0
            for uid in list(all_users):
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 <b>ANNOUNCEMENT:</b>\n\n{text}", parse_mode="HTML")
                    count += 1
                except Exception:
                    pass
            await update.message.reply_text(f"✅ {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে।")

        elif step == "ADMIN_BLOCK":
            del user_states[user_id]
            if text.isdigit():
                target_id = int(text)
                blocked_users.add(target_id)
                active_signal_users.pop(target_id, None)
                await update.message.reply_text(f"🚫 User {target_id} ব্লক করা হয়েছে।")

        elif step == "ADMIN_UNBLOCK":
            del user_states[user_id]
            if text.isdigit():
                target_id = int(text)
                blocked_users.discard(target_id)
                await update.message.reply_text(f"✅ User {target_id} আনব্লক করা হয়েছে।")

# --- SIGNAL SENDER ---
async def send_live_signals(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    while user_id in active_signal_users and user_id not in blocked_users and bot_active:
        interval_sec = active_signal_users.get(user_id, 30)
        now = datetime.now(timezone.utc)
        remaining_seconds = interval_sec - (now.second % interval_sec)
        
        await asyncio.sleep(remaining_seconds)
        
        if user_id not in active_signal_users or user_id in blocked_users or not bot_active:
            break

        prd, sig_type, num = get_signal_data(interval_sec)
        
        msg = (
            f"<b>🚦 VIP LIVE SIGNAL ({interval_sec}s) 🚦</b>\n\n"
            f"<b>📌 PRD:</b> <code>{prd}</code>\n"
            f"<b>🎯 RESULT:</b> <b>{sig_type}</b>\n"
            f"<b>🎲 NUMBER:</b> <code>{num}</code>\n\n"
            f"⏳ <i>Next signal in {interval_sec} seconds...</i>"
        )
        
        try:
            await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
        except Exception:
            active_signal_users.pop(user_id, None)
            break

# --- MAIN RUNNER ---
def main():
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CallbackQueryHandler(button_click))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_inputs))
    
    print("Bot is running...")
    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
