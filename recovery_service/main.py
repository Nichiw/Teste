"""
MedMatch - Servico de Recuperacao de Senha
RF03 - Recuperacao de Senha
RNF01 - Tokens temporarios com expiracao
RNF04 - Auditoria de operacoes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
import secrets
import logging
import os

app = FastAPI(title="MedMatch - Password Recovery Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
RESET_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("recovery_service")

# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "credentials-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_credentials"),
    )

# ── Schemas ───────────────────────────────────────────────────────────────────
class SolicitarResetRequest(BaseModel):
    email: EmailStr

class ResetSenhaRequest(BaseModel):
    token: str
    nova_senha: str

class MensagemResponse(BaseModel):
    mensagem: str

# ── Helpers ───────────────────────────────────────────────────────────────────
def gerar_reset_token(usuario_id: int) -> str:
    expira = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "tipo": "reset", "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verificar_reset_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("tipo") != "reset":
            raise ValueError("Tipo de token invalido")
        return int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=400, detail="Token invalido ou expirado")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/solicitar-reset", response_model=MensagemResponse)
def solicitar_reset(req: SolicitarResetRequest):
    """
    RF03 - Solicita recuperacao de senha.
    Gera um token temporario e, em producao, envia por e-mail.
    Responde sempre com sucesso para nao vazar se o e-mail existe.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM usuarios WHERE email = %s", (req.email,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()

    if usuario:
        token = gerar_reset_token(usuario["id"])
        # Em producao: enviar token por e-mail via servico SMTP ou de notificacoes
        # send_email(req.email, token)
        logger.info(f"[AUDIT] RESET_SOLICITADO usuario_id={usuario['id']}")
        # Apenas para desenvolvimento: logar o token
        logger.debug(f"[DEV] reset_token={token}")

    # Resposta generica - nao revela se o e-mail existe (RNF01 / info disclosure)
    return MensagemResponse(mensagem="Se o e-mail estiver cadastrado, voce recebera as instrucoes em breve.")


@app.post("/confirmar-reset", response_model=MensagemResponse)
def confirmar_reset(req: ResetSenhaRequest):
    """RF03 - Confirma o reset com token temporario e define nova senha"""
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
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    logger.info(f"[AUDIT] SENHA_REDEFINIDA usuario_id={usuario_id}")
    return MensagemResponse(mensagem="Senha redefinida com sucesso.")


@app.get("/health")
def health():
    return {"status": "ok", "service": "recovery"}
