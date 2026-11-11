import os
import random
import time
import uuid
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.stories import SendStoryRequest, TogglePinnedRequest
from telethon.tl.types import (
    InputPeerSelf,
    InputMediaUploadedPhoto,
    InputMediaUploadedDocument,
    DocumentAttributeVideo,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts,
    InputPrivacyValueAllowCloseFriends
)
from sqlalchemy.orm import Session

from app.config import TELEGRAM_API_ID, TELEGRAM_API_HASH, AVATARS_DIR
from app.security import encrypt_session, decrypt_session
from app.models import TelegramAccount, ScheduledStory
from app.media_utils import (
    inspect_video_metadata,
    extract_video_thumbnail,
    prepare_story_video,
)


# Fluxos de login em andamento (token -> cliente, telefone, hash do código, credenciais)
_PENDING_LOGINS: Dict[str, Dict[str, Any]] = {}


def resolve_credentials(api_id: Optional[str], api_hash: Optional[str]) -> Tuple[int, str]:
    """Usa o api_id/api_hash informado; se vazio, cai no padrão do .env."""
    api_id = (str(api_id).strip() if api_id is not None else "")
    api_hash = (api_hash or "").strip()
    if not api_id and not api_hash:
        if TELEGRAM_API_ID is None or not TELEGRAM_API_HASH:
            raise ValueError("Informe o api_id e o api_hash desta conta (my.telegram.org).")
        return TELEGRAM_API_ID, TELEGRAM_API_HASH
    if not api_id.isdigit():
        raise ValueError("api_id inválido: deve conter apenas números.")
    if len(api_hash) != 32 or not all(c in "0123456789abcdefABCDEF" for c in api_hash):
        raise ValueError("api_hash inválido: deve ter 32 caracteres hexadecimais.")
    return int(api_id), api_hash


def account_credentials(account: TelegramAccount) -> Tuple[int, str]:
    """Credenciais de uma conta salva (descriptografadas); sem as próprias, usa o .env."""
    if account.encrypted_api_id and account.encrypted_api_hash:
        return int(decrypt_session(account.encrypted_api_id)), decrypt_session(account.encrypted_api_hash)
    if TELEGRAM_API_ID is None or not TELEGRAM_API_HASH:
        raise RuntimeError("Conta sem api_id/api_hash. Reconecte informando as credenciais.")
    return TELEGRAM_API_ID, TELEGRAM_API_HASH


async def _drop_login(token: str):
    data = _PENDING_LOGINS.pop(token, None)
    if data and "client" in data:
        try:
            await data["client"].disconnect()
        except Exception:
            pass


async def _clean_expired_logins():
    """Remove tentativas de login pendentes com mais de 10 minutos."""
    now = time.time()
    for token in [t for t, d in _PENDING_LOGINS.items() if now - d.get("timestamp", 0) > 600]:
        await _drop_login(token)


async def request_login_code(phone: str, api_id: Optional[str] = None, api_hash: Optional[str] = None) -> Dict[str, str]:
    """Inicia o login e envia o código ao Telegram/SMS usando as credenciais desta conta."""
    await _clean_expired_logins()
    cred_id, cred_hash = resolve_credentials(api_id, api_hash)

    phone_clean = phone.strip().replace(" ", "").replace("-", "")
    if not phone_clean.startswith("+"):
        phone_clean = "+" + phone_clean

    client = TelegramClient(StringSession(), cred_id, cred_hash)
    await client.connect()

    try:
        sent_code = await client.send_code_request(phone_clean)
        session_token = str(uuid.uuid4())
        _PENDING_LOGINS[session_token] = {
            "client": client,
            "phone": phone_clean,
            "phone_code_hash": sent_code.phone_code_hash,
            "api_id": cred_id,
            "api_hash": cred_hash,
            "custom_creds": bool(api_id and str(api_id).strip()),
            "timestamp": time.time()
        }
        return {
            "session_token": session_token,
            "phone": phone_clean,
            "message": "Código de verificação enviado com sucesso pelo Telegram/SMS."
        }
    except errors.ApiIdInvalidError:
        await client.disconnect()
        raise ValueError("api_id/api_hash inválidos. Confira em my.telegram.org.")
    except errors.PhoneNumberInvalidError:
        await client.disconnect()
        raise ValueError("Número de telefone inválido. Verifique o código do país e DDD.")
    except errors.FloodWaitError as e:
        await client.disconnect()
        raise ValueError(f"Muitas tentativas recentes. Aguarde {e.seconds} segundos antes de tentar novamente.")
    except Exception as e:
        await client.disconnect()
        raise RuntimeError(f"Erro ao solicitar código: {str(e)}")


async def verify_login_code(session_token: str, code: str, db: Session) -> Dict[str, Any]:
    """Valida o código. Se houver 2FA, pede a senha; senão salva a conta criptografada."""
    await _clean_expired_logins()

    login_data = _PENDING_LOGINS.get(session_token)
    if not login_data:
        raise ValueError("Sessão de login expirada ou inválida. Inicie o login novamente.")

    client: TelegramClient = login_data["client"]
    try:
        await client.sign_in(
            phone=login_data["phone"], code=code.strip(), phone_code_hash=login_data["phone_code_hash"]
        )
    except errors.SessionPasswordNeededError:
        return {
            "status": "2fa_required",
            "message": "Sua conta possui Verificação em Duas Etapas (2FA). Digite sua senha adicional."
        }
    except (errors.PhoneCodeInvalidError, errors.PhoneCodeEmptyError):
        raise ValueError("Código de verificação incorreto. Verifique e tente novamente.")
    except errors.PhoneCodeExpiredError:
        raise ValueError("O código de verificação expirou. Solicite um novo código.")
    except errors.FloodWaitError as e:
        raise ValueError(f"Muitas tentativas incorretas. Aguarde {e.seconds} segundos.")
    except Exception as e:
        raise RuntimeError(f"Erro ao validar código: {str(e)}")

    return await _finalize_account_connection(login_data, db, session_token)


async def verify_2fa_password(session_token: str, password: str, db: Session) -> Dict[str, Any]:
    """Valida a senha 2FA e finaliza o vínculo da conta."""
    await _clean_expired_logins()

    login_data = _PENDING_LOGINS.get(session_token)
    if not login_data:
        raise ValueError("Sessão de login expirada ou inválida. Inicie o login novamente.")

    try:
        await login_data["client"].sign_in(password=password)
    except errors.PasswordHashInvalidError:
        raise ValueError("Senha 2FA incorreta. Tente novamente.")
    except errors.FloodWaitError as e:
        raise ValueError(f"Muitas tentativas incorretas. Aguarde {e.seconds} segundos.")
    except Exception as e:
        raise RuntimeError(f"Erro ao validar senha 2FA: {str(e)}")

    return await _finalize_account_connection(login_data, db, session_token)


async def _finalize_account_connection(login_data: Dict[str, Any], db: Session, session_token: str) -> Dict[str, Any]:
    """Obtém o perfil, criptografa sessão + credenciais e salva (uma linha por telefone)."""
    client: TelegramClient = login_data["client"]
    phone: str = login_data["phone"]
    try:
        me = await client.get_me()
        encrypted_session = encrypt_session(client.session.save())

        # Credenciais próprias só são gravadas quando digitadas; senão usa o .env
        enc_id = encrypt_session(str(login_data["api_id"])) if login_data["custom_creds"] else None
        enc_hash = encrypt_session(login_data["api_hash"]) if login_data["custom_creds"] else None

        account = db.query(TelegramAccount).filter(TelegramAccount.phone == phone).first()
        if not account:
            account = TelegramAccount(phone=phone, encrypted_session=encrypted_session)
            db.add(account)
        account.user_id = me.id
        account.first_name = me.first_name
        account.username = me.username
        account.is_premium = bool(getattr(me, "premium", False))
        account.encrypted_session = encrypted_session
        account.encrypted_api_id = enc_id
        account.encrypted_api_hash = enc_hash
        account.is_active = True
        account.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(account)
        _PENDING_LOGINS.pop(session_token, None)

        # Baixa a foto de perfil da conta logo na conexão
        try:
            avatar_dest = get_avatar_path(account.id)
            await client.download_profile_photo(me, file=str(avatar_dest))
        except Exception:
            pass

        return {
            "status": "connected",
            "message": "Conta do Telegram conectada com sucesso!",
            "id": account.id,
            "phone": account.phone,
            "first_name": account.first_name,
            "username": account.username,
            "is_premium": account.is_premium,
            "avatar_url": f"/api/auth/avatar/{account.id}",
        }
    finally:
        await client.disconnect()


_AVATAR_LOCKS: Dict[int, asyncio.Lock] = {}
_AVATAR_CACHE_TTL_SEC = 12 * 3600  # Atualiza foto a cada 12 horas se necessário


def get_avatar_path(account_id: int) -> Path:
    return AVATARS_DIR / f"account_{account_id}.jpg"


async def fetch_or_get_account_avatar(db: Session, account_id: int) -> Optional[Path]:
    """
    Retorna a foto de perfil da conta salva em cache ou busca direto no Telegram se ainda não existir.
    """
    account = get_account(db, account_id)
    if not account:
        return None

    avatar_path = get_avatar_path(account_id)
    if avatar_path.exists() and avatar_path.stat().st_size > 0:
        age_sec = time.time() - avatar_path.stat().st_mtime
        if age_sec < _AVATAR_CACHE_TTL_SEC:
            return avatar_path

    if not account.encrypted_session:
        return avatar_path if avatar_path.exists() else None

    lock = _AVATAR_LOCKS.setdefault(account_id, asyncio.Lock())
    async with lock:
        if avatar_path.exists() and avatar_path.stat().st_size > 0:
            if (time.time() - avatar_path.stat().st_mtime) < _AVATAR_CACHE_TTL_SEC:
                return avatar_path

        try:
            session_str = decrypt_session(account.encrypted_session)
            if not session_str:
                return None
            cid, chash = account_credentials(account)
            client = TelegramClient(StringSession(session_str), cid, chash)
            await client.connect()
            try:
                if await client.is_user_authorized():
                    downloaded = await client.download_profile_photo("me", file=str(avatar_path))
                    if downloaded and Path(downloaded).exists():
                        return Path(downloaded)
            finally:
                await client.disconnect()
        except Exception:
            if avatar_path.exists() and avatar_path.stat().st_size > 0:
                return avatar_path
            return None

    return avatar_path if avatar_path.exists() and avatar_path.stat().st_size > 0 else None


def list_active_accounts(db: Session) -> List[TelegramAccount]:
    """Todas as contas conectadas."""
    return db.query(TelegramAccount).filter(TelegramAccount.is_active == True).order_by(TelegramAccount.id).all()


def get_account(db: Session, account_id: Optional[int]) -> Optional[TelegramAccount]:
    """Conta ativa por id. Sem id, usa a primeira ativa (compatibilidade)."""
    q = db.query(TelegramAccount).filter(TelegramAccount.is_active == True)
    if account_id is not None:
        q = q.filter(TelegramAccount.id == account_id)
    return q.order_by(TelegramAccount.id).first()


async def disconnect_telegram_account(db: Session, account_id: int) -> bool:
    """Revoga a sessão da conta no Telegram e a desativa localmente."""
    account = get_account(db, account_id)
    if not account:
        return False

    try:
        session_str = decrypt_session(account.encrypted_session)
        if session_str:
            cid, chash = account_credentials(account)
            client = TelegramClient(StringSession(session_str), cid, chash)
            await client.connect()
            if await client.is_user_authorized():
                await client.log_out()
            await client.disconnect()
    except Exception:
        pass

    account.is_active = False
    account.encrypted_session = ""
    account.encrypted_api_id = None
    account.encrypted_api_hash = None
    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    try:
        get_avatar_path(account_id).unlink(missing_ok=True)
    except Exception:
        pass
    return True


async def toggle_story_pinned_on_telegram(db: Session, story: ScheduledStory, pinned: bool) -> bool:
    """Fixa ou remove um story publicado da grade do perfil no Telegram."""
    account = get_account(db, story.account_id)
    if not account or not account.encrypted_session:
        raise RuntimeError("Conta do Telegram não encontrada ou desconectada.")
    if not story.telegram_story_id:
        raise RuntimeError("ID do story no Telegram não encontrado.")

    session_str = decrypt_session(account.encrypted_session)
    cid, chash = account_credentials(account)
    client = TelegramClient(StringSession(session_str), cid, chash)

    await client.connect()
    try:
        await client(TogglePinnedRequest(peer=InputPeerSelf(), id=[story.telegram_story_id], pinned=pinned))
        return True
    finally:
        await client.disconnect()


async def _build_uploaded_video_media(
    client: TelegramClient,
    media_path_obj: Path,
    db: Session,
    story: ScheduledStory,
    force_reencode: bool = False,
) -> InputMediaUploadedDocument:
    """Normaliza (se necessário), extrai thumbnail e envia vídeo para upload no Telegram."""
    meta = await asyncio.to_thread(inspect_video_metadata, media_path_obj)
    needs_normalize = force_reencode or (
        media_path_obj.suffix.lower() != ".mp4"
        or meta["vcodec"] != "h264"
        or not meta["has_audio"]
        or meta["duration"] > 60
        or meta["width"] > 1080
        or meta["height"] > 1920
    )
    if needs_normalize:
        media_path_obj = await asyncio.to_thread(
            prepare_story_video,
            media_path_obj,
            remove_audio=False,
            force_reencode=force_reencode,
        )
        story.media_path = str(media_path_obj)
        db.commit()
        meta = await asyncio.to_thread(inspect_video_metadata, media_path_obj)

    thumb_path: Optional[Path] = None
    try:
        thumb_path = await asyncio.to_thread(extract_video_thumbnail, media_path_obj)
        uploaded_file = await client.upload_file(str(media_path_obj))
        uploaded_thumb = await client.upload_file(str(thumb_path)) if thumb_path else None
    finally:
        if thumb_path and thumb_path.exists():
            thumb_path.unlink(missing_ok=True)

    return InputMediaUploadedDocument(
        file=uploaded_file,
        thumb=uploaded_thumb,
        mime_type="video/mp4",
        attributes=[
            DocumentAttributeVideo(
                duration=float(meta["duration"]),
                w=int(meta["width"]),
                h=int(meta["height"]),
                supports_streaming=True,
            )
        ],
    )


async def publish_story_to_telegram(db: Session, story: ScheduledStory) -> int:
    """Publica o story via MTProto (stories.SendStoryRequest) na conta escolhida no agendamento."""
    account = get_account(db, story.account_id)
    if not account or not account.encrypted_session:
        raise RuntimeError("A conta do Telegram deste agendamento não está conectada. Reconecte-a.")

    session_str = decrypt_session(account.encrypted_session)
    cid, chash = account_credentials(account)
    client = TelegramClient(StringSession(session_str), cid, chash)

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("A sessão do Telegram expirou ou foi revogada. Conecte sua conta novamente.")

        if not os.path.exists(story.media_path):
            raise FileNotFoundError(f"Arquivo de mídia não encontrado: {story.media_path}")

        # Delay aleatório curto antes do upload/envio automático para evitar padrão robótico
        await asyncio.sleep(round(random.uniform(1.3, 3.1) + random.uniform(0.08, 0.42), 3))

        media_path_obj = Path(story.media_path)

        if story.media_type == "photo":
            uploaded_file = await client.upload_file(str(media_path_obj))
            media = InputMediaUploadedPhoto(file=uploaded_file)
        elif story.media_type == "video":
            media = await _build_uploaded_video_media(client, media_path_obj, db, story, force_reencode=False)
        else:
            raise ValueError(f"Tipo de mídia não suportado: {story.media_type}")

        if story.privacy == "contacts":
            privacy_rules = [InputPrivacyValueAllowContacts()]
        elif story.privacy == "close_friends":
            privacy_rules = [InputPrivacyValueAllowCloseFriends()]
        else:
            privacy_rules = [InputPrivacyValueAllowAll()]

        # Suporte a custom emojis / formatação HTML (ex: letras 3D do Telegram Pro)
        caption_text = None
        caption_entities = None
        if story.caption:
            try:
                from telethon.extensions import html
                caption_text, caption_entities = html.parse(story.caption)
            except Exception:
                caption_text = story.caption
                caption_entities = None

        request = SendStoryRequest(
            peer=InputPeerSelf(),
            media=media,
            privacy_rules=privacy_rules,
            pinned=bool(story.pinned),
            caption=caption_text,
            entities=caption_entities if caption_entities else None,
            period=story.period,
            random_id=random.getrandbits(63)
        )

        try:
            updates = await client(request)
        except errors.FloodWaitError as e:
            # Aguarda o tempo exigido pelo Telegram (até 2 min) e tenta uma vez; acima disso, deixa o retry do agendador
            if e.seconds <= 120:
                await asyncio.sleep(e.seconds + 1)
                updates = await client(request)
            else:
                raise RuntimeError(f"Telegram FloodWait: aguarde {e.seconds} segundos antes de tentar novamente.")
        except Exception as e:
            err_str = str(e)
            if "MEDIA_FILE_INVALID" in err_str.upper() and story.media_type == "video":
                # Fallback automático: recodifica estritamente em 720x1280 H.264 keyframe=1s e reenvia
                media = await _build_uploaded_video_media(
                    client, Path(story.media_path), db, story, force_reencode=True
                )
                request = SendStoryRequest(
                    peer=InputPeerSelf(),
                    media=media,
                    privacy_rules=privacy_rules,
                    pinned=bool(story.pinned),
                    caption=caption_text,
                    entities=caption_entities if caption_entities else None,
                    period=story.period,
                    random_id=random.getrandbits(63)
                )
                updates = await client(request)
            elif "PREMIUM" in err_str.upper() or "STORY_PERIOD_INVALID" in err_str:
                raise RuntimeError(
                    "A duração selecionada (48h) ou recurso específico requer uma assinatura Telegram Premium ativa na conta."
                )
            else:
                raise RuntimeError(f"Erro na API do Telegram: {err_str}")

        story_id = None
        if hasattr(updates, "updates"):
            for upd in updates.updates:
                if hasattr(upd, "story") and hasattr(upd.story, "id"):
                    story_id = upd.story.id
                    break

        # pinned=True no envio só salva o story no perfil DEPOIS que ele expira.
        # Para aparecer na grade do perfil imediatamente, fixamos logo após publicar.
        # Falha aqui NÃO pode derrubar o job: o story já foi publicado (retry duplicaria).
        story._grid_warning = None
        if story.pinned:
            if not story_id:
                story._grid_warning = "Story publicado, mas não consegui o ID para colocá-lo na grade do perfil."
            else:
                try:
                    # Delay aleatório curto antes de fixar na grade do perfil
                    await asyncio.sleep(round(random.uniform(1.2, 2.6) + random.uniform(0.07, 0.35), 3))
                    await client(TogglePinnedRequest(peer=InputPeerSelf(), id=[story_id], pinned=True))
                except Exception as e:
                    story._grid_warning = f"Story publicado, mas falhou ao colocá-lo na grade do perfil: {e}"

        return story_id if story_id else int(time.time())

    finally:
        await client.disconnect()
