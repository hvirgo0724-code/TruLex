"""最小冒烟测试：验证 /healthz 正常响应。

不进入 lifespan 上下文，因此不会连接 MySQL/Redis/ES 等外部依赖。
"""

from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "trullex-backend"


def test_openapi() -> None:
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/chat" in paths