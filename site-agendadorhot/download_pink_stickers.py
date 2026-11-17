import asyncio
import os
import sys
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler")
os.chdir(str(BASE))
sys.path.insert(0, str(BASE))

from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from app.database import SessionLocal
from app.models import TelegramAccount
from app.telegram_client import account_credentials
from app.security import decrypt_session

async def fetch_and_save_stickers():
    db = SessionLocal()
    acc = db.query(TelegramAccount).filter(TelegramAccount.is_active == True).first()
    if not acc:
        print("No active account found in local db!")
        return

    session_str = decrypt_session(acc.encrypted_session)
    cid, chash = account_credentials(acc)
    client = TelegramClient(StringSession(session_str), cid, chash)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("User not authorized!")
        await client.disconnect()
        return

    print("Connected to Telegram successfully!")
    
    out_dir = BASE / "pinkcandyy_stickers"
    out_dir.mkdir(exist_ok=True)

    res = await client(functions.messages.GetStickerSetRequest(
        stickerset=types.InputStickerSetShortName(short_name="pinkcandyy"),
        hash=0
    ))
    
    print(f"Total documents: {len(res.documents)}")
    for i, doc in enumerate(res.documents):
        path = out_dir / f"doc_{i:02d}_{doc.id}.webp"
        if not path.exists():
            await client.download_media(doc, str(path))
        
        # Check document attributes (like alt)
        alts = []
        for a in doc.attributes:
            if isinstance(a, types.DocumentAttributeSticker):
                alts.append(a.alt)
        print(f"Doc {i:02d}: id={doc.id}, alt={alts}")

    await client.disconnect()
    print("Done downloading all stickers!")

if __name__ == "__main__":
    asyncio.run(fetch_and_save_stickers())
