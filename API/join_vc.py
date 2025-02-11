from fastapi import FastAPI
from pyrogram import Client
from pytgcalls import PyTgCalls
from pyrogram.types import InputStream
import os

app = FastAPI()

# API credentials from environment variables (Vercel Environment Variables)
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")

# Create Client instance for userbot
client = Client("my_userbot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Initialize PyTgCalls for Voice Calls
call = PyTgCalls(client)

# API endpoint to join group voice call
@app.get("/join_vc")
def join_vc(chat_id: int, audio_file: str):
    try:
        with client:
            call.join_group_call(chat_id, InputStream(audio_file))  # Join Voice Call with Audio File
        return {"status": "success", "message": "Joined group call", "chat_id": chat_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}
