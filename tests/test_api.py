"""HTTP + WebSocket surface."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["rules_loaded"] >= 9
    assert set(body["capabilities"]) == {"live_audio", "llm_judge", "room_agent", "server_tts"}
    # Must describe the backend that is actually wired up.
    assert set(body["llm"]) == {"backend", "judge_model", "room_model"}
    assert body["llm"]["backend"] in {"groq", "assemblyai-gateway", "anthropic", "none"}


def test_rules_endpoint_exposes_the_pack(client):
    body = client.get("/api/rules").json()
    ids = {r["id"] for r in body["rules"]}
    assert {"guaranteed-return", "insider-information", "client-distress"} <= ids
    for r in body["rules"]:
        assert r["patterns"] > 0
        assert r["severity"] in {"critical", "warning", "coach", "info"}


def test_script_endpoint(client):
    body = client.get("/api/script").json()
    assert body["title"]
    assert len(body["script"]["turns"]) == 20


def test_index_serves_the_console(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Second Chair" in r.text


def test_static_assets(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_websocket_session_streams_a_full_call(client):
    """The integration test that matters: a browser gets a complete call."""
    events = []
    with client.websocket_connect("/ws/session?mode=simulated&speed=0") as ws:
        while True:
            ev = json.loads(ws.receive_text())
            events.append(ev)
            if ev["type"] == "audit.ready":
                break

    kinds = [e["type"] for e in events]
    assert kinds[0] == "session.begin"
    assert kinds[-1] == "audit.ready"
    assert kinds.count("turn.processed") == 20
    assert kinds.count("room") == 2
    assert kinds.count("whisper") >= 5
    assert "transcript.partial" in kinds

    end = next(e for e in events if e["type"] == "session.end")
    assert end["violations_by_severity"]["critical"] == 2
    assert end["budget_misses"] == 0

    # Nothing sensitive crossed the wire.
    assert "412-99-8765" not in json.dumps(events)


def test_websocket_reports_capabilities(client):
    with client.websocket_connect("/ws/session?mode=simulated&speed=0") as ws:
        begin = json.loads(ws.receive_text())
    assert begin["type"] == "session.begin"
    assert begin["session_id"]
    assert "llm_judge" in begin["capabilities"]


def test_whisper_precedes_its_turn_on_the_wire(client):
    """The earpiece fires before the transcript renders - that is the promise."""
    events = []
    with client.websocket_connect("/ws/session?mode=simulated&speed=0") as ws:
        while True:
            ev = json.loads(ws.receive_text())
            events.append(ev)
            if ev["type"] == "audit.ready":
                break

    idx_first_whisper = next(i for i, e in enumerate(events) if e["type"] == "whisper")
    # The turn that caused it is emitted after.
    following = next(
        e for e in events[idx_first_whisper:] if e["type"] == "turn.processed" and e["violations"]
    )
    assert following["violations"][0]["rule_id"] == events[idx_first_whisper]["rule_id"]
