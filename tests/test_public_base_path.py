import pytest
from fastapi.testclient import TestClient

import config
import main


client = TestClient(main.app)


def test_public_base_path_defaults_to_empty():
    assert config.public_base_path(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("legal-rag/", "/legal-rag"),
        ("/legal-rag", "/legal-rag"),
        (" /legal-rag/ ", "/legal-rag"),
    ],
)
def test_public_base_path_normalizes_slashes(value, expected):
    assert config.public_base_path(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/legal-rag",
        "/legal-rag?preview=1",
        "/legal-rag#demo",
        "/legal-rag//chat",
    ],
)
def test_public_base_path_rejects_non_path_values(value):
    with pytest.raises(RuntimeError):
        config.public_base_path(value)


def test_index_template_contains_every_base_path_hook():
    html = (config.ENV_FILE.parent / "static" / "index.html").read_text(
        encoding="utf-8"
    )

    assert 'const PUBLIC_BASE_PATH="__PUBLIC_BASE_PATH__"' in html
    assert 'href="__PUBLIC_BASE_PATH__/health"' in html
    assert 'fetch(PUBLIC_BASE_PATH + "/health")' in html
    assert 'fetch(PUBLIC_BASE_PATH + "/chat"' in html


def test_index_renders_branded_routes_from_forwarded_prefix():
    response = client.get("/", headers={"X-Forwarded-Prefix": "/legal-rag"})

    assert response.status_code == 200
    assert 'const PUBLIC_BASE_PATH="/legal-rag"' in response.text
    assert 'href="/legal-rag/health"' in response.text
    assert 'fetch(PUBLIC_BASE_PATH + "/health")' in response.text
    assert 'fetch(PUBLIC_BASE_PATH + "/chat"' in response.text
    assert "__PUBLIC_BASE_PATH__" not in response.text


def test_index_keeps_direct_railway_routes_at_root():
    response = client.get("/")

    assert response.status_code == 200
    assert 'const PUBLIC_BASE_PATH=""' in response.text
    assert 'href="/health"' in response.text
    assert "__PUBLIC_BASE_PATH__" not in response.text
