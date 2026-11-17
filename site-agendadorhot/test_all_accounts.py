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

async def test_accounts():
    db = SessionLocal()
    accounts = db.query(TelegramAccount).all()
    for acc in accounts:
        print(f"\nTesting Account #{acc.id} ({acc.first_name} {acc.phone})...")
        try:
            session_str = decrypt_session(acc.encrypted_session)
            cid, chash = account_credentials(acc)
            client = TelegramClient(StringSession(session_str), cid, chash)
            await client.connect()
            auth = await client.is_user_authorized()
            print(f"  Authorized: {auth}")
            if auth:
                # Try fetching pinkcandyy
                res = await client(functions.messages.GetStickerSetRequest(
                    stickerset=types.InputStickerSetShortName(short_name="pinkcandyy"),
                    hash=0
                ))
                print(f"  SUCCESS! Fetched pinkcandyy with {len(res.documents)} documents!")
                await client.disconnect()
                return client, res, acc
            await client.disconnect()
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_accounts())
