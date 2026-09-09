import pytest

from app.models import Role
from app.sources.assemblyai import AssemblyAIStreamingSource
from app.sources.base import RoleResolver
from app.sources.simulated import SimulatedSource


def test_role_resolver_seats_by_speaking_order():
    r = RoleResolver()
    assert r.resolve("SPEAKER_A") is Role.ADVISOR
    assert r.resolve("SPEAKER_B") is Role.CLIENT
    assert r.resolve("SPEAKER_C") is Role.SPOUSE
    assert r.resolve("SPEAKER_A") is Role.ADVISOR      # stable
    assert r.resolve("SPEAKER_D") is Role.UNKNOWN


def test_role_resolver_override():
    r = RoleResolver()
    r.resolve("SPEAKER_A")
    r.override("SPEAKER_A", Role.CLIENT)
    assert r.resolve("SPEAKER_A") is Role.CLIENT


def test_assemblyai_url_requests_diarization():
    s = AssemblyAIStreamingSource("k", max_speakers=3)
    assert s.url.startswith("wss://streaming.assemblyai.com/v3/ws?")
    assert "speaker_labels=true" in s.url
    assert "max_speakers=3" in s.url
    assert "speech_model=universal-3-5-pro" in s.url


def test_assemblyai_requires_a_key():
    with pytest.raises(ValueError):
        AssemblyAIStreamingSource("")


def test_assemblyai_turn_parsing_uses_dominant_word_speaker():
    s = AssemblyAIStreamingSource("k")
    msg = {
        "type": "Turn",
        "turn_order": 4,
        "end_of_turn": True,
        "end_of_turn_confidence": 0.91,
        "transcript": "that sounds high to me",
        "words": [
            {"text": "that", "start": 1000, "end": 1200, "speaker": "SPEAKER_B"},
            {"text": "sounds", "start": 1200, "end": 1500, "speaker": "SPEAKER_B"},
            {"text": "high", "start": 1500, "end": 1800, "speaker": "SPEAKER_C"},
            {"text": "to me", "start": 1800, "end": 2100, "speaker": "SPEAKER_B"},
        ],
    }
    t = s._to_turn(msg)
    assert t.speaker == "SPEAKER_B"       # 3 of 4 words
    assert t.start_ms == 1000 and t.end_ms == 2100
    assert t.end_of_turn and t.turn_order == 4
    assert t.confidence == pytest.approx(0.91)


def test_assemblyai_turn_parsing_without_words():
    s = AssemblyAIStreamingSource("k")
    t = s._to_turn({"type": "Turn", "transcript": "hello", "end_of_turn": False})
    assert t.text == "hello" and not t.end_of_turn
    assert t.speaker == "SPEAKER_A"


async def test_simulated_source_shape():
    src = SimulatedSource(speed=0)
    finals = [t async for t in src.stream() if t.end_of_turn]
    assert len(finals) == 20
    assert {t.role for t in finals} == {Role.ADVISOR, Role.CLIENT, Role.SPOUSE}
    # Turn order is monotonic and timestamps advance.
    assert [t.turn_order for t in finals] == sorted(t.turn_order for t in finals)
    assert finals[-1].received_at_ms > finals[0].received_at_ms


async def test_simulated_source_emits_partials_before_finals():
    src = SimulatedSource(speed=0, emit_partials=True)
    seen: list[tuple[int, bool]] = []
    async for t in src.stream():
        seen.append((t.turn_order, t.end_of_turn))
    for order in {o for o, _ in seen}:
        flags = [f for o, f in seen if o == order]
        assert flags[-1] is True, "final must be last for a turn"
        assert flags.count(True) == 1


async def test_simulated_roles_come_from_the_script():
    src = SimulatedSource(speed=0, emit_partials=False)
    by_role = {}
    async for t in src.stream():
        by_role.setdefault(t.role, []).append(t.speaker)
    assert set(by_role[Role.ADVISOR]) == {"SPEAKER_A"}
    assert set(by_role[Role.CLIENT]) == {"SPEAKER_B"}
    assert set(by_role[Role.SPOUSE]) == {"SPEAKER_C"}
