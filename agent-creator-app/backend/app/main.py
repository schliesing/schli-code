"""
Agent Creator Backend - Main FastAPI Application
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import create_tables
from app.routers import catalog, templates, agents, chat, export, payment


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create DB tables on startup."""
    create_tables()
    yield


app = FastAPI(
    title="Agent Creator API",
    description=(
        "Backend para o Agent Creator App — crie agentes de IA sem precisar programar. "
        "Armazena configurações, serve catálogos, executa agentes via WebSocket "
        "e gera pacotes .tar.gz para download."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Agent-Name"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(catalog.router)
app.include_router(templates.router)
app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(export.router)
app.include_router(payment.router)


# ---------------------------------------------------------------------------
# Health & Root
# ---------------------------------------------------------------------------

@app.get("/", tags=["root"])
def root():
    return {
        "name": "Agent Creator API",
        "version": "0.1.0",
        "status": "online",
        "docs": "/docs",
        "message": "Bem-vindo ao Agent Creator! Acesse /docs para ver a documentação.",
    }


@app.get("/health", tags=["root"])
def health_check():
    return {"status": "healthy", "service": "agent-creator-backend"}
