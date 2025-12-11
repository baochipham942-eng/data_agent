import importlib
import sqlite3
import sys

import pytest


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS conversation (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    started_at TEXT,
    ended_at TEXT,
    source TEXT,
    has_error INTEGER,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS conversation_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    role TEXT,
    content TEXT,
    extra_json TEXT,
    created_at TEXT
);
"""


def _reload_modules(monkeypatch, db_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("LOGS_DB_PATH", str(db_path))

    for mod in ("app.config", "app.services.conversation_log"):
        if mod in sys.modules:
            del sys.modules[mod]

    importlib.import_module("app.config")
    return importlib.import_module("app.services.conversation_log")


@pytest.fixture()
def log_module(tmp_path, monkeypatch):
    db_path = tmp_path / "logs.db"
    module = _reload_modules(monkeypatch, db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript(CREATE_TABLE_SQL)
    conn.commit()
    conn.close()

    return module, db_path


def _fetch_all(conn, query):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    return cur.execute(query).fetchall()


def test_log_conversation_flow(log_module):
    module, db_path = log_module

    conversation_id = "pytest-conv"
    module.log_conversation_start(conversation_id, user_id="pytest-user", source="pytest")
    module.log_message(
        conversation_id,
        "user",
        "问题",
        extra={"foo": "bar"},
    )
    module.log_message(conversation_id, "assistant", "回答")
    module.log_conversation_end(conversation_id, has_error=False, summary="done")

    conn = sqlite3.connect(db_path)
    conversations = _fetch_all(conn, "SELECT * FROM conversation")
    messages = _fetch_all(conn, "SELECT * FROM conversation_message")
    conn.close()

    assert len(conversations) == 1
    conv = conversations[0]
    assert conv["id"] == conversation_id
    assert conv["user_id"] == "pytest-user"
    assert conv["has_error"] == 0
    assert conv["summary"] == "done"

    assert [msg["role"] for msg in messages] == ["user", "assistant"]
    assert messages[0]["extra_json"] == '{"foo": "bar"}'


def test_log_error_marks_conversation(log_module):
    module, db_path = log_module
    conversation_id = "pytest-error"

    module.log_conversation_start(conversation_id, user_id="pytest-user")
    module.log_error(conversation_id, "boom!", extra={"code": 500})

    conn = sqlite3.connect(db_path)
    conversations = _fetch_all(conn, "SELECT * FROM conversation")
    messages = _fetch_all(conn, "SELECT * FROM conversation_message ORDER BY id")
    conn.close()

    assert conversations[0]["has_error"] == 1
    assert messages[-1]["role"] == "system"
    assert "[ERROR] boom!" in messages[-1]["content"]
    assert '"code": 500' in messages[-1]["extra_json"]

