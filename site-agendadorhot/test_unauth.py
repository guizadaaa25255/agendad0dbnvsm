import asyncio
from telethon import TelegramClient, functions, types

async def test_unauth():
    # Public sticker set can sometimes be accessed or let's test
    client = TelegramClient(None, 38038737, "825a5e23a53d5991ba488adfec3da147")
    await client.connect()
    try:
        res = await client(functions.messages.GetStickerSetRequest(
            stickerset=types.InputStickerSetShortName(short_name="pinkcandyy"),
            hash=0
        ))
        print(f"Success! {len(res.documents)} docs found.")
    except Exception as e:
        print("Error with unauth:", type(e), e)
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_unauth())
