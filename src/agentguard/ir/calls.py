"""Known-call tables used by adapters to classify external operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias

from agentguard.ir.models import CallSite


class TimeoutMode(str, Enum):
    """How a call determines whether a timeout is configured."""

    REQUIRED = "required"
    DEFAULT = "default"
    CLIENT = "client"


CallKind: TypeAlias = Literal["llm", "http", "tool", "subprocess", "other"]


@dataclass(frozen=True)
class KnownCall:
    """Classification and timeout behavior for a qualified call family."""

    prefix: str
    kind: CallKind
    timeout_mode: TimeoutMode
    client_family: str | None = None


KNOWN_CALLS: tuple[KnownCall, ...] = (
    KnownCall("requests.get", "http", TimeoutMode.REQUIRED),
    KnownCall("requests.post", "http", TimeoutMode.REQUIRED),
    KnownCall("requests.put", "http", TimeoutMode.REQUIRED),
    KnownCall("requests.delete", "http", TimeoutMode.REQUIRED),
    KnownCall("requests.request", "http", TimeoutMode.REQUIRED),
    KnownCall("requests.Session", "http", TimeoutMode.REQUIRED),
    KnownCall("urllib.request.urlopen", "http", TimeoutMode.REQUIRED),
    KnownCall("httpx.get", "http", TimeoutMode.DEFAULT),
    KnownCall("httpx.post", "http", TimeoutMode.DEFAULT),
    KnownCall("httpx.put", "http", TimeoutMode.DEFAULT),
    KnownCall("httpx.delete", "http", TimeoutMode.DEFAULT),
    KnownCall("httpx.request", "http", TimeoutMode.DEFAULT),
    KnownCall("httpx.Client", "http", TimeoutMode.CLIENT, "httpx"),
    KnownCall("httpx.AsyncClient", "http", TimeoutMode.CLIENT, "httpx"),
    KnownCall("aiohttp.ClientSession", "http", TimeoutMode.CLIENT, "aiohttp"),
    KnownCall("openai.OpenAI", "llm", TimeoutMode.CLIENT, "openai"),
    KnownCall("openai.AsyncOpenAI", "llm", TimeoutMode.CLIENT, "openai"),
    KnownCall("anthropic.Anthropic", "llm", TimeoutMode.CLIENT, "anthropic"),
    KnownCall("anthropic.AsyncAnthropic", "llm", TimeoutMode.CLIENT, "anthropic"),
    KnownCall("langchain_openai.ChatOpenAI", "llm", TimeoutMode.CLIENT, "langchain"),
    KnownCall(
        "langchain_anthropic.ChatAnthropic", "llm", TimeoutMode.CLIENT, "langchain"
    ),
    KnownCall("openai", "llm", TimeoutMode.CLIENT, "openai"),
    KnownCall("anthropic", "llm", TimeoutMode.CLIENT, "anthropic"),
)


def lookup_known_call(qualified_name: str) -> KnownCall | None:
    """Return the most specific known-call entry for a qualified name."""
    matches = [
        known
        for known in KNOWN_CALLS
        if qualified_name == known.prefix
        or qualified_name.startswith(f"{known.prefix}.")
    ]
    return max(matches, key=lambda known: len(known.prefix), default=None)


def classify_call(site: CallSite) -> KnownCall | None:
    """Look up the call represented by a call site."""
    return lookup_known_call(site.qualified_name)
