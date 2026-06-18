"""
MedMatch - Servico de Medicos e Especialidades
RF04 - Visualizar especialidades medicas
RF05 - Visualizar medicos cadastrados
RF12 - Gerenciamento de medicos (Admin)
RF13 - Gerenciamento de especialidades (Admin)
RNF04 - Auditoria de operacoes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from typing import Optional
import mysql.connector
import logging
import os

app = FastAPI(title="MedMatch - Doctors & Specialties Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
bearer_scheme = HTTPBearer(auto_error=False)

# Rate limiting - RF DoS: listagem e publica, limitar por IP
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Muitas requisicoes. Tente novamente em breve."})

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("doctors_service")

# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "doctors-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_doctors"),
    )

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token necessario")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return {"usuario_id": int(payload["sub"]), "perfil": payload["perfil"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")

def exigir_admin(usuario: dict = Depends(get_current_user)):
    if usuario["perfil"] != "administrador":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return usuario

# ── Schemas ───────────────────────────────────────────────────────────────────
class EspecialidadeCreate(BaseModel):
    nome: str

class EspecialidadeUpdate(BaseModel):
    nome: str

class MedicoCreate(BaseModel):
    nome: str
    email_profissional: EmailStr
    telefone_profissional: Optional[str] = None
    especialidade_id: int
    crm: str
    usuario_id: Optional[int] = None

class MedicoUpdate(BaseModel):
    nome: Optional[str] = None
    email_profissional: Optional[EmailStr] = None
    telefone_profissional: Optional[str] = None
    especialidade_id: Optional[int] = None
    usuario_id: Optional[int] = None

# ── Especialidades ────────────────────────────────────────────────────────────

@app.get("/especialidades")
@limiter.limit("60/minute")
def listar_especialidades(request: Request):
    """RF04 - Listagem publica de especialidades (rate-limited por IP)"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nome FROM especialidades ORDER BY nome")
    especialidades = cursor.fetchall()
    cursor.close()
    db.close()
    return especialidades


@app.post("/especialidades", status_code=201)
def criar_especialidade(req: EspecialidadeCreate, admin: dict = Depends(exigir_admin)):
    """RF13 - Criacao de especialidade (somente Admin)"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO especialidades (nome) VALUES (%s)", (req.nome,))
        db.commit()
        esp_id = cursor.lastrowid
        logger.info(f"[AUDIT] ESPECIALIDADE_CRIADA id={esp_id} admin_id={admin['usuario_id']}")
        return {"id": esp_id, "nome": req.nome}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="Especialidade ja existe")
    finally:
        cursor.close()
        db.close()


@app.put("/especialidades/{esp_id}")
def atualizar_especialidade(esp_id: int, req: EspecialidadeUpdate, admin: dict = Depends(exigir_admin)):
    """RF13 - Atualizacao de especialidade (somente Admin)"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE especialidades SET nome = %s WHERE id = %s", (req.nome, esp_id))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Especialidade nao encontrada")
    logger.info(f"[AUDIT] ESPECIALIDADE_ATUALIZADA id={esp_id} admin_id={admin['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": "Especialidade atualizada"}


@app.delete("/especialidades/{esp_id}", status_code=204)
def remover_especialidade(esp_id: int, admin: dict = Depends(exigir_admin)):
    """RF13 - Remocao de especialidade (somente Admin)"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM especialidades WHERE id = %s", (esp_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Especialidade nao encontrada")
    logger.info(f"[AUDIT] ESPECIALIDADE_REMOVIDA id={esp_id} admin_id={admin['usuario_id']}")
    cursor.close()
    db.close()

# ── Medicos ───────────────────────────────────────────────────────────────────

@app.get("/medicos")
@limiter.limit("60/minute")
def listar_medicos(request: Request, especialidade_id: Optional[int] = None):
    """
    RF05 - Listagem publica de medicos (rate-limited por IP).
    Retorna somente campos publicos - sem dados pessoais sensiveis (info disclosure).
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if especialidade_id:
        cursor.execute(
            """SELECT m.id, m.nome, e.nome AS especialidade, m.email_profissional, m.telefone_profissional
               FROM medicos m JOIN especialidades e ON m.especialidade_id = e.id
               WHERE m.especialidade_id = %s ORDER BY m.nome""",
            (especialidade_id,),
        )
    else:
        cursor.execute(
            """SELECT m.id, m.nome, e.nome AS especialidade, m.email_profissional, m.telefone_profissional
               FROM medicos m JOIN especialidades e ON m.especialidade_id = e.id
               ORDER BY m.nome"""
        )
    medicos = cursor.fetchall()
    cursor.close()
    db.close()
    return medicos


@app.get("/medicos/{medico_id}")
@limiter.limit("60/minute")
def detalhar_medico(medico_id: int, request: Request):
    """RF05 - Detalhe de medico (campos publicos apenas)"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """SELECT m.id, m.nome, e.nome AS especialidade, m.email_profissional, m.telefone_profissional, m.crm
           FROM medicos m JOIN especialidades e ON m.especialidade_id = e.id
           WHERE m.id = %s""",
        (medico_id,),
    )
    medico = cursor.fetchone()
    cursor.close()
    db.close()
    if not medico:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    return medico


@app.post("/medicos/auto-registro", status_code=201)
def auto_registro_medico(req: MedicoCreate):
    """Chamado internamente pelo auth_service quando um medico se registra"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO medicos (usuario_id, nome, email_profissional, telefone_profissional, especialidade_id, crm) VALUES (%s,%s,%s,%s,%s,%s)",
            (req.usuario_id, req.nome, req.email_profissional, req.telefone_profissional, req.especialidade_id, req.crm),
        )
        db.commit()
        medico_id = cursor.lastrowid
        logger.info(f"[AUDIT] MEDICO_AUTO_REGISTRADO id={medico_id} usuario_id={req.usuario_id}")
        return {"id": medico_id, "nome": req.nome}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="CRM ou e-mail ja cadastrado")
    finally:
        cursor.close()
        db.close()


@app.get("/medicos/por-usuario/{usuario_id}")
def medico_por_usuario(usuario_id: int):
    """Retorna o medico_id a partir do usuario_id do credentials-db"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM medicos WHERE usuario_id = %s", (usuario_id,))
    medico = cursor.fetchone()
    cursor.close()
    db.close()
    if not medico:
        raise HTTPException(status_code=404, detail="Medico nao encontrado para este usuario")
    return medico


@app.post("/medicos", status_code=201)
def cadastrar_medico(req: MedicoCreate, admin: dict = Depends(exigir_admin)):
    """RF12 - Cadastro de medico (somente Admin)"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO medicos (nome, email_profissional, telefone_profissional, especialidade_id, crm, usuario_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (req.nome, req.email_profissional, req.telefone_profissional, req.especialidade_id, req.crm, req.usuario_id),
        )
        db.commit()
        medico_id = cursor.lastrowid
        logger.info(f"[AUDIT] MEDICO_CADASTRADO id={medico_id} admin_id={admin['usuario_id']}")
        return {"id": medico_id, "nome": req.nome}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="CRM ou e-mail ja cadastrado")
    finally:
        cursor.close()
        db.close()


@app.put("/medicos/{medico_id}")
def atualizar_medico(medico_id: int, req: MedicoUpdate, admin: dict = Depends(exigir_admin)):
    """RF12 - Atualizacao de medico (somente Admin)"""
    campos = {k: v for k, v in req.dict().items() if v is not None}
    if not campos:
        raise HTTPException(status_code=400, detail="Nenhum campo informado para atualizacao")
    set_clause = ", ".join(f"{k} = %s" for k in campos)
    valores = list(campos.values()) + [medico_id]
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f"UPDATE medicos SET {set_clause} WHERE id = %s", valores)
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    logger.info(f"[AUDIT] MEDICO_ATUALIZADO id={medico_id} admin_id={admin['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": "Medico atualizado"}


@app.delete("/medicos/{medico_id}", status_code=204)
def remover_medico(medico_id: int, admin: dict = Depends(exigir_admin)):
    """RF12 - Remocao de medico (somente Admin)"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM medicos WHERE id = %s", (medico_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Medico nao encontrado")
    logger.info(f"[AUDIT] MEDICO_REMOVIDO id={medico_id} admin_id={admin['usuario_id']}")
    cursor.close()
    db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "doctors"}