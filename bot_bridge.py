import os
import logging
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from supabase import create_client, Client

# --- 1. KEEP ALIVE SYSTEM (FOR RENDER FREE TIER) ---
# This creates a tiny web server so Render doesn't kill the bot
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Render provides a PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()

# --- 2. CONFIGURATION ---
load_dotenv() 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, TELEGRAM_TOKEN]):
    print("❌ ERROR: Missing environment variables!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- 3. THE BROADCAST COMMAND ---
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Usage: /send \"Title\" \"Message Body\"")
            return

        title = context.args[0]
        body = " ".join(context.args[1:])

        await update.message.reply_text("⏳ Fetching users and sending broadcast...")

        users_response = supabase.table("profiles").select("id").execute()
        users = users_response.data

        if not users:
            await update.message.reply_text("⚠️ No users found in the profiles table.")
            return

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

# --- 4. START THE BOT ---
if __name__ == '__main__':
    # Start the web server in the background
    print("🌐 Starting web server for Render Free Tier...")
    keep_alive()
    
    # Start the Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("send", send_broadcast))
    
    print("🤖 Telegram Notifier Bot is running...")
    application.run_polling()