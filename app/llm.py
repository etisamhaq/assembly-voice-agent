"""LLM access, behind one interface with two backends.

Second Chair needs a language model for two jobs: the tier-2 compliance judge
(structured output, latency-sensitive) and the room agent (short prose). Both
can be served two ways:

  GroqBackend       - Groq Cloud. Fast, generous free tier, and full tool /
                      json_schema support. The default.
  GatewayBackend    - AssemblyAI's LLM Gateway. OpenAI-compatible, and it
                      authenticates with the SAME AssemblyAI key that drives
                      transcription - one key for the whole product, but Claude
                      models there need paid account entitlements.
  AnthropicBackend  - the Anthropic API directly. Native structured outputs
                      and the `effort` latency lever, at the cost of a second
                      credential.

Groq is preferred, then the gateway, then Anthropic.

Structured output is the awkward part, because what the gateway allows depends
on the model AND on the account's entitlements:

  * Claude models there accept `tools` + `tool_choice` but reject
    `response_format` on Opus 5.
  * Haiku 4.5 / Sonnet 4.5-4.6 / Opus 4.5 additionally accept `response_format`.
  * An AssemblyAI account without paid model access can reach only
    `qwen3.5-4b-32k-fast`, which rejects both.
  * Groq's `openai/gpt-oss-*` and `qwen3.8-27b` accept everything; `qwen3.6-27b`
    and `groq/compound` do not.

So `structured()` walks a ladder - forced tool call, then json_schema, then
prompt-coerced JSON - drops a rung whenever the gateway answers "does not
support", and remembers the rung that worked so the probe is paid once per
process rather than once per turn.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger("secondchair.llm")

GATEWAY_URLS = {
    "us": "https://llm-gateway.assemblyai.com/v1",
    "eu": "https://llm-gateway.eu.assemblyai.com/v1",
}

# Free-tier default: the one model reachable without paid gateway access.
# Set SC_GATEWAY_MODEL=claude-opus-5 once the AssemblyAI account has Claude.
DEFAULT_GATEWAY_MODEL = "qwen3.5-4b-32k-fast"

# Groq defaults, chosen by measurement (see check_llm.py): gpt-oss-120b is the
# strongest reasoner for the judge and tier 2 is detached, so ~800ms is fine;
# gpt-oss-20b answers in ~430ms, which matters for speech played into a room.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_ROOM_MODEL = "openai/gpt-oss-20b"

TOOL_CALL, JSON_SCHEMA, PROMPTED = "tool_call", "json_schema", "prompted"
_LADDER = (TOOL_CALL, JSON_SCHEMA, PROMPTED)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any] | None:
    """Recover a JSON object from a reply that may not be pure JSON.

    Prompt-coerced output arrives wrapped in fences, prefaced with prose, or
    trailed by commentary. Tolerate all three rather than discarding a good
    finding over punctuation.
    """
    if not text:
        return None
    body = text.strip()

    for candidate in (m.group(1).strip() for m in _FENCE.finditer(body)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Scan for the first balanced {...}, respecting strings and escapes.
    start = body.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(body)):
            ch = body[i]
            if esc:
                esc = False
                continue
            if ch == "\\" and in_str:
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(body[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = body.find("{", start + 1)
    return None


def _unsupported(exc: Exception) -> bool:
    """Did the provider reject the *mechanism* rather than the request?

    Providers phrase this three different ways, and a model that emits
    malformed tool calls (`tool_use_failed`) is unusable for structuring even
    though the endpoint accepted the request - all four mean "drop a rung".
    """
    msg = str(exc).lower()
    return (
        "does not support" in msg
        or "not supported" in msg
        or "unsupported" in msg
        or "tool_use_failed" in msg
    )


def _rate_limited(exc: Exception) -> bool:
    return "429" in str(exc) or "too many requests" in str(exc).lower()


def _retry_after(exc: Exception, fallback: float) -> float:
    """Honour a Retry-After header when the SDK surfaces one."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    if headers:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            try:
                return max(0.5, min(float(raw), 30.0))
            except (TypeError, ValueError):
                pass
    return fallback


@dataclass
class LLMReply:
    text: str = ""
    refused: bool = False


class LLMBackend(Protocol):
    name: str
    model: str

    @property
    def enabled(self) -> bool: ...

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LLMReply: ...

    async def structured(
        self, *, system: str, user: str, schema: dict[str, Any], tool_name: str, max_tokens: int
    ) -> dict[str, Any] | None: ...


class OpenAICompatBackend:
    """Any OpenAI-shaped chat endpoint: the structuring ladder plus throttling.

    Groq and the AssemblyAI gateway differ only in base URL, credential and
    which structuring mechanisms their models accept - and the ladder discovers
    the last of those at runtime. So they share this implementation.
    """

    name = "openai-compatible"
    base_url = ""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "",
        base_url: str = "",
        timeout_s: float = 20.0,
        strategy: str | None = None,
        max_retries: int = 3,
        min_interval_s: float = 0.0,
        reasoning_effort: str | None = None,
        token_floor: int = 1024,
    ) -> None:
        self.model = model
        self.base_url = base_url or self.base_url
        # Reasoning models (Groq's gpt-oss family) spend max_tokens on hidden
        # reasoning before emitting a single visible character, so a budget
        # sized for the answer alone returns empty content with
        # finish_reason="length". Floor the budget and cap the thinking.
        self.reasoning_effort = reasoning_effort
        self.token_floor = token_floor
        self._supports_reasoning_effort = reasoning_effort is not None
        self.max_retries = max_retries
        # Free tiers rate-limit hard, and Second Chair can burst (a judge call
        # per advisor turn). Serialise and space requests rather than firing
        # them all and eating 429s.
        self.min_interval_s = min_interval_s
        self._gate = asyncio.Lock()
        self._last_call = 0.0
        # None = walk the ladder and learn; a value pins one rung.
        self._strategy: str | None = strategy
        self._client = None
        if api_key:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    base_url=self.base_url, api_key=api_key, timeout=timeout_s, max_retries=0
                )
            except ImportError:  # pragma: no cover
                log.warning("openai SDK not installed; %s backend disabled", self.name)

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def strategy(self) -> str | None:
        """Whichever structuring rung last worked, once one has."""
        return self._strategy

    async def _create(self, **kwargs: Any) -> Any:
        """One call: spaced, serialised, and retried through 429s."""
        assert self._client is not None
        async with self._gate:
            gap = asyncio.get_running_loop().time() - self._last_call
            if gap < self.min_interval_s:
                await asyncio.sleep(self.min_interval_s - gap)

            delay = 2.0
            try:
                for attempt in range(self.max_retries + 1):
                    try:
                        return await self._client.chat.completions.create(**kwargs)
                    except Exception as exc:
                        if _rate_limited(exc) and attempt < self.max_retries:
                            await asyncio.sleep(_retry_after(exc, delay))
                            delay *= 2
                            continue
                        raise
            finally:
                self._last_call = asyncio.get_running_loop().time()

    def _messages(self, system: str, user: str) -> list[dict[str, str]]:
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _params(self, max_tokens: int) -> dict[str, Any]:
        params: dict[str, Any] = {"max_tokens": max(max_tokens, self.token_floor)}
        if self._supports_reasoning_effort and self.reasoning_effort:
            params["reasoning_effort"] = self.reasoning_effort
        return params

    async def _chat(self, *, system: str, user: str, max_tokens: int, **extra: Any) -> Any:
        """One chat call that survives reasoning-model quirks.

        Drops `reasoning_effort` permanently if the model rejects it, and
        retries once at a larger budget if reasoning ate the whole allowance.
        """
        try:
            resp = await self._create(
                model=self.model, messages=self._messages(system, user),
                **self._params(max_tokens), **extra,
            )
        except Exception as exc:
            if self._supports_reasoning_effort and "reasoning_effort" in str(exc).lower():
                log.info("%s does not accept reasoning_effort; dropping it", self.model)
                self._supports_reasoning_effort = False
                resp = await self._create(
                    model=self.model, messages=self._messages(system, user),
                    **self._params(max_tokens), **extra,
                )
            else:
                raise

        choice = resp.choices[0]
        if choice.finish_reason == "length" and not (choice.message.content or ""):
            log.info("%s spent its budget on reasoning; retrying with more room", self.model)
            resp = await self._create(
                model=self.model, messages=self._messages(system, user),
                **{**self._params(max_tokens), "max_tokens": max(max_tokens, self.token_floor) * 4},
                **extra,
            )
        return resp

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LLMReply:
        if not self._client:
            return LLMReply()
        try:
            resp = await self._chat(system=system, user=user, max_tokens=max_tokens)
        except Exception as exc:
            log.warning("%s completion failed (%s): %s", self.name, self.model, exc)
            return LLMReply()
        choice = resp.choices[0]
        if choice.finish_reason == "content_filter":
            return LLMReply(refused=True)
        return LLMReply(text=(choice.message.content or "").strip())

    async def _try_tool_call(self, system, user, schema, tool_name, max_tokens):
        resp = await self._chat(
            system=system, user=user, max_tokens=max_tokens,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": "Report the result. Call exactly once.",
                        "parameters": schema,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        calls = resp.choices[0].message.tool_calls or []
        if not calls:
            return None
        return extract_json(calls[0].function.arguments)

    async def _try_json_schema(self, system, user, schema, tool_name, max_tokens):
        resp = await self._chat(
            system=system, user=user, max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": tool_name, "schema": schema, "strict": True},
            },
        )
        return extract_json(resp.choices[0].message.content or "")

    async def _try_prompted(self, system, user, schema, tool_name, max_tokens):
        coerced = (
            f"{system}\n\n"
            "OUTPUT FORMAT - this is absolute:\n"
            "Reply with a single JSON object and nothing else. No prose before or after, "
            "no code fences, no explanation. It must validate against this JSON Schema:\n"
            f"{json.dumps(schema)}\n"
            "If you have nothing to report, return the object with an empty array."
        )
        resp = await self._chat(system=coerced, user=user, max_tokens=max_tokens)
        return extract_json(resp.choices[0].message.content or "")

    async def structured(
        self, *, system: str, user: str, schema: dict[str, Any], tool_name: str, max_tokens: int
    ) -> dict[str, Any] | None:
        if not self._client:
            return None

        attempts = {
            TOOL_CALL: self._try_tool_call,
            JSON_SCHEMA: self._try_json_schema,
            PROMPTED: self._try_prompted,
        }
        rungs = (self._strategy,) if self._strategy else _LADDER

        for rung in rungs:
            try:
                result = await attempts[rung](system, user, schema, tool_name, max_tokens)
            except Exception as exc:
                if _unsupported(exc) and self._strategy is None:
                    log.info("%s rejects %s; trying the next strategy", self.model, rung)
                    continue
                log.warning("%s structured call failed (%s/%s): %s",
                            self.name, self.model, rung, exc)
                return None
            if result is not None:
                if self._strategy is None:
                    log.info("%s structured output via %s", self.model, rung)
                    self._strategy = rung
                return result
            if self._strategy is not None:
                return None
        return None


class GroqBackend(OpenAICompatBackend):
    """Groq Cloud. Fast, and its gpt-oss / qwen3.8 models support the top rung."""

    name = "groq"
    base_url = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GROQ_MODEL,
        reasoning_effort: str | None = "low",
        **kw,
    ) -> None:
        super().__init__(
            api_key, model=model, base_url=self.base_url,
            reasoning_effort=reasoning_effort, **kw,
        )


class GatewayBackend(OpenAICompatBackend):
    """AssemblyAI LLM Gateway - authenticated by the transcription key."""

    name = "assemblyai-gateway"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_GATEWAY_MODEL,
        region: str = "us",
        min_interval_s: float = 1.5,   # this free tier 429s on bursts
        **kw,
    ) -> None:
        super().__init__(
            api_key,
            model=model,
            base_url=GATEWAY_URLS.get(region, GATEWAY_URLS["us"]),
            min_interval_s=min_interval_s,
            **kw,
        )


class AnthropicBackend:
    """Anthropic API directly - native structured outputs and effort control."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-opus-5",
        effort: str = "low",
        timeout_s: float = 20.0,
    ) -> None:
        self.model = model
        self.effort = effort
        self._client = None
        if api_key:
            try:
                import anthropic

                self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)
            except ImportError:  # pragma: no cover
                log.warning("anthropic SDK not installed; direct backend disabled")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def _system(self, text: str) -> list[dict[str, Any]]:
        # Stable prefix - worth caching across every turn of a call.
        return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]

    async def complete(self, *, system: str, user: str, max_tokens: int) -> LLMReply:
        if not self._client:
            return LLMReply()
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system(system),
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort},
            )
        except Exception as exc:
            log.warning("anthropic completion failed: %s", exc)
            return LLMReply()
        if getattr(resp, "stop_reason", None) == "refusal":
            return LLMReply(refused=True)
        return LLMReply(text=" ".join(b.text for b in resp.content if b.type == "text").strip())

    async def structured(
        self, *, system: str, user: str, schema: dict[str, Any], tool_name: str, max_tokens: int
    ) -> dict[str, Any] | None:
        if not self._client:
            return None
        try:
            resp = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system(system),
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except Exception as exc:
            log.warning("anthropic structured call failed: %s", exc)
            return None
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        block = next((b for b in resp.content if b.type == "text"), None)
        return extract_json(block.text) if block else None


class NullBackend:
    """No credentials. Everything degrades to the deterministic tier."""

    name = "none"
    model = ""

    @property
    def enabled(self) -> bool:
        return False

    async def complete(self, **_: Any) -> LLMReply:
        return LLMReply()

    async def structured(self, **_: Any) -> dict[str, Any] | None:
        return None


def build_backend(
    *,
    groq_key: str = "",
    assemblyai_key: str = "",
    anthropic_key: str = "",
    groq_model: str = DEFAULT_GROQ_MODEL,
    gateway_model: str = DEFAULT_GATEWAY_MODEL,
    model: str = "claude-opus-5",
    prefer: str = "auto",
    region: str = "us",
    effort: str = "low",
) -> LLMBackend:
    """Groq first, then the AssemblyAI gateway, then Anthropic.

    Groq leads because its free tier actually serves capable models with full
    tool support, where the gateway gates every Claude model behind a paid
    account. `prefer` pins one provider instead of walking the order.
    """
    if prefer == "off":
        return NullBackend()

    order: list[tuple[str, Any]] = [
        ("groq", lambda: GroqBackend(groq_key, model=groq_model) if groq_key else None),
        ("gateway", lambda: GatewayBackend(assemblyai_key, model=gateway_model, region=region)
            if assemblyai_key else None),
        ("anthropic", lambda: AnthropicBackend(anthropic_key, model=model, effort=effort)
            if anthropic_key else None),
    ]

    for label, make in order:
        if prefer not in ("auto", label):
            continue
        backend = make()
        if backend is not None and backend.enabled:
            return backend
        if prefer == label:
            return NullBackend()

    return NullBackend()
