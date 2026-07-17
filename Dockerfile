# Dockerfile — backend FastAPI (Delta.AI)
#
# Imagem mínima Python 3.12 slim. Usada tanto pelo Fly.io em produção
# (fly.toml aponta pra este Dockerfile) quanto pelo docker-compose.yml
# em desenvolvimento local (com --reload sobrescrito no compose).
#
# Contexto de build é a raiz do repo (não app/), pra copiar apenas
# app/requirements.txt e app/ — mantém a imagem enxuta.

FROM python:3.12-slim

WORKDIR /code

COPY app/requirements.txt /code/app/requirements.txt
RUN pip install --no-cache-dir -r /code/app/requirements.txt

COPY app /code/app

EXPOSE 8000

# Fly.io usa o healthcheck configurado em fly.toml contra /health.
# Comando de produção (sem --reload); docker-compose.yml sobrescreve
# pra dev com hot reload.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
