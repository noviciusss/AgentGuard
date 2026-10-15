"""Private same-file symbolic taint propagation.

Only module-level functions in the parsed module are resolved.  Imported,
dynamic, class, and nested-function calls remain unknown for return-flow
purposes.  Function summaries record direct sources and dependencies on formal
parameters; sink summaries retain the source location where the sink occurs.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from agentguard.findings import Location
from agentguard.ir.calls import lookup_known_call
from agentguard.ir.models import DataSource, TaintFlow, TaintSink

_EXTERNAL_PARAMETER_NAMES = frozenset({"user_input", "prompt", "query", "message"})


@dataclass(frozen=True)
class _SymbolicValue:
    """Sources and current-function formal parameters in an expression."""

    sources: frozenset[DataSource]
    dependencies: frozenset[str]


_EMPTY_VALUE = _SymbolicValue(frozenset(), frozenset())


@dataclass(frozen=True)
class _Parameter:
    name: str
    default: ast.expr | None
    positional_only: bool


@dataclass(frozen=True)
class _FunctionInfo:
    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    positional_only: tuple[_Parameter, ...]
    positional_or_keyword: tuple[_Parameter, ...]
    keyword_only: tuple[_Parameter, ...]
    vararg: str | None
    kwarg: str | None

    @property
    def parameters(self) -> tuple[_Parameter, ...]:
        return (
            *self.positional_only,
            *self.positional_or_keyword,
            *self.keyword_only,
            *(
                (_Parameter(self.vararg, None, False),)
                if self.vararg is not None
                else ()
            ),
            *((_Parameter(self.kwarg, None, False),) if self.kwarg is not None else ()),
        )


@dataclass(frozen=True)
class _SinkSummary:
    loc: Location
    sink: TaintSink
    value: _SymbolicValue
    function: str | None


@dataclass(frozen=True)
class _FunctionSummary:
    returns: _SymbolicValue
    sinks: frozenset[_SinkSummary]


_EMPTY_SUMMARY = _FunctionSummary(_EMPTY_VALUE, frozenset())


@dataclass(frozen=True)
class _BranchResult:
    environment: dict[str, _SymbolicValue]
    returns: _SymbolicValue
    sinks: frozenset[_SinkSummary]


@dataclass(frozen=True)
class _CallArguments:
    positional: tuple[_SymbolicValue, ...]
    keywords: dict[str, _SymbolicValue]
    dynamic_keywords: tuple[_SymbolicValue, ...]


def analyze_interprocedural(
    tree: ast.Module, path: Path
) -> tuple[list[TaintFlow], dict[str, tuple[str, ...]]]:
    """Return deterministic same-file taint flows and the local call graph."""
    functions = _collect_functions(tree)
    import_aliases = _module_aliases(tree)
    function_aliases = _function_aliases(tree, functions, import_aliases)
    call_graph, called_functions = _call_graph_and_called_functions(
        tree, functions, function_aliases, import_aliases
    )
    summaries = _fixed_point_summaries(
        path, functions, function_aliases, import_aliases
    )

    flow_values: set[tuple[Location, DataSource, TaintSink, str | None]] = set()
    module_runner = _SummaryBuilder(
        path,
        None,
        None,
        functions,
        function_aliases,
        import_aliases,
        summaries,
    )
    module_runner.visit_block(tree.body)
    _add_flows(flow_values, module_runner.sinks, {})

    for name, info in sorted(functions.items()):
        if name in called_functions:
            continue
        bindings = _entry_bindings(
            path,
            info,
            functions,
            function_aliases,
            import_aliases,
            summaries,
        )
        _add_flows(flow_values, summaries[name].sinks, bindings)

    flows = [
        TaintFlow(
            loc=loc,
            source=source,
            sink=sink,
            function=function,
            value_name=None,
        )
        for loc, source, sink, function in sorted(
            flow_values,
            key=lambda value: (
                value[0].file.as_posix(),
                value[0].line,
                value[0].col,
                value[0].end_line,
                value[0].end_col,
                value[1].value,
                value[2].value,
                value[3] or "",
            ),
        )
    ]
    return flows, call_graph


def _collect_functions(tree: ast.Module) -> dict[str, _FunctionInfo]:
    """Collect only module-level functions; class and nested names are local."""
    functions: dict[str, _FunctionInfo] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = _function_info(node)
    return functions


def _function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> _FunctionInfo:
    positional = [*node.args.posonlyargs, *node.args.args]
    default_offset = len(positional) - len(node.args.defaults)
    defaults: list[ast.expr | None] = [None] * default_offset
    defaults.extend(node.args.defaults)
    positional_only = tuple(
        _Parameter(argument.arg, defaults[index], True)
        for index, argument in enumerate(node.args.posonlyargs)
    )
    positional_or_keyword = tuple(
        _Parameter(argument.arg, defaults[index], False)
        for index, argument in enumerate(
            node.args.args, start=len(node.args.posonlyargs)
        )
    )
    keyword_only = tuple(
        _Parameter(argument.arg, default, False)
        for argument, default in zip(
            node.args.kwonlyargs, node.args.kw_defaults, strict=False
        )
    )
    return _FunctionInfo(
        name=node.name,
        node=node,
        positional_only=positional_only,
        positional_or_keyword=positional_or_keyword,
        keyword_only=keyword_only,
        vararg=node.args.vararg.arg if node.args.vararg is not None else None,
        kwarg=node.args.kwarg.arg if node.args.kwarg is not None else None,
    )


def _function_aliases(
    tree: ast.Module,
    functions: dict[str, _FunctionInfo],
    import_aliases: dict[str, str],
) -> dict[str, str]:
    """Resolve an unambiguous module-level ``alias = function`` binding."""
    assignments: dict[str, list[str]] = {}
    assignment_counts: dict[str, int] = {}
    for node in tree.body:
        targets: list[ast.AST] = []
        value: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            assignment_counts[target.id] = assignment_counts.get(target.id, 0) + 1
            if isinstance(value, ast.Name):
                assignments.setdefault(target.id, []).append(value.id)

    aliases: dict[str, str] = {}
    for _ in range(max(len(assignments), 1)):
        changed = False
        for alias, candidates in sorted(assignments.items()):
            if assignment_counts[alias] != 1 or len(candidates) != 1:
                continue
            candidate = candidates[0]
            if candidate in import_aliases:
                continue
            resolved = candidate
            if candidate in aliases:
                resolved = aliases[candidate]
            if resolved not in functions or aliases.get(alias) == resolved:
                continue
            aliases[alias] = resolved
            changed = True
        if not changed:
            break
    return aliases


def _fixed_point_summaries(
    path: Path,
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
) -> dict[str, _FunctionSummary]:
    """Resolve finite symbolic summaries until recursive growth stops."""
    summaries = {name: _EMPTY_SUMMARY for name in functions}
    maximum_iterations = max(8, (len(functions) + 1) * (len(functions) + 1) * 4)
    for _ in range(maximum_iterations):
        updated = {
            name: _summarize_function(
                path,
                info,
                functions,
                function_aliases,
                import_aliases,
                summaries,
            )
            for name, info in sorted(functions.items())
        }
        if updated == summaries:
            return summaries
        summaries = updated
    return summaries


def _summarize_function(
    path: Path,
    info: _FunctionInfo,
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
    summaries: dict[str, _FunctionSummary],
) -> _FunctionSummary:
    builder = _SummaryBuilder(
        path,
        info.name,
        info,
        functions,
        function_aliases,
        import_aliases,
        summaries,
    )
    builder.visit_block(info.node.body)
    return _FunctionSummary(builder.returns, frozenset(builder.sinks))


class _SummaryBuilder:
    """Flow-insensitive symbolic execution of one lexical function scope."""

    def __init__(
        self,
        path: Path,
        function_name: str | None,
        info: _FunctionInfo | None,
        functions: dict[str, _FunctionInfo],
        function_aliases: dict[str, str],
        import_aliases: dict[str, str],
        summaries: dict[str, _FunctionSummary],
    ) -> None:
        self.path = path
        self.function_name = function_name
        self.info = info
        self.functions = functions
        self.function_aliases = function_aliases
        self.import_aliases = import_aliases
        self.summaries = summaries
        self.environment: dict[str, _SymbolicValue] = {}
        self.returns = _EMPTY_VALUE
        self.sinks: set[_SinkSummary] = set()
        if info is not None:
            for parameter in info.parameters:
                self.environment[parameter.name] = _value(dependencies={parameter.name})

    def visit_block(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self.visit_statement(statement)

    def visit_statement(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Assign):
            value = self.evaluate(node.value)
            for target in node.targets:
                self.assign(target, value)
            return
        if isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.assign(node.target, self.evaluate(node.value))
            return
        if isinstance(node, ast.AugAssign):
            value = _merge_values(self.evaluate(node.target), self.evaluate(node.value))
            self.assign(node.target, value)
            return
        if isinstance(node, ast.Return):
            if node.value is not None:
                self.returns = _merge_values(self.returns, self.evaluate(node.value))
            return
        if isinstance(node, ast.Expr):
            self.evaluate(node.value)
            return
        if isinstance(node, ast.If):
            self.evaluate(node.test)
            body = self.branch(node.body)
            alternate = self.branch(node.orelse)
            self.merge_branches((body, alternate))
            return
        if isinstance(node, (ast.For, ast.AsyncFor)):
            iterator = self.evaluate(node.iter)
            body = self.branch(node.body, (node.target, iterator))
            alternate = self.branch(node.orelse)
            self.merge_branches(
                (
                    _BranchResult(dict(self.environment), _EMPTY_VALUE, frozenset()),
                    body,
                    alternate,
                )
            )
            return
        if isinstance(node, ast.While):
            self.evaluate(node.test)
            body = self.branch(node.body)
            alternate = self.branch(node.orelse)
            self.merge_branches(
                (
                    _BranchResult(dict(self.environment), _EMPTY_VALUE, frozenset()),
                    body,
                    alternate,
                )
            )
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                self.evaluate(item.context_expr)
                if item.optional_vars is not None:
                    self.assign(item.optional_vars, _EMPTY_VALUE)
            self.visit_block(node.body)
            return
        if isinstance(node, ast.Try):
            branches = [self.branch(node.body)]
            branches.extend(self.branch(handler.body) for handler in node.handlers)
            branches.append(self.branch(node.orelse))
            self.merge_branches(tuple(branches))
            self.visit_block(node.finalbody)
            return
        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.environment.pop(target.id, None)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
            return
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self.evaluate(child)

    def branch(
        self,
        statements: list[ast.stmt],
        assignment: tuple[ast.expr, _SymbolicValue] | None = None,
    ) -> _BranchResult:
        branch = _SummaryBuilder(
            self.path,
            self.function_name,
            self.info,
            self.functions,
            self.function_aliases,
            self.import_aliases,
            self.summaries,
        )
        branch.environment = dict(self.environment)
        if assignment is not None:
            branch.assign(*assignment)
        branch.visit_block(statements)
        return _BranchResult(
            branch.environment,
            branch.returns,
            frozenset(branch.sinks),
        )

    def merge_branches(self, branches: tuple[_BranchResult, ...]) -> None:
        environment: dict[str, _SymbolicValue] = {}
        for branch in branches:
            for name, value in branch.environment.items():
                environment[name] = _merge_values(
                    environment.get(name, _EMPTY_VALUE), value
                )
        self.environment = environment
        for branch in branches:
            self.returns = _merge_values(self.returns, branch.returns)
            self.sinks.update(branch.sinks)

    def assign(self, target: ast.expr, value: _SymbolicValue) -> None:
        if isinstance(target, ast.Name):
            self.environment[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self.assign(element, value)

    def evaluate(self, node: ast.expr) -> _SymbolicValue:
        if isinstance(node, ast.Constant):
            return _EMPTY_VALUE
        if isinstance(node, ast.Name):
            return self.environment.get(node.id, _EMPTY_VALUE)
        if isinstance(node, ast.Lambda):
            return _EMPTY_VALUE
        if isinstance(node, ast.Call):
            arguments = self.call_arguments(node)
            argument_value = _merge_values(
                *arguments.positional,
                *arguments.keywords.values(),
                *arguments.dynamic_keywords,
            )
            qualified = _qualified_static(node.func, self.import_aliases)
            sink = _sink(qualified, node)
            if sink is not None:
                self.sinks.add(
                    _SinkSummary(
                        _location(self.path, node),
                        sink,
                        argument_value,
                        self.function_name,
                    )
                )

            target = _resolve_local_function(
                node.func, self.functions, self.function_aliases, self.import_aliases
            )
            if target is None:
                return _value(sources=_direct_call_sources(qualified))
            callee = self.summaries[target.name]
            bindings = _bind_arguments(self, target, arguments)
            for summary_sink in callee.sinks:
                self.sinks.add(_instantiate_sink(summary_sink, bindings))
            result = _instantiate(callee.returns, bindings)
            if target.name == self.function_name and callee.returns == _EMPTY_VALUE:
                result = _merge_values(result, *bindings.values())
            return result
        if isinstance(node, ast.NamedExpr):
            value = self.evaluate(node.value)
            self.assign(node.target, value)
            return value

        result = _EMPTY_VALUE
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                result = _merge_values(result, self.evaluate(child))
        return result

    def call_arguments(self, node: ast.Call) -> _CallArguments:
        positional = tuple(
            self.evaluate(argument.value)
            if isinstance(argument, ast.Starred)
            else self.evaluate(argument)
            for argument in node.args
        )
        keywords: dict[str, _SymbolicValue] = {}
        dynamic: list[_SymbolicValue] = []
        for keyword in node.keywords:
            value = self.evaluate(keyword.value)
            if keyword.arg is None:
                dynamic.append(value)
            else:
                keywords[keyword.arg] = value
        return _CallArguments(positional, keywords, tuple(dynamic))


def _bind_arguments(
    builder: _SummaryBuilder,
    info: _FunctionInfo,
    arguments: _CallArguments,
) -> dict[str, _SymbolicValue]:
    bindings = {parameter.name: _EMPTY_VALUE for parameter in info.parameters}
    consumed_keywords: set[str] = set()
    positional_parameters = [*info.positional_only, *info.positional_or_keyword]
    for index, parameter in enumerate(positional_parameters):
        if index < len(arguments.positional):
            bindings[parameter.name] = arguments.positional[index]
        elif not parameter.positional_only and parameter.name in arguments.keywords:
            bindings[parameter.name] = arguments.keywords[parameter.name]
            consumed_keywords.add(parameter.name)
        elif parameter.default is not None:
            bindings[parameter.name] = builder.evaluate(parameter.default)

    if info.vararg is not None:
        bindings[info.vararg] = _merge_values(
            *arguments.positional[len(positional_parameters) :]
        )

    for parameter in info.keyword_only:
        if parameter.name in arguments.keywords:
            bindings[parameter.name] = arguments.keywords[parameter.name]
            consumed_keywords.add(parameter.name)
        elif parameter.default is not None:
            bindings[parameter.name] = builder.evaluate(parameter.default)

    if info.kwarg is not None:
        bindings[info.kwarg] = _merge_values(
            *arguments.dynamic_keywords,
            *(
                value
                for name, value in arguments.keywords.items()
                if name not in consumed_keywords
                and name not in {parameter.name for parameter in info.positional_only}
            ),
        )
    return bindings


def _entry_bindings(
    path: Path,
    info: _FunctionInfo,
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
    summaries: dict[str, _FunctionSummary],
) -> dict[str, _SymbolicValue]:
    bindings: dict[str, _SymbolicValue] = {}
    defaults = _SummaryBuilder(
        path,
        None,
        None,
        functions,
        function_aliases,
        import_aliases,
        summaries,
    )
    for parameter in info.parameters:
        if parameter.name in _EXTERNAL_PARAMETER_NAMES:
            bindings[parameter.name] = _value(sources={DataSource.USER_INPUT})
        elif parameter.default is not None:
            bindings[parameter.name] = defaults.evaluate(parameter.default)
        else:
            bindings[parameter.name] = _EMPTY_VALUE
    return bindings


def _instantiate(
    value: _SymbolicValue, bindings: dict[str, _SymbolicValue]
) -> _SymbolicValue:
    result = _value(sources=value.sources)
    for dependency in value.dependencies:
        result = _merge_values(result, bindings.get(dependency, _EMPTY_VALUE))
    return result


def _instantiate_sink(
    sink: _SinkSummary, bindings: dict[str, _SymbolicValue]
) -> _SinkSummary:
    return _SinkSummary(
        sink.loc,
        sink.sink,
        _instantiate(sink.value, bindings),
        sink.function,
    )


def _add_flows(
    flow_values: set[tuple[Location, DataSource, TaintSink, str | None]],
    sinks: frozenset[_SinkSummary] | set[_SinkSummary],
    bindings: dict[str, _SymbolicValue],
) -> None:
    for sink in sinks:
        value = _instantiate(sink.value, bindings)
        for source in value.sources:
            flow_values.add((sink.loc, source, sink.sink, sink.function))


def _call_graph_and_called_functions(
    tree: ast.Module,
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    graph: dict[str, tuple[str, ...]] = {}
    called: set[str] = set()
    for name, info in sorted(functions.items()):
        targets = _resolved_calls(
            info.node.body, functions, function_aliases, import_aliases
        )
        graph[name] = tuple(sorted(targets))
        called.update(targets)
    top_level_statements = [
        node
        for node in tree.body
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    called.update(
        _resolved_calls(
            top_level_statements, functions, function_aliases, import_aliases
        )
    )
    return graph, called


class _ResolvedCallCollector(ast.NodeVisitor):
    def __init__(
        self,
        functions: dict[str, _FunctionInfo],
        function_aliases: dict[str, str],
        import_aliases: dict[str, str],
    ) -> None:
        self.functions = functions
        self.function_aliases = function_aliases
        self.import_aliases = import_aliases
        self.targets: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        target = _resolve_local_function(
            node.func, self.functions, self.function_aliases, self.import_aliases
        )
        if target is not None:
            self.targets.add(target.name)
        self.generic_visit(node)


def _resolved_calls(
    statements: list[ast.stmt],
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
) -> set[str]:
    collector = _ResolvedCallCollector(functions, function_aliases, import_aliases)
    for statement in statements:
        collector.visit(statement)
    return collector.targets


def _resolve_local_function(
    node: ast.AST,
    functions: dict[str, _FunctionInfo],
    function_aliases: dict[str, str],
    import_aliases: dict[str, str],
) -> _FunctionInfo | None:
    if not isinstance(node, ast.Name) or node.id in import_aliases:
        return None
    name = function_aliases.get(node.id, node.id)
    return functions.get(name)


def _module_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for item in node.names:
                if item.name != "*":
                    aliases[item.asname or item.name] = (f"{module}.{item.name}").strip(
                        "."
                    )
    return aliases


def _qualified_static(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        return f"{_qualified_static(node.value, aliases)}.{node.attr}"
    return "<dynamic>"


def _direct_call_sources(qualified: str) -> set[DataSource]:
    sources: set[DataSource] = set()
    if qualified in {"input", "builtins.input"}:
        sources.add(DataSource.USER_INPUT)
    if qualified.endswith(".getenv") or qualified == "os.getenv":
        sources.add(DataSource.ENV)
    known = lookup_known_call(qualified)
    if known is not None and known.kind == "llm":
        sources.add(DataSource.LLM_OUTPUT)
    if known is not None and known.kind == "tool":
        sources.add(DataSource.TOOL_OUTPUT)
    if any(
        marker in qualified.lower()
        for marker in (".responses.", ".chat.", ".completions.")
    ):
        sources.add(DataSource.LLM_OUTPUT)
    return sources


def _sink(qualified: str, node: ast.Call) -> TaintSink | None:
    leaf = qualified.rsplit(".", 1)[-1]
    if leaf == "eval":
        return TaintSink.EVAL
    if leaf == "exec":
        return TaintSink.EXEC
    if qualified.startswith("subprocess."):
        return TaintSink.SUBPROCESS
    if leaf in {"execute", "executemany"}:
        return TaintSink.SQL
    if leaf == "open" or qualified == "pathlib.Path":
        return TaintSink.FILE_PATH
    if any(
        keyword in qualified.lower() for keyword in {"system_prompt", "systemmessage"}
    ):
        return TaintSink.SYSTEM_PROMPT
    if any(keyword.arg in {"system", "system_prompt"} for keyword in node.keywords):
        return TaintSink.SYSTEM_PROMPT
    return None


def _value(
    sources: set[DataSource] | frozenset[DataSource] | None = None,
    dependencies: set[str] | frozenset[str] | None = None,
) -> _SymbolicValue:
    return _SymbolicValue(
        frozenset() if sources is None else frozenset(sources),
        frozenset() if dependencies is None else frozenset(dependencies),
    )


def _merge_values(*values: _SymbolicValue) -> _SymbolicValue:
    return _value(
        sources={source for value in values for source in value.sources},
        dependencies={
            dependency for value in values for dependency in value.dependencies
        },
    )


def _location(path: Path, node: ast.AST) -> Location:
    line = getattr(node, "lineno", 1)
    col = getattr(node, "col_offset", 0)
    return Location(
        path,
        line,
        col,
        getattr(node, "end_lineno", line),
        getattr(node, "end_col_offset", col + 1),
    )
