"""
MedMatch - Serviço de Agendamento
RF06 - Consulta de horários disponíveis
RF07 - Agendamento de consulta
RF08 - Cancelamento de consulta
RF09 - Modificação (reagendamento) de consulta
RF10 - Visualizar agenda (médico)
RF11 - Atualizar status de consulta (médico)
RNF03 - Escalabilidade modular
RNF04 - Auditoria de operações
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
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
import logging
import os

app = FastAPI(title="MedMatch - Scheduling Service")

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
bearer_scheme = HTTPBearer()

# Rate limiting
def get_token_key(request: Request):
    auth = request.headers.get("Authorization", "")
    return auth if auth else get_remote_address(request)

limiter = Limiter(key_func=get_token_key)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Limite de requisições atingido."})

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scheduling_service")

# BD
def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "scheduling-db"),
        user=os.getenv("DB_USER", "medmatch"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "medmatch_scheduling"),
    )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return {"usuario_id": int(payload["sub"]), "perfil": payload["perfil"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

def exigir_medico(usuario: dict = Depends(get_current_user)):
    if usuario["perfil"] not in ("medico", "administrador"):
        raise HTTPException(status_code=403, detail="Acesso restrito a médicos")
    return usuario


class AgendarRequest(BaseModel):
    medico_id: int
    horario_id: int  # ID do slot de horário disponível

class RemarcarRequest(BaseModel):
    novo_horario_id: int

class StatusRequest(BaseModel):
    status: str  # "confirmada" | "concluida" | "falta"

# Endpoints

@app.get("/horarios/{medico_id}")
def consultar_horarios(medico_id: int, data: Optional[date] = None):
    """RF06 - Consulta horários disponíveis de um médico"""
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
        # Verificar disponibilidade com lock para evitar conflito de horário (DoS / tampering)
        cursor.execute("SELECT * FROM horarios WHERE id = %s AND disponivel = TRUE FOR UPDATE", (req.horario_id,))
        horario = cursor.fetchone()
        if not horario:
            raise HTTPException(status_code=409, detail="Horário indisponível ou já ocupado")
        if horario["medico_id"] != req.medico_id:
            raise HTTPException(status_code=400, detail="Horário não pertence ao médico informado")

        # Criar consulta
        cursor.execute(
            """INSERT INTO consultas (paciente_id, medico_id, horario_id, status, criado_em)
               VALUES (%s, %s, %s, 'agendada', NOW())""",
            (usuario["usuario_id"], req.medico_id, req.horario_id),
        )
        consulta_id = cursor.lastrowid

        # Marcar horário como indisponível
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
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    # Validar que quem cancela é o dono ou admin (tampering)
    if usuario["perfil"] != "administrador" and consulta["paciente_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para cancelar esta consulta")

    if consulta["status"] in ("concluida", "cancelada"):
        raise HTTPException(status_code=400, detail=f"Consulta já está com status '{consulta['status']}'")

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
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    # Somente o dono pode remarcar (tampering)
    if usuario["perfil"] != "administrador" and consulta["paciente_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para remarcar esta consulta")

    if consulta["status"] in ("concluida", "cancelada"):
        raise HTTPException(status_code=400, detail="Consulta não pode ser remarcada")

    cursor.execute("SELECT * FROM horarios WHERE id = %s AND disponivel = TRUE FOR UPDATE", (req.novo_horario_id,))
    novo_horario = cursor.fetchone()
    if not novo_horario:
        raise HTTPException(status_code=409, detail="Novo horário indisponível")

    try:
        # Liberar horário antigo e ocupar novo
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


@app.get("/agenda")
def ver_agenda(usuario: dict = Depends(exigir_medico)):
    """RF10 - Médico visualiza sua própria agenda com dados do paciente"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        """SELECT c.id, h.data_hora, c.status,
                  p.nome AS paciente_nome, p.email AS paciente_email, p.telefone AS paciente_telefone,
                  c.observacoes
           FROM consultas c
           JOIN horarios h ON c.horario_id = h.id
           JOIN pacientes_view p ON c.paciente_id = p.id
           WHERE c.medico_id = %s AND c.status NOT IN ('cancelada')
           ORDER BY h.data_hora""",
        (usuario["usuario_id"],),
    )
    agenda = cursor.fetchall()
    cursor.close()
    db.close()
    return agenda


@app.patch("/consultas/{consulta_id}/status")
def atualizar_status(consulta_id: int, req: StatusRequest, usuario: dict = Depends(exigir_medico)):
    """RF11 - Médico atualiza status da consulta (confirmada, concluida, falta)"""
    status_validos = {"confirmada", "concluida", "falta"}
    if req.status not in status_validos:
        raise HTTPException(status_code=400, detail=f"Status inválido. Use: {status_validos}")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM consultas WHERE id = %s", (consulta_id,))
    consulta = cursor.fetchone()

    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    # Médico só altera suas próprias consultas (tampering)
    if usuario["perfil"] == "medico" and consulta["medico_id"] != usuario["usuario_id"]:
        raise HTTPException(status_code=403, detail="Sem permissão para alterar esta consulta")

    cursor.execute(
        "UPDATE consultas SET status = %s, atualizado_em = NOW() WHERE id = %s",
        (req.status, consulta_id),
    )
    db.commit()
    logger.info(f"[AUDIT] STATUS_ATUALIZADO consulta_id={consulta_id} status={req.status} medico_id={usuario['usuario_id']}")
    cursor.close()
    db.close()
    return {"mensagem": f"Status atualizado para '{req.status}'"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "scheduling"}
