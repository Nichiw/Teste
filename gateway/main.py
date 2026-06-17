"""
MedMatch - API Gateway
Centraliza entrada de requisicoes, valida tokens e roteia para os microsservicos internos.
Nunca expoe os microsservicos diretamente a internet (spoofing mitigation).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import httpx
import logging
import os

app = FastAPI(title="MedMatch - API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer(auto_error=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("api_gateway")

# ── URLs internas dos microsservicos (rede privada Kubernetes) ────────────────
AUTH_SERVICE_URL       = os.getenv("AUTH_SERVICE_URL",       "http://auth-service:8000")
RECOVERY_SERVICE_URL   = os.getenv("RECOVERY_SERVICE_URL",   "http://recovery-service:8000")
DOCTORS_SERVICE_URL    = os.getenv("DOCTORS_SERVICE_URL",    "http://doctors-service:8000")
SCHEDULING_SERVICE_URL = os.getenv("SCHEDULING_SERVICE_URL", "http://scheduling-service:8000")

ROTAS_PUBLICAS = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("POST", "/recovery/solicitar-reset"),
    ("POST", "/recovery/confirmar-reset"),
    ("GET",  "/doctors/especialidades"),
    ("GET",  "/doctors/medicos"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────
async def validar_token_interno(token: str) -> dict:
    """Valida JWT no servico de autenticacao (unico ponto de validacao)"""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AUTH_SERVICE_URL}/validate",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Token invalido")
            return resp.json()
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Servico de autenticacao indisponivel")


async def proxy(destino: str, request: Request, token: str | None = None) -> JSONResponse:
    """Encaminha a requisicao para o microsservico interno"""
    headers = dict(request.headers)
    headers.pop("host", None)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = await request.body()

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method=request.method,
                url=destino,
                headers=headers,
                content=body,
                params=request.query_params,
                timeout=10.0,
            )
            # Nunca expoe erros tecnicos detalhados ao cliente (info disclosure)
            if resp.status_code >= 500:
                logger.error(f"Erro interno ao rotear para {destino}: {resp.text}")
                return JSONResponse(status_code=502, content={"detail": "Servico temporariamente indisponivel"})
            return JSONResponse(status_code=resp.status_code, content=resp.json())
        except httpx.RequestError as e:
            logger.error(f"Erro de conexao com {destino}: {e}")
            return JSONResponse(status_code=503, content={"detail": "Servico indisponivel"})

# ── Roteador principal ────────────────────────────────────────────────────────

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def gateway(
    path: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    method = request.method
    rota_chave = (method, f"/{path.split('/')[0]}/{'/'.join(path.split('/')[1:2])}" if '/' in path else f"/{path}")

    token = credentials.credentials if credentials else None
    usuario = None

    # Rotas publicas nao precisam de token
    eh_publica = any(
        method == m and f"/{path}".startswith(p)
        for m, p in ROTAS_PUBLICAS
    )

    if not eh_publica:
        if not token:
            raise HTTPException(status_code=401, detail="Autenticacao necessaria")
        usuario = await validar_token_interno(token)
        logger.info(f"[GATEWAY] {method} /{path} usuario_id={usuario['usuario_id']} perfil={usuario['perfil']}")
    else:
        logger.info(f"[GATEWAY] {method} /{path} (publico)")

    # ── Roteamento ─────────────────────────────────────────────────────────────
    segmentos = path.split("/")
    servico = segmentos[0]
    sub_path = "/".join(segmentos[1:])

    if servico == "auth":
        return await proxy(f"{AUTH_SERVICE_URL}/{sub_path}", request, token)
    elif servico == "recovery":
        return await proxy(f"{RECOVERY_SERVICE_URL}/{sub_path}", request, token)
    elif servico == "doctors":
        return await proxy(f"{DOCTORS_SERVICE_URL}/{sub_path}", request, token)
    elif servico == "scheduling":
        return await proxy(f"{SCHEDULING_SERVICE_URL}/{sub_path}", request, token)
    else:
        raise HTTPException(status_code=404, detail="Rota nao encontrada")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}
