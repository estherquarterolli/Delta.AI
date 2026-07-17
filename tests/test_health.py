"""Testes dos health checks (`/health` e `/health/db`)."""

from httpx import AsyncClient


async def test_health_retorna_ok_com_versao(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.0.1"}


async def test_health_db_sem_database_url_retorna_503(client: AsyncClient) -> None:
    response = await client.get("/health/db")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["db"] == "unreachable"
    assert "DATABASE_URL" in body["detail"]
