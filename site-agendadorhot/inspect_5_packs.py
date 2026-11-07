import asyncio
import json
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
from app.database import SessionLocal
from app.models import TelegramAccount
from app.telegram_client import account_credentials
from app.security import decrypt_session

PACKS = [
    {"short_name": "mfslots", "label": "Mf Pink / Red 3D", "badge": "🍓 Vermelho / Rosa 3D"},
    {"short_name": "goxtosastyle", "label": "Goxtosa Style Rosa", "badge": "🌸 Rosa Chiclete Suave"},
    {"short_name": "pinkcandyy", "label": "Pink Candy Listrado", "badge": "🍭 Rosa Doce Listrado"},
    {"short_name": "docelaranja", "label": "Doce Laranja Listrado", "badge": "🍊 Laranja Listrado"},
    {"short_name": "isapurpleblue", "label": "Isa Purple / Blue 3D", "badge": "💜 Roxo / Azul 3D"}
]

async def inspect_all_5():
    db = SessionLocal()
    acc = db.query(TelegramAccount).filter(TelegramAccount.is_active == True).first()
    session_str = decrypt_session(acc.encrypted_session)
    cid, chash = account_credentials(acc)
    client = TelegramClient(StringSession(session_str), cid, chash)
    await client.connect()

    results = {}

    for p in PACKS:
        sname = p["short_name"]
        print(f"\n==============================================")
        print(f"Buscando pack: {sname}...")
        try:
            res = await client(functions.messages.GetStickerSetRequest(
                stickerset=types.InputStickerSetShortName(short_name=sname),
                hash=0
            ))
            print(f"Pack Title: '{res.set.title}', Total Docs: {len(res.documents)}")
            
            # Instala o pack para garantir que a conta possa usar perfeitamente
            try:
                await client(functions.messages.InstallStickerSetRequest(
                    stickerset=types.InputStickerSetShortName(short_name=sname),
                    archived=False
                ))
                print(f"Instalado na conta {acc.first_name}!")
            except Exception as ie:
                print("Install error (pode já estar instalado):", ie)

            docs_info = []
            for i, doc in enumerate(res.documents):
                docs_info.append(doc.id)

            results[sname] = {
                "name": sname,
                "label": p["label"],
                "badge": p["badge"],
                "title": res.set.title,
                "short_name": sname,
                "total": len(res.documents),
                "doc_ids": docs_info
            }
        except Exception as e:
            print(f"Erro ao buscar {sname}: {e}")

    with open("inspected_5_packs.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Salvo em inspected_5_packs.json!")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect_all_5())
