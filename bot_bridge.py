import os
import logging
from dotenv import load_dotenv  # ✅ FIXED: Added this import
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

# --- 1. CONFIGURATION ---
# Load variables from your .env file
load_dotenv() 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ✅ SECURITY CHECK: Ensure all keys are found
if not all([SUPABASE_URL, SUPABASE_KEY, TELEGRAM_TOKEN]):
    print("❌ ERROR: One or more environment variables are missing!")
    print(f"URL: {'OK' if SUPABASE_URL else 'MISSING'}")
    print(f"KEY: {'OK' if SUPABASE_KEY else 'MISSING'}")
    print(f"TOKEN: {'OK' if TELEGRAM_TOKEN else 'MISSING'}")
    exit(1)

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- 2. THE BROADCAST COMMAND ---
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: /send \"Title\" \"Message Body\"")
            return

        title = context.args[0]
        body = " ".join(context.args[1:])

        await update.message.reply_text("⏳ Fetching users and sending broadcast...")

        # 1. Get all user IDs from profiles table
        users_response = supabase.table("profiles").select("id").execute()
        users = users_response.data

        if not users:
            await update.message.reply_text("⚠️ No users found in the profiles table.")
            return

        # 2. Insert notification for each user
        count = 0
        for user in users:
            supabase.table("notifications").insert({
                "user_id": user['id'],
                "title": title,
                "body": body,
                "is_read": False
            }).execute()
            count += 1

        await update.message.reply_text(f"🚀 Success! Sent '{title}' to {count} users.")

    except Exception as e:
        logging.error(f"Error in broadcast: {e}")
        await update.message.reply_text(f"❌ Critical Error: {e}")

# --- 3. START THE BOT ---
if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("send", send_broadcast))
    
    print("🤖 Telegram Notifier Bot is running...")
    print("Commands available: /send <title> <body>")
    
    application.run_polling()