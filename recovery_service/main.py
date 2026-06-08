"""
MedMatch - Serviço de Recuperação de Senha
RF03 - Recuperação de Senha
RNF01 - Tokens temporários com expiração
RNF04 - Auditoria de operações
"""

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
import secrets
import logging
import os

app = FastAPI(title="MedMatch - Password Recovery Service")

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
RESET_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("recovery_service")

# BD
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "credentials-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_credentials"),
    )


class SolicitarResetRequest(BaseModel):
    email: EmailStr

class ResetSenhaRequest(BaseModel):
    token: str
    nova_senha: str

class MensagemResponse(BaseModel):
    mensagem: str


def gerar_reset_token(usuario_id: int) -> str:
    expira = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "tipo": "reset", "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verificar_reset_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("tipo") != "reset":
            raise ValueError("Tipo de token inválido")
        return int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")

# Endpoints

@app.post("/solicitar-reset", response_model=MensagemResponse)
def solicitar_reset(req: SolicitarResetRequest):
    """
    RF03 - Solicita recuperação de senha.
    Gera um token temporário e, em produção, envia por e-mail.
    Responde sempre com sucesso para não vazar se o e-mail existe.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM usuarios WHERE email = %s", (req.email,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()

    if usuario:
        token = gerar_reset_token(usuario["id"])
        # Em produção: enviar token por e-mail via serviço SMTP ou de notificações
        # send_email(req.email, token)
        logger.info(f"[AUDIT] RESET_SOLICITADO usuario_id={usuario['id']}")
        # logar o token
        logger.debug(f"[DEV] reset_token={token}")

    # Resposta genérica
    return MensagemResponse(mensagem="Se o e-mail estiver cadastrado, você receberá as instruções em breve.")


@app.post("/confirmar-reset", response_model=MensagemResponse)
def confirmar_reset(req: ResetSenhaRequest):
    """RF03 - Confirma o reset com token temporário e define nova senha"""
    if len(req.nova_senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 8 caracteres")

    usuario_id = verificar_reset_token(req.token)
    nova_hash = pwd_context.hash(req.nova_senha)

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "UPDATE usuarios SET senha_hash = %s, atualizado_em = NOW() WHERE id = %s",
        (nova_hash, usuario_id),
    )
    db.commit()
    rows = cursor.rowcount
    cursor.close()
    db.close()

    if rows == 0:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    logger.info(f"[AUDIT] SENHA_REDEFINIDA usuario_id={usuario_id}")
    return MensagemResponse(mensagem="Senha redefinida com sucesso.")


@app.get("/health")
def health():
    return {"status": "ok", "service": "recovery"}
