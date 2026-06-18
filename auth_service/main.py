"""
MedMatch - Servico de Autenticacao
RF01 - Cadastro
RF02 - Autenticacao do Usuario
RNF01 - Seguranca de autenticacao (bcrypt + JWT)
RNF04 - Auditoria de operacoes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import mysql.connector
import httpx
import logging
import os

app = FastAPI(title="MedMatch - Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuracao ──────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
DOCTORS_SERVICE_URL = os.getenv("DOCTORS_SERVICE_URL", "http://doctors-service:8000")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auth_service")

# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "credentials-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_credentials"),
    )

# ── Schemas ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    perfil: str  # "paciente" | "medico" | "administrador"
    # Campos obrigatorios apenas para perfil medico
    crm: str = ""
    especialidade_id: int = 0
    telefone_profissional: str = ""

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: str
    usuario_id: int

# ── Helpers JWT ───────────────────────────────────────────────────────────────
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(req: RegisterRequest):
    """RF01 - Cadastro de usuario"""
    perfis_validos = {"paciente", "medico", "administrador"}
    if req.perfil not in perfis_validos:
        raise HTTPException(status_code=400, detail="Perfil invalido")

    if req.perfil == "medico":
        if not req.crm:
            raise HTTPException(status_code=400, detail="CRM e obrigatorio para medicos")
        if not req.especialidade_id:
            raise HTTPException(status_code=400, detail="Especialidade e obrigatoria para medicos")

    senha_tratada = req.senha.strip()[:72]
    hash_senha = pwd_context.hash(senha_tratada)
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

        # Se medico, cria registro no doctors_service automaticamente
        if req.perfil == "medico":
            token_temp = criar_token(usuario_id, req.perfil)
            try:
                resp = httpx.post(
                    f"{DOCTORS_SERVICE_URL}/medicos/auto-registro",
                    json={
                        "usuario_id": usuario_id,
                        "nome": req.nome,
                        "email_profissional": req.email,
                        "telefone_profissional": req.telefone_profissional,
                        "especialidade_id": req.especialidade_id,
                        "crm": req.crm,
                    },
                    timeout=5.0,
                )
                if resp.status_code not in (200, 201):
                    raise Exception(resp.text)
            except Exception as e:
                # Desfaz o cadastro se nao conseguir criar o medico
                cursor2 = db.cursor()
                cursor2.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
                db.commit()
                cursor2.close()
                logger.error(f"Erro ao criar medico no doctors_service: {e}")
                raise HTTPException(status_code=500, detail="Erro ao cadastrar medico. Tente novamente.")

        token = criar_token(usuario_id, req.perfil)
        return TokenResponse(access_token=token, perfil=req.perfil, usuario_id=usuario_id)
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="E-mail ja cadastrado")
    finally:
        cursor.close()
        db.close()


@app.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """RF02 - Autenticacao do usuario"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (req.email,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()

    if not usuario or not pwd_context.verify(req.senha.strip()[:72], usuario["senha_hash"]):
        logger.warning(f"[AUDIT] LOGIN_FALHOU email={req.email}")
        raise HTTPException(status_code=401, detail="Credenciais invalidas")

    logger.info(f"[AUDIT] LOGIN usuario_id={usuario['id']} perfil={usuario['perfil']}")
    token = criar_token(usuario["id"], usuario["perfil"])
    return TokenResponse(access_token=token, perfil=usuario["perfil"], usuario_id=usuario["id"])


@app.post("/validate")
def validar_token(usuario: dict = Depends(verificar_token)):
    """Endpoint interno usado pelo API Gateway para validar tokens"""
    return usuario


@app.get("/usuarios/{usuario_id}")
def buscar_usuario(usuario_id: int, atual: dict = Depends(verificar_token)):
    """Endpoint interno — retorna dados publicos de um usuario pelo ID (usado pelo scheduling_service)"""
    # Somente medicos, admins ou o proprio usuario podem consultar
    if atual["perfil"] not in ("medico", "administrador") and atual["usuario_id"] != usuario_id:
        raise HTTPException(status_code=403, detail="Sem permissao")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nome, email FROM usuarios WHERE id = %s", (usuario_id,))
    usuario = cursor.fetchone()
    cursor.close()
    db.close()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return usuario


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}