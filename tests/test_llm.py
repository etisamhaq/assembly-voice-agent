"""Backend selection, the structuring ladder, and tolerant JSON recovery."""
import json
from types import SimpleNamespace

import pytest

from app.llm import (
    JSON_SCHEMA,
    PROMPTED,
    TOOL_CALL,
    AnthropicBackend,
    GatewayBackend,
    NullBackend,
    build_backend,
    extract_json,
)

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


# ------------------------------------------------------------- extract_json

@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"ok": true}', {"ok": True}),
        ('```json\n{"ok": true}\n```', {"ok": True}),
        ("```\n{\"ok\": false}\n```", {"ok": False}),
        ('Here you go:\n{"ok": true}\nHope that helps.', {"ok": True}),
        ('{"a": {"b": "brace } inside string"}}', {"a": {"b": "brace } inside string"}}),
        ('{"a": "quote \\" escaped"}', {"a": 'quote " escaped'}),
        ("no json at all", None),
        ("", None),
        ("[1,2,3]", None),          # arrays are not objects
        ("{broken", None),
    ],
)
def test_extract_json(raw, expected):
    assert extract_json(raw) == expected


def test_extract_json_prefers_first_valid_object():
    assert extract_json('junk {"first": 1} then {"second": 2}') == {"first": 1}


# ------------------------------------------------------------ fake gateway

class FakeCompletions:
    """Mimics the gateway: rejects whichever mechanisms the model lacks."""

    def __init__(self, *, supports_tools=False, supports_schema=False, content='{"ok": true}',
                 rate_limit_first=0):
        self.supports_tools = supports_tools
        self.supports_schema = supports_schema
        self.content = content
        self.rate_limit_first = rate_limit_first
        self.calls = []

    async def create(self, **kw):
        self.calls.append(kw)
        if self.rate_limit_first > 0:
            self.rate_limit_first -= 1
            raise RuntimeError("Error code: 429 - too many requests for this action")
        if "tools" in kw and not self.supports_tools:
            raise RuntimeError("Error code: 400 - model does not support tools")
        if "response_format" in kw and not self.supports_schema:
            raise RuntimeError("Error code: 400 - model does not support response_format")
        if "tools" in kw:
            call = SimpleNamespace(function=SimpleNamespace(arguments=self.content))
            msg = SimpleNamespace(content=None, tool_calls=[call])
        else:
            msg = SimpleNamespace(content=self.content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])


def gateway(min_interval_s=0.0, max_retries=3, **kw):
    # Spacing and backoff are real sleeps; switch them off unless under test.
    g = GatewayBackend("", min_interval_s=min_interval_s, max_retries=max_retries)
    g._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(**kw)))
    return g, g._client.chat.completions


async def test_ladder_uses_tool_call_when_supported():
    g, fake = gateway(supports_tools=True)
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="report", max_tokens=100) == {"ok": True}
    assert g.strategy == TOOL_CALL
    assert len(fake.calls) == 1


async def test_ladder_falls_back_to_json_schema():
    g, fake = gateway(supports_tools=False, supports_schema=True)
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="report", max_tokens=100) == {"ok": True}
    assert g.strategy == JSON_SCHEMA
    assert len(fake.calls) == 2                 # tool attempt, then schema


async def test_ladder_falls_back_to_prompting():
    """The free-tier path: neither tools nor response_format are available."""
    g, fake = gateway(supports_tools=False, supports_schema=False)
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="report", max_tokens=100) == {"ok": True}
    assert g.strategy == PROMPTED
    assert len(fake.calls) == 3
    # The prompted rung must inject the schema into the system message.
    assert "JSON Schema" in fake.calls[-1]["messages"][0]["content"]


async def test_ladder_is_learned_once_not_per_turn():
    g, fake = gateway(supports_tools=False, supports_schema=False)
    for _ in range(3):
        await g.structured(system="s", user="u", schema=SCHEMA, tool_name="r", max_tokens=100)
    # 3 probing calls on the first turn, then 1 per turn after.
    assert len(fake.calls) == 3 + 2


async def test_prompted_rung_recovers_messy_output():
    g, _ = gateway(content='Sure!\n```json\n{"violations": []}\n```')
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="r", max_tokens=100) == {"violations": []}


async def test_rate_limit_is_retried():
    g, fake = gateway(supports_tools=True, rate_limit_first=1)
    g._client.chat.completions.rate_limit_first = 1
    import time
    t0 = time.perf_counter()
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="r", max_tokens=100) == {"ok": True}
    assert len(fake.calls) == 2
    assert time.perf_counter() - t0 >= 2.0, "backoff must actually wait"


async def test_rate_limit_gives_up_after_max_retries():
    g, fake = gateway(max_retries=1, supports_tools=True, rate_limit_first=99)
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="r", max_tokens=100) is None
    assert len(fake.calls) == 2                 # initial + one retry


async def test_requests_are_spaced_to_respect_the_free_tier():
    """The gateway 429s on bursts, so calls are serialised and spaced."""
    import time
    g, fake = gateway(min_interval_s=0.25, supports_tools=True)
    t0 = time.perf_counter()
    for _ in range(3):
        await g.structured(system="s", user="u", schema=SCHEMA, tool_name="r", max_tokens=100)
    elapsed = time.perf_counter() - t0
    assert len(fake.calls) == 3
    assert elapsed >= 0.5, f"3 calls at 0.25s spacing took only {elapsed:.2f}s"


async def test_complete_returns_text():
    g, _ = gateway(content="two sentences, spoken aloud.")
    reply = await g.complete(system="s", user="u", max_tokens=100)
    assert reply.text == "two sentences, spoken aloud."
    assert not reply.refused


async def test_unparseable_structured_output_is_not_fatal():
    g, _ = gateway(supports_tools=True, content="I refuse to emit JSON")
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="r", max_tokens=100) is None


# ---------------------------------------------------------- backend routing

def test_assemblyai_key_is_preferred():
    b = build_backend(assemblyai_key="aai", anthropic_key="ant")
    assert b.name == "assemblyai-gateway"


def test_gateway_uses_the_gateway_model_not_the_anthropic_one():
    b = build_backend(assemblyai_key="aai", model="claude-opus-5",
                      gateway_model="qwen3.5-4b-32k-fast")
    assert b.model == "qwen3.5-4b-32k-fast"


def test_anthropic_used_when_it_is_the_only_key():
    b = build_backend(anthropic_key="ant", model="claude-opus-5")
    assert b.name == "anthropic"
    assert b.model == "claude-opus-5"


def test_explicit_preference_is_honoured():
    assert build_backend(assemblyai_key="aai", anthropic_key="ant",
                         prefer="anthropic").name == "anthropic"
    assert build_backend(assemblyai_key="aai", anthropic_key="ant",
                         prefer="gateway").name == "assemblyai-gateway"


def test_no_keys_or_off_gives_a_disabled_backend():
    assert isinstance(build_backend(), NullBackend)
    assert isinstance(build_backend(assemblyai_key="aai", prefer="off"), NullBackend)
    assert build_backend().enabled is False


def test_eu_region_endpoint():
    b = build_backend(assemblyai_key="aai", region="eu")
    assert b.base_url == "https://llm-gateway.eu.assemblyai.com/v1"


# ------------------------------------------------ reasoning-model behaviour

class ReasoningCompletions(FakeCompletions):
    """Mimics gpt-oss: reasoning eats max_tokens before any visible content."""

    def __init__(self, *, need_tokens=1024, rejects_effort=False, **kw):
        super().__init__(**kw)
        self.need_tokens = need_tokens
        self.rejects_effort = rejects_effort

    async def create(self, **kw):
        if self.rejects_effort and "reasoning_effort" in kw:
            self.calls.append(kw)
            raise RuntimeError("Error code: 400 - unknown parameter reasoning_effort")
        if kw.get("max_tokens", 0) < self.need_tokens:
            self.calls.append(kw)
            msg = SimpleNamespace(content="", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="length")])
        return await super().create(**kw)


def reasoning_gateway(**kw):
    g = GatewayBackend("", min_interval_s=0.0, reasoning_effort="low", token_floor=256)
    g._client = SimpleNamespace(chat=SimpleNamespace(completions=ReasoningCompletions(**kw)))
    return g, g._client.chat.completions


async def test_token_floor_is_applied():
    g, fake = reasoning_gateway(need_tokens=200)
    await g.complete(system="s", user="u", max_tokens=16)
    assert fake.calls[0]["max_tokens"] == 256, "small budget must be floored"


async def test_budget_eaten_by_reasoning_triggers_a_larger_retry():
    g, fake = reasoning_gateway(need_tokens=900, content="ok")
    reply = await g.complete(system="s", user="u", max_tokens=100)
    assert reply.text == "ok"
    assert len(fake.calls) == 2
    assert fake.calls[1]["max_tokens"] > fake.calls[0]["max_tokens"]


async def test_reasoning_effort_is_sent_then_dropped_if_rejected():
    g, fake = reasoning_gateway(rejects_effort=True, content="ok")
    assert "ok" == (await g.complete(system="s", user="u", max_tokens=2000)).text
    assert "reasoning_effort" in fake.calls[0]
    assert "reasoning_effort" not in fake.calls[-1]
    # And it stays dropped on subsequent calls.
    await g.complete(system="s", user="u", max_tokens=2000)
    assert "reasoning_effort" not in fake.calls[-1]


async def test_groq_defaults_to_low_reasoning_effort():
    from app.llm import GroqBackend
    assert GroqBackend("k").reasoning_effort == "low"
    assert GroqBackend("k").base_url == "https://api.groq.com/openai/v1"


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 400 - model does not support tools",
        "Error code: 400 - `tool calling` is not supported with this model",
        "Error code: 400 - unsupported parameter",
        "Error code: 400 - tool_use_failed: parameters did not match schema",
    ],
)
async def test_every_capability_failure_phrasing_drops_a_rung(message):
    """Providers word this four different ways; all must fall through."""
    class Rejects(FakeCompletions):
        async def create(self, **kw):
            self.calls.append(kw)
            if "tools" in kw:
                raise RuntimeError(message)
            if "response_format" in kw:
                raise RuntimeError("does not support response_format")
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content='{"ok": true}', tool_calls=None),
                finish_reason="stop")])

    g = GatewayBackend("", min_interval_s=0.0)
    g._client = SimpleNamespace(chat=SimpleNamespace(completions=Rejects()))
    assert await g.structured(system="s", user="u", schema=SCHEMA,
                              tool_name="r", max_tokens=100) == {"ok": True}
    assert g.strategy == PROMPTED
