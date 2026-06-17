"""
MedMatch - Servico de Agendamento
RF06 - Consulta de horarios disponiveis
RF07 - Agendamento de consulta
RF08 - Cancelamento de consulta
RF09 - Modificacao (reagendamento) de consulta
RF10 - Visualizar agenda (medico)
RF11 - Atualizar status de consulta (medico)
RNF03 - Escalabilidade modular
RNF04 - Auditoria de operacoes
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, date
import mysql.connector
import httpx
import logging
import os

app = FastAPI(title="MedMatch - Scheduling Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
bearer_scheme = HTTPBearer()

# Rate limiting por token (previne flood de agendamentos - DoS)
def get_token_key(request: Request):
    auth = request.headers.get("Authorization", "")
    return auth if auth else get_remote_address(request)

limiter = Limiter(key_func=get_token_key)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Limite de requisicoes atingido."})

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scheduling_service")

# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "scheduling-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_scheduling"),
    )

# ── Auth helpers ──────────────────────────────────────────────────────────────
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return {"usuario_id": int(payload["sub"]), "perfil": payload["perfil"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")

def exigir_medico(usuario: dict = Depends(get_current_user)):
    if usuario["perfil"] not in ("medico", "administrador"):
        raise HTTPException(status_code=403, detail="Acesso restrito a medicos")
    return usuario

# ── Schemas ───────────────────────────────────────────────────────────────────
class AgendarRequest(BaseModel):
    medico_id: int
    horario_id: int

class CriarHorarioRequest(BaseModel):
    data_hora: datetime

class RemarcarRequest(BaseModel):
    novo_horario_id: int

class StatusRequest(BaseModel):
    status: str  # "confirmada" | "concluida" | "falta"

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/horarios/{medico_id}")
def consultar_horarios(medico_id: int, data: Optional[date] = None):
    """RF06 - Consulta horarios disponiveis de um medico"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if data:
        cursor.execute(
            """SELECT h.id, h.data_hora
               FROM horarios h
               WHERE h.medico_id = %s AND DATE(h.data_hora) = %s AND h.disponivel = TRUE
               ORDER BY h.data_hora""",
            (medico_id, data),
        )
    else:
        cursor.execute(
            """SELECT h.id, h.data_hora
               FROM horarios h
               WHERE h.medico_id = %s AND h.disponivel = TRUE AND h.data_hora >= NOW()
               ORDER BY h.data_hora""",
            (medico_id,),
        )
    horarios = cursor.fetchall()
    cursor.close()
    db.close()
    return horarios


@app.post("/consultas", status_code=201)
@limiter.limit("10/minute")  # RF DoS: limitar agendamentos por token
def agendar_consulta(req: AgendarRequest, request: Request, usuario: dict = Depends(get_current_user)):
    """RF07 - Agendamento de consulta"""
    if usuario["perfil"] not in ("paciente", "administrador"):
        raise HTTPException(status_code=403, detail="Somente pacientes podem agendar consultas")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Verificar disponibilidade com lock para evitar conflito de horario (DoS / tampering)
        cursor.execute("SELECT * FROM horarios WHERE id = %s AND disponivel = TRUE FOR UPDATE", (req.horario_id,))
        horario = cursor.fetchone()
        if not horario:
            raise HTTPException(status_code=409, detail="Horario indisponivel ou ja ocupado")
        if horario["medico_id"] != req.medico_id:
            raise HTTPException(status_code=400, detail="Horario nao pertence ao medico informado")

        # Criar consulta
        cursor.execute(
            """INSERT INTO consultas (paciente_id, medico_id, horario_id, status, criado_em)
               VALUES (%s, %s, %s, 'agendada', NOW())""",
            (usuario["usuario_id"], req.medico_id, req.horario_id),
        )
        consulta_id = cursor.lastrowid

        # Marcar horario como indisponivel
        cursor.execute("UPDATE horarios SET disponivel = FALSE WHERE id = %s", (req.horario_id,))
        db.commit()

        logger.info(f"[AUDIT] CONSULTA_AGENDADA id={consulta_id} paciente_id={usuario['usuario_id']} medico_id={req.medico_id}")
        return {"id": consulta_id, "mensagem": "Consulta agendada com sucesso"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao agendar consulta: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao agendar consulta")
    finally:
        cursor.close()
        db.close()


@app.delete("/consultas/{consulta_id}", status_code=200)
def cancelar_consulta(consulta_id: int, usuario: dict = Depends(get_current_user)):
    """RF08 - Cancelamento de consulta"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultas WHERE id = %s", (consulta_id,))
    consulta = cursor.fetchone()

    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta nao encontrada")

    # Validar que quem cancela e o dono ou admin (tampering)
    if usuario["perfil"] != "administrador" and consulta["paciente_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissao para cancelar esta consulta")

    if consulta["status"] in ("concluida", "cancelada"):
        raise HTTPException(status_code=400, detail=f"Consulta ja esta com status '{consulta['status']}'")

    cursor.execute("UPDATE consultas SET status = 'cancelada', atualizado_em = NOW() WHERE id = %s", (consulta_id,))
    cursor.execute("UPDATE horarios SET disponivel = TRUE WHERE id = %s", (consulta["horario_id"],))
    db.commit()

    logger.info(f"[AUDIT] CONSULTA_CANCELADA id={consulta_id} usuario_id={usuario['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": "Consulta cancelada com sucesso"}


@app.put("/consultas/{consulta_id}/remarcar")
def remarcar_consulta(consulta_id: int, req: RemarcarRequest, usuario: dict = Depends(get_current_user)):
    """RF09 - Reagendamento de consulta sem cancelar e criar nova"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultas WHERE id = %s", (consulta_id,))
    consulta = cursor.fetchone()

    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta nao encontrada")

    # Somente o dono pode remarcar (tampering)
    if usuario["perfil"] != "administrador" and consulta["paciente_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissao para remarcar esta consulta")

    if consulta["status"] in ("concluida", "cancelada"):
        raise HTTPException(status_code=400, detail="Consulta nao pode ser remarcada")

    cursor.execute("SELECT * FROM horarios WHERE id = %s AND disponivel = TRUE FOR UPDATE", (req.novo_horario_id,))
    novo_horario = cursor.fetchone()
    if not novo_horario:
        raise HTTPException(status_code=409, detail="Novo horario indisponivel")

    try:
        # Liberar horario antigo e ocupar novo
        cursor.execute("UPDATE horarios SET disponivel = TRUE WHERE id = %s", (consulta["horario_id"],))
        cursor.execute("UPDATE horarios SET disponivel = FALSE WHERE id = %s", (req.novo_horario_id,))
        cursor.execute(
            "UPDATE consultas SET horario_id = %s, atualizado_em = NOW() WHERE id = %s",
            (req.novo_horario_id, consulta_id),
        )
        db.commit()
        logger.info(f"[AUDIT] CONSULTA_REMARCADA id={consulta_id} novo_horario={req.novo_horario_id} usuario_id={usuario['usuario_id']}")
        return {"mensagem": "Consulta remarcada com sucesso"}
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao remarcar: {e}")
        raise HTTPException(status_code=500, detail="Erro ao remarcar consulta")
    finally:
        cursor.close()
        db.close()


def buscar_usuario_auth(usuario_id: int, token: str) -> dict:
    """Busca dados do paciente no auth_service via HTTP"""
    try:
        resp = httpx.get(
            f"{AUTH_SERVICE_URL}/usuarios/{usuario_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Nao foi possivel buscar dados do paciente {usuario_id}: {e}")
    return {"nome": f"Paciente #{usuario_id}", "email": "-", "telefone": "-"}


@app.get("/agenda")
def ver_agenda(request: Request, usuario: dict = Depends(exigir_medico)):
    """RF10 - Medico visualiza sua propria agenda com dados do paciente"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """SELECT c.id, c.paciente_id, h.data_hora, c.status, c.observacoes
           FROM consultas c
           JOIN horarios h ON c.horario_id = h.id
           WHERE c.medico_id = %s AND c.status NOT IN ('cancelada')
           ORDER BY h.data_hora""",
        (usuario["usuario_id"],),
    )
    consultas = cursor.fetchall()
    cursor.close()
    db.close()

    # Busca dados dos pacientes unicos no auth_service
    ids_unicos = list({c["paciente_id"] for c in consultas})
    pacientes = {}
    for pid in ids_unicos:
        pacientes[pid] = buscar_usuario_auth(pid, token)

    # Monta resposta enriquecida
    agenda = []
    for c in consultas:
        p = pacientes.get(c["paciente_id"], {})
        agenda.append({
            "id": c["id"],
            "data_hora": c["data_hora"],
            "status": c["status"],
            "observacoes": c["observacoes"],
            "paciente_nome": p.get("nome", f"Paciente #{c['paciente_id']}"),
            "paciente_email": p.get("email", "-"),
            "paciente_telefone": p.get("telefone", "-"),
        })
    return agenda


@app.patch("/consultas/{consulta_id}/status")
def atualizar_status(consulta_id: int, req: StatusRequest, usuario: dict = Depends(exigir_medico)):
    """RF11 - Medico atualiza status da consulta (confirmada, concluida, falta)"""
    status_validos = {"confirmada", "concluida", "falta"}
    if req.status not in status_validos:
        raise HTTPException(status_code=400, detail=f"Status invalido. Use: {status_validos}")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultas WHERE id = %s", (consulta_id,))
    consulta = cursor.fetchone()

    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta nao encontrada")

    # Medico so altera suas proprias consultas (tampering)
    if usuario["perfil"] == "medico" and consulta["medico_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissao para alterar esta consulta")

    cursor.execute(
        "UPDATE consultas SET status = %s, atualizado_em = NOW() WHERE id = %s",
        (req.status, consulta_id),
    )
    db.commit()
    logger.info(f"[AUDIT] STATUS_ATUALIZADO consulta_id={consulta_id} status={req.status} medico_id={usuario['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": f"Status atualizado para '{req.status}'"}


@app.get("/consultas/minhas")
def minhas_consultas(usuario: dict = Depends(get_current_user)):
    """RF07/RF08 - Paciente visualiza suas proprias consultas"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """SELECT c.id, h.data_hora, c.status, c.medico_id,
                  c.observacoes
           FROM consultas c
           JOIN horarios h ON c.horario_id = h.id
           WHERE c.paciente_id = %s
           ORDER BY h.data_hora DESC""",
        (usuario["usuario_id"],),
    )
    consultas = cursor.fetchall()
    cursor.close()
    db.close()
    return consultas


@app.get("/health")
def health():
    return {"status": "ok", "service": "scheduling"}


@app.post("/horarios", status_code=201)
def criar_horario(req: CriarHorarioRequest, usuario: dict = Depends(exigir_medico)):
    """Medico cadastra seus proprios horarios disponiveis"""
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO horarios (medico_id, data_hora, disponivel) VALUES (%s, %s, TRUE)",
            (usuario["usuario_id"], req.data_hora),
        )
        db.commit()
        horario_id = cursor.lastrowid
        logger.info(f"[AUDIT] HORARIO_CRIADO id={horario_id} medico_id={usuario['usuario_id']}")
        return {"id": horario_id, "data_hora": req.data_hora, "disponivel": True}
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=409, detail="Horario ja cadastrado para este medico neste horario")
    finally:
        cursor.close()
        db.close()


@app.delete("/horarios/{horario_id}", status_code=200)
def remover_horario(horario_id: int, usuario: dict = Depends(exigir_medico)):
    """Medico remove um horario disponivel que ainda nao foi agendado"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM horarios WHERE id = %s", (horario_id,))
    horario = cursor.fetchone()

    if not horario:
        raise HTTPException(status_code=404, detail="Horario nao encontrado")
    if usuario["perfil"] == "medico" and horario["medico_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissao para remover este horario")
    if not horario["disponivel"]:
        raise HTTPException(status_code=400, detail="Horario ja agendado, cancele a consulta antes de remover")

    cursor.execute("DELETE FROM horarios WHERE id = %s", (horario_id,))
    db.commit()
    logger.info(f"[AUDIT] HORARIO_REMOVIDO id={horario_id} medico_id={usuario['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": "Horario removido"}
