"""Dataclasses for the normalized AgentGuard intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, TypeAlias

from agentguard.findings import Location

LiteralValue: TypeAlias = str | int | float | bool | None


class Capability(str, Enum):
    """A capability that a tool or agent operation can exercise."""

    SHELL = "shell"
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    FS_DELETE = "fs_delete"
    NETWORK = "network"
    SQL = "sql"
    EVAL = "eval"
    EMAIL = "email"
    PAYMENT = "payment"


class DataSource(str, Enum):
    """The best-known origin of a value flowing through an agent."""

    LITERAL = "literal"
    USER_INPUT = "user_input"
    TOOL_OUTPUT = "tool_output"
    LLM_OUTPUT = "llm_output"
    ENV = "env"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class KwargInfo:
    """Information about a keyword argument observed at a call site."""

    value: LiteralValue
    is_literal: bool


@dataclass
class CallSite:
    """A call that may affect reliability, cost, or security."""

    loc: Location
    kind: Literal["llm", "http", "tool", "subprocess", "other"]
    qualified_name: str
    kwargs: dict[str, KwargInfo]
    has_timeout: bool | None
    enclosing_function: str | None
    in_loop: bool


@dataclass
class Loop:
    """A loop or retry construct represented in the agent IR."""

    loc: Location
    kind: Literal[
        "while",
        "for",
        "retry_decorator",
        "retry_call",
        "recursion",
        "graph_cycle",
    ]
    has_bound: bool | None
    bound_value: int | None
    bounded_by: str | None
    has_backoff: bool | None
    calls_inside: list[CallSite]
    catches_exceptions: bool


@dataclass
class StateKey:
    """A state field and the reducer/type information known about it."""

    name: str
    has_reducer: bool
    mutable_type: bool


@dataclass
class AgentNode:
    """A node in a framework-neutral agent graph."""

    name: str
    framework: str
    loc: Location
    function_ref: str | None
    reads_state: set[str]
    writes_state: set[str]
    call_sites: list[CallSite]
    tools: list[ToolDef]


@dataclass
class ToolDef:
    """A tool exposed to an agent and its known safety properties."""

    name: str
    loc: Location
    capabilities: set[Capability]
    requires_approval: bool
    is_idempotent: bool | None


@dataclass
class Edge:
    """A directed graph edge, including unresolved conditional edges."""

    source: str
    target: str | None
    conditional: bool
    loc: Location


@dataclass
class FanOut:
    """A graph or concurrency construct that executes multiple branches."""

    source: str
    branches: list[str]
    loc: Location
    mechanism: Literal[
        "multiple_edges",
        "send_api",
        "thread_pool",
        "asyncio_gather",
        "crewai_async",
    ]


@dataclass
class AgentGraph:
    """A normalized agent graph with nodes, edges, and state metadata."""

    name: str
    framework: str
    nodes: dict[str, AgentNode]
    edges: list[Edge]
    entry: str | None
    terminals: set[str]
    state_keys: dict[str, StateKey]
    recursion_limit: int | None
    fan_outs: list[FanOut]
    loc: Location


@dataclass
class ModuleFacts:
    """Facts extracted from one source module by an adapter."""

    path: Path
    call_sites: list[CallSite]
    loops: list[Loop]
    graphs: list[AgentGraph]
    module_mutables: dict[str, Location]
    imports: dict[str, str]


@dataclass
class AgentSystem:
    """All normalized module facts from one scan."""

    modules: list[ModuleFacts]
