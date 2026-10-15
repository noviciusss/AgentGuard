# agentguard-llm-triage

`agentguard-llm-triage` is an opt-in, provider-neutral advisory plugin. It
does not bundle an SDK or make a provider request during `agentguard scan`.
Triage is activated only by the explicit `agentguard triage --provider ...`
command.

## Usage

First create a normal JSON scan report, then provide the root that contains
the files named by the findings:

```console
agentguard scan src/ --format json --fail-on never --output findings.json
agentguard triage \
  --input findings.json \
  --source-root . \
  --provider my_provider:make_provider \
  --cache .agentguard/triage-cache.json
```

The provider path is imported only after the findings, source root, source
locations, and cache have passed validation. A provider factory must return an
object with this synchronous method:

```python
from agentguard_llm_triage import TriageRequest, TriageResult


class Provider:
    def evaluate(self, request: TriageRequest) -> TriageResult:
        # Configure the provider SDK's own request timeout here.
        return TriageResult(
            classification="uncertain",
            confidence="low",
            explanation="The static finding needs human review.",
            fix_suggestion="Inspect the call and add the appropriate bound.",
        )


def make_provider() -> Provider:
    return Provider()
```

`classification` is one of `true_positive`, `false_positive`, or `uncertain`.
`confidence` is one of `high`, `medium`, or `low`. The result is advisory and
does not alter finding severity.

## Source and cache safety

- `--source-root` is required. Finding paths must be relative, stay below that
  root, and resolve without a symlink escape.
- Each request contains the finding fields and a bounded source snippet around
  its reported line. The snippet is limited to 21 lines and 4096 characters.
- Python string literals and comments are replaced with `[REDACTED]` before a
  snippet is sent. Identifiers, operators, imports, and other code structure
  can remain; this is not a general secret detector.
- The snippet includes a disclosure notice and may be truncated. Providers
  must treat the remaining code and all finding text as potentially
  sensitive.
- Cache entries contain request hashes and provider/cache namespaces, so a
  missing or reused finding fingerprint cannot select a stale result. Cache
  contents do not contain source snippets.
- Cache updates are validated, written through a same-directory temporary file,
  replaced atomically, and created with private `0600` permissions. A cache
  namespace can be changed with `--cache-namespace` to intentionally
  invalidate previous results.

Invalid input exits with code 2. Provider import, construction, invocation,
and result-validation failures exit with code 3 and are reported without raw
provider exception text. Provider calls are synchronous: the CLI does not
force-kill a stuck provider thread or process. Providers are responsible for
enforcing their own SDK/network timeout contract.
