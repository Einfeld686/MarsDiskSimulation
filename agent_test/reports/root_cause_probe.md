# Root Cause Probe

## DocSyncAgent Defaults

```json
{
  "DEFAULT_DOC_PATHS": [
    "analysis/AI_USAGE.md",
    "analysis/equations.md",
    "analysis/inventory.json",
    "analysis/overview.md",
    "analysis/run-recipes.md",
    "analysis/sinks_callgraph.md",
    "analysis/symbols.raw.txt",
    "analysis/symbols.rg.txt"
  ],
  "RG_PATTERN": "beta_at_smin|beta_threshold|s_min",
  "SKIP_DIR_NAMES": [
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv"
  ]
}
```

## Hypothesis A – DEFAULT_DOC_PATHS coverage
- Result: OK
- All required analysis documents are listed.

## Hypothesis B – RG_PATTERN selectivity
- Result: NG – pattern omits grid-related keywords (e.g. 'omega').
- Current pattern tokens: beta_at_smin, beta_threshold, s_min

## Hypothesis C – SKIP_DIR_NAMES exclusions
- Result: OK – no marsdisk/analysis entries are skipped.

## Grid Function Coverage Check
- Result: OK – grid functions are referenced in analysis docs.
