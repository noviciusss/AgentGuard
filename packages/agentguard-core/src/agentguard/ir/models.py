"""Dataclasses for the normalized AgentGuard intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field
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


class TaintSink(str, Enum):
    """A destination where untrusted or generated data needs review."""

    SYSTEM_PROMPT = "system_prompt"
    EVAL = "eval"
    EXEC = "exec"
    SUBPROCESS = "subprocess"
    SQL = "sql"
    FILE_PATH = "file_path"


@dataclass(frozen=True)
class TaintFlow:
    """A conservative intra-function source-to-sink dataflow fact."""

    loc: Location
    source: DataSource
    sink: TaintSink
    function: str | None
    value_name: str | None


@dataclass(frozen=True)
class SecretFact:
    """A likely hardcoded credential detected in source."""

    loc: Location
    name: str
    kind: str


@dataclass(frozen=True)
class ExceptionFact:
    """An exception handler that may hide a tool failure."""

    loc: Location
    function: str | None
    catches: str | None
    has_raise: bool
    has_logging: bool
    has_fallback: bool


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
    model_name: str | None = None
    max_tokens: int | None = None
    data_sources: frozenset[DataSource] = frozenset()
    approval_gate: bool = False


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
    mutable_default_args: set[str] = field(default_factory=set)
    protected_writes: set[str] = field(default_factory=set)


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
    iteration_limit: int | None = None
    cycle_nodes: set[str] = field(default_factory=set)
    unreachable_nodes: set[str] = field(default_factory=set)


@dataclass
class ModuleFacts:
    """Facts extracted from one source module by an adapter."""

    path: Path
    call_sites: list[CallSite]
    loops: list[Loop]
    graphs: list[AgentGraph]
    module_mutables: dict[str, Location]
    imports: dict[str, str]
    taint_flows: list[TaintFlow] = field(default_factory=list)
    secrets: list[SecretFact] = field(default_factory=list)
    exception_facts: list[ExceptionFact] = field(default_factory=list)
    state_growths: list[Location] = field(default_factory=list)
    call_graph: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass
class AgentSystem:
    """All normalized module facts from one scan."""

    modules: list[ModuleFacts]
