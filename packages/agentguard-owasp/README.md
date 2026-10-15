# agentguard-owasp

Offline OWASP LLM Top 10 (2025) and CWE metadata plugin for AgentGuard.

The modifier adds deterministic `tags` and `metadata` to applicable findings.
It never makes network calls or changes severity. Current mappings cover
prompt injection, excessive agency, improper output handling, sensitive
information disclosure, unbounded retries, unbounded agent loops, no-cost
budgets, and unbounded state growth.

Example machine-readable output includes:

```json
{
  "tags": ["CWE-693", "LLM01:Prompt Injection"],
  "metadata": {
    "cwe": "CWE-693",
    "owasp": "LLM01:Prompt Injection",
    "owasp_version": "2025"
  }
}
```
