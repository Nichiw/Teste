"""
MedMatch - Serviço de Autenticação
RF01 - Cadastro
RF02 - Autenticação do Usuário
RNF01 - Segurança de autenticação (bcrypt + JWT)
RNF04 - Auditoria de operações
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
import logging
import os

app = FastAPI(title="MedMatch - Auth Service")

# Config
SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auth_service")

# BD
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "credentials-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_credentials"),
    )


class RegisterRequest(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    perfil: str  # "paciente" | "medico" | "administrador"

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: str
    usuario_id: int

# JWT
def criar_token(usuario_id: int, perfil: str) -> str:
    expira = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(usuario_id), "perfil": perfil, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload["sub"])
        perfil = payload["perfil"]
        return {"usuario_id": usuario_id, "perfil": perfil}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")

# Endpoints

@app.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(req: RegisterRequest):
    """RF01 - Cadastro de usuário"""
    perfis_validos = {"paciente", "medico", "administrador"}
    if req.perfil not in perfis_validos:
        raise HTTPException(status_code=400, detail="Perfil inválido")

    hash_senha = pwd_context.hash(req.senha)
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, perfil, criado_em) VALUES (%s, %s, %s, %s, NOW())",
            (req.nome, req.email, hash_senha, req.perfil),
        )
        db.commit()
        usuario_id = cursor.lastrowid
        logger.info(f"[AUDIT] CADASTRO usuario_id={usuario_id} perfil={req.perfil}")
        token = criar_token(usuario_id, req.perfil)
        return TokenResponse(access_token=token, perfil=req.perfil, usuario_id=usuario_id)
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    finally:
        cursor.close()
        db.close()


@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """RF02 - Autenticação do usuário"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (req.email,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()

    if not usuario or not pwd_context.verify(req.senha, usuario["senha_hash"]):
        logger.warning(f"[AUDIT] LOGIN_FALHOU email={req.email}")
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    logger.info(f"[AUDIT] LOGIN usuario_id={usuario['id']} perfil={usuario['perfil']}")
    token = criar_token(usuario["id"], usuario["perfil"])
    return TokenResponse(access_token=token, perfil=usuario["perfil"], usuario_id=usuario["id"])


@app.post("/validate")
def validar_token(usuario: dict = Depends(verificar_token)):
    """Endpoint interno usado pelo API Gateway para validar tokens"""
    return usuario


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}
