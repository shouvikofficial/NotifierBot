from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Use your actual ID and Hash from your logs
API_ID = 34748224 
API_HASH = '4a5b76ba2a82d88ce0368c7d29cde72a'

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\n--- COPY THE LINE BELOW --- \n")
    print(client.session.save())
    print("\n--- END OF STRING ---")