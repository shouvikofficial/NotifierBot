import os
import logging
import threading
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
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
        text = update.message.text
        # Remove the '/send ' prefix to get the actual command content
        prefix_len = len(update.message.text.split(' ')[0]) + 1
        msg_content = update.message.text[prefix_len:].strip()
        
        parts = [p.strip() for p in msg_content.split('|')]
        
        if len(parts) < 2:
            await update.message.reply_text("❌ Usage: /send Title | Message Body | [Image URL] | [Action Link]")
            return

        title = parts[0]
        body = parts[1]
        image_url = parts[2] if len(parts) > 2 and parts[2] else None
        action_link = parts[3] if len(parts) > 3 and parts[3] else None

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
                "image_url": image_url,
                "action_link": action_link,
                "is_read": False
            }).execute()
            count += 1

        await update.message.reply_text(f"🚀 Success! Sent '{title}' to {count} users.")

    except Exception as e:
        logging.error(f"Error in broadcast: {e}")
        await update.message.reply_text(f"❌ Critical Error: {e}")

# --- 4. PHOTO HANDLING ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        caption = update.message.caption
        if not caption or not caption.startswith('/send'):
            return  # Ignore photos without the /send command in the caption

        # Parse caption identical to standard /send command
        prefix_len = len(caption.split(' ')[0]) + 1
        msg_content = caption[prefix_len:].strip()
        
        parts = [p.strip() for p in msg_content.split('|')]
        
        if len(parts) < 2:
            await update.message.reply_text("❌ Usage in caption: /send Title | Message Body | [Optional Action Link]")
            return
            
        title = parts[0]
        body = parts[1]
        # Skip parts[2] since the image URL will be generated locally
        action_link = parts[2] if len(parts) > 2 and parts[2] else None
        if len(parts) > 3:
            action_link = parts[3] if parts[3] else action_link

        await update.message.reply_text("⏳ Uploading image to Supabase and sending broadcast...")

        # 1. Download Photo
        photo_file = await update.message.photo[-1].get_file()
        file_bytes = await photo_file.download_as_bytearray()
        
        # 2. Upload to Supabase Storage
        file_name = f"notification_{update.message.message_id}.jpg"
        bucket_name = "notifications"
        
        try:
            supabase.storage.from_(bucket_name).upload(
                file_name,
                bytes(file_bytes),
                {"content-type": "image/jpeg"}
            )
        except Exception as e:
            if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                raise e # Throw if it's a real error, otherwise it's just a duplicate retry

        # 3. Get Public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)

        # 4. Save to DB
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
                "image_url": public_url,
                "action_link": action_link,
                "is_read": False
            }).execute()
            count += 1

        await update.message.reply_text(f"🚀 Success! Sent '{title}' with photo to {count} users.")

    except Exception as e:
        logging.error(f"Error handling photo: {e}")
        await update.message.reply_text(f"❌ Failed to process photo: {e}")

# --- 5. START THE BOT ---
if __name__ == '__main__':
    # Start the web server in the background
    print("🌐 Starting web server for Render Free Tier...")
    keep_alive()
    
    # Start the Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("send", send_broadcast))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Telegram Notifier Bot is running...")
    application.run_polling()