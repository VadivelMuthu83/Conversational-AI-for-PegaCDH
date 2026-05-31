"""
Unit and integration tests for the parser and chat API.
"""
import io
import json
import pytest
from fastapi.testclient import TestClient


# ─── Parser Tests ─────────────────────────────────────────────────────────────

def test_csv_parsing():
    from app.parsers.file_parser import FileParser
    csv_content = b"name,age,salary\nAlice,30,75000\nBob,25,60000\n"
    parser = FileParser()
    results = parser.parse_bytes(csv_content, "test.csv")
    assert len(results) == 1
    pf = results[0]
    assert pf.file_type == "csv"
    assert pf.row_count == 2
    assert "name" in pf.columns
    assert len(pf.text_chunks) > 0


def test_json_parsing():
    from app.parsers.file_parser import FileParser
    data = [{"id": 1, "value": "foo"}, {"id": 2, "value": "bar"}]
    content = json.dumps(data).encode()
    parser = FileParser()
    results = parser.parse_bytes(content, "test.json")
    assert len(results) == 1
    pf = results[0]
    assert pf.row_count == 2


def test_text_chunking():
    from app.parsers.file_parser import FileParser
    parser = FileParser(chunk_size=100, chunk_overlap=20)
    text = "x" * 300
    chunks = parser._chunk_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 100


def test_zip_parsing():
    import zipfile
    from app.parsers.file_parser import FileParser

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.csv", "col1,col2\n1,2\n3,4\n")
        zf.writestr("notes.txt", "Some notes here")
    buf.seek(0)

    parser = FileParser()
    results = parser.parse_bytes(buf.read(), "archive.zip")
    assert len(results) == 2
    file_types = {r.file_type for r in results}
    assert "csv" in file_types or "text" in file_types


def test_unsupported_extension():
    from app.parsers.file_parser import FileParser
    parser = FileParser()
    assert not parser.can_parse("binary.exe")
    assert parser.can_parse("data.csv")
    assert parser.can_parse("data.parquet")


# ─── API Tests ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Create test client with mocked index service."""
    from app.main import app
    from unittest.mock import MagicMock, AsyncMock
    
    mock_index = MagicMock()
    mock_index.parsed_files = []
    mock_index.chunks = []
    mock_index.get_file_summary = MagicMock(return_value=[])
    mock_index.search = AsyncMock(return_value=[])
    app.state.index_service = mock_index
    
    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_files_indexed_endpoint(client):
    resp = client.get("/api/files/indexed")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_files" in data
    assert "total_chunks" in data


def test_chat_sync(client):
    resp = client.post("/api/chat", json={
        "message": "What files do we have?",
        "stream": False,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "session_id" in data


def test_chat_empty_message(client):
    resp = client.post("/api/chat", json={
        "message": "",
        "stream": False,
    })
    # Empty message should still return 200 (LLM handles it)
    assert resp.status_code in (200, 422)
