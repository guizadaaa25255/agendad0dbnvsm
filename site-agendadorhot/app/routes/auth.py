from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    TwoFactorRequest,
    AccountStatusResponse,
    AccountItem
)
from app.telegram_client import (
    request_login_code,
    verify_login_code,
    verify_2fa_password,
    list_active_accounts,
    disconnect_telegram_account,
    fetch_or_get_account_avatar
)

router = APIRouter(prefix="/api/auth", tags=["Autenticação Telegram"])


@router.get("/status", response_model=AccountStatusResponse)
async def check_status(db: Session = Depends(get_db)):
    """Lista as contas conectadas. Nunca expõe sessão, api_id ou api_hash."""
    accounts = [
        AccountItem(
            id=a.id, phone=a.phone, first_name=a.first_name, username=a.username,
            is_premium=bool(a.is_premium), connected_at=a.connected_at,
            avatar_url=f"/api/auth/avatar/{a.id}?v={int(a.updated_at.timestamp()) if a.updated_at else 1}"
        )
        for a in list_active_accounts(db)
    ]
    return AccountStatusResponse(connected=len(accounts) > 0, accounts=accounts)


@router.get("/avatar/{account_id}")
async def get_account_avatar(account_id: int, db: Session = Depends(get_db)):
    """Retorna a foto de perfil da conta do Telegram (com cache local e fallback automático)."""
    avatar_path = await fetch_or_get_account_avatar(db, account_id)
    if not avatar_path or not avatar_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta sem foto de perfil.")
    return FileResponse(
        str(avatar_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"}
    )


@router.post("/send-code", response_model=SendCodeResponse)
async def send_code(payload: SendCodeRequest):
    """Envia o código de login usando o api_id/api_hash informado (ou o padrão do .env)."""
    try:
        result = await request_login_code(payload.phone, payload.api_id, payload.api_hash)
        return SendCodeResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/verify-code")
async def verify_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Confirma o código recebido no Telegram ou SMS."""
    try:
        return await verify_login_code(payload.session_token, payload.code, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/verify-2fa")
async def verify_2fa(payload: TwoFactorRequest, db: Session = Depends(get_db)):
    """Valida a senha de Verificação em Duas Etapas (2FA)."""
    try:
        return await verify_2fa_password(payload.session_token, payload.password, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/disconnect/{account_id}")
async def disconnect(account_id: int, db: Session = Depends(get_db)):
    """Desconecta uma conta específica."""
    success = await disconnect_telegram_account(db, account_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada.")
    return {"success": True, "message": "Conta desconectada com sucesso."}
