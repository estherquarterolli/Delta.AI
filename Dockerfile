# Dockerfile — backend FastAPI (Delta.AI)
#
# Multi-stage build, imagem final mínima e non-root. Usada tanto pelo
# Fly.io em produção (fly.toml aponta pra este Dockerfile) quanto pelo
# docker-compose.yml em desenvolvimento local (CMD sobrescrito com
# --reload no compose).
#
# Contexto de build é a raiz do repo (não app/), pra copiar apenas
# app/requirements.txt e app/ — mantém a imagem enxuta (ver .dockerignore).

# ------------------------------------------------------------------
# Stage 1: builder — instala dependências em /install (isolado),
# incluindo toolchain de compilação (necessária pra libs com
# extensões nativas, ex.: asyncpg, cryptography). Essa camada inteira
# fica pra trás e não vai pra imagem final.
# ------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /code

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt /code/app/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /code/app/requirements.txt

# ------------------------------------------------------------------
# Stage 2: imagem final — só runtime, sem toolchain de build, sem
# root. Copia as dependências já compiladas do stage builder e o
# código da aplicação.
# ------------------------------------------------------------------
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# Usuário non-root com uid/gid fixos (facilita troubleshooting e
# permissões consistentes entre ambientes).
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /usr/sbin/nologin --no-create-home appuser

WORKDIR /code

COPY --from=builder /install /usr/local
COPY app /code/app

RUN chown -R appuser:appuser /code

USER appuser

EXPOSE 8000

# Fly.io usa o healthcheck configurado em fly.toml contra /health.
# Comando de produção (sem --reload); docker-compose.yml sobrescreve
# pra dev com hot reload (monta ./app:/code/app por cima).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
