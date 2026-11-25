# Langfuse Prompt Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The order assistant crew fetches all 11 prompts from Langfuse at runtime; the project
ships them in a TOML file plus a `make prompts-push` setup command.

**Architecture:** `crew/prompts.toml` (package data) holds the prompts in Langfuse `{{var}}`
syntax. `crew/prompts.py` loads that file (for setup and tests only) and fetches the `production`
versions from Langfuse at runtime, converting them to CrewAI `{var}` syntax. `crew/push_prompts.py`
is the setup CLI. `crew.py` keeps no prompt text and records prompt versions on the trace.

**Tech Stack:** Python 3.13, uv, CrewAI 1.15, Langfuse SDK 5.2, stdlib `tomllib`, pytest, mypy
strict, ruff.

**Spec:** `docs/superpowers/specs/2026-11-25-langfuse-prompt-management-design.md`

All paths below are relative to `apps/server/`. Run commands from `apps/server/`.

## Global Constraints

- No runtime fallback: prompt text exists only in Langfuse at runtime and in `prompts.toml` for
  setup/tests. `crew.py` holds no prompt text.
- Langfuse label: `production`; prompt type: `text`; fetch cache TTL: 60 seconds.
- Prompt names (exactly 11): `order-assistant/resolve-request`, `order-assistant/expected-answer`,
  `order-assistant/{details-agent,search-agent,refund-agent}/{role,goal,backstory}`.
- `prompts-push` never changes an existing prompt unless `--force` is given.
- No new dependencies. Tests make no network calls.
- Do not commit; the user commits on request (`AGENTS.md` + global rules). Run `make test` after
  each task.

## Review Focus

1. Langfuse unreachable or a prompt missing at request time → `PromptsUnavailableError` naming the
   prompt and `make prompts-push`; the endpoint returns 503 (test in Task 1).
2. Langfuse keys unset → `PromptsUnavailableError` without any network call (test in Task 1).
3. A prompt edited in Langfuse to use an unknown `{{var}}` (or a variable in an agent text) →
   rejected at fetch with `PromptsUnavailableError` naming the prompt, not a CrewAI `KeyError`
   mid-run (test in Task 1).
4. `prompts-push` run twice → second run creates nothing (test in Task 3).
5. `prompts-push` when Langfuse fails with a non-404 error → creates nothing for that prompt,
   reports it, exits non-zero (test in Task 3).

---

### Task 1: Prompt file and runtime prompt fetching

**Files:**
- Create: `src/langfuse_agent_demo/crew/prompts.toml`
- Create: `src/langfuse_agent_demo/crew/prompts.py`
- Test: `tests/crew/test_prompts.py`

**Interfaces:**
- Produces (in `langfuse_agent_demo.crew.prompts`):
  - `LABEL = "production"`, `CACHE_TTL_SECONDS = 60`
  - `PROMPT_NAMES: tuple[str, ...]` (the 11 names, order as in Global Constraints)
  - `TASK_VARIABLES = {"message", "today"}`; only `order-assistant/resolve-request` may use them
  - `class PromptsUnavailableError(RuntimeError)`
  - `load_prompt_file() -> dict[str, str]`: Langfuse-syntax texts keyed by name
  - `to_crewai(text: str) -> str`: `{{ name }}` → `{name}`
  - `@dataclass(frozen=True) class CrewPrompts`: `texts: Mapping[str, str]` (CrewAI syntax),
    `versions: Mapping[str, int]`; `__getitem__(name: str) -> str` returns the text
  - `CrewPrompts.from_file() -> CrewPrompts` (classmethod; versions all `0`; tests only)
  - `langfuse_client() -> Langfuse`: raises `PromptsUnavailableError` if
    `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` unset; otherwise builds `Langfuse(...)` from
    settings exactly as `observability.setup_tracing` does
  - `fetch_prompts(client: Langfuse) -> CrewPrompts`

- [ ] **Step 1: Write `prompts.toml`** — nested tables flattened with `/` give the names:
  `[order-assistant]` with `resolve-request` / `expected-answer` (multi-line strings, text copied
  verbatim from `RESOLVE_REQUEST` / `EXPECTED_ANSWER` in `crew.py`, with `{message}` → `{{message}}`
  and `{today}` → `{{today}}`), and `[order-assistant.details-agent]` etc. with `role`, `goal`,
  `backstory` copied verbatim from the `Agent(...)` calls. Top comment: this file is loaded into
  Langfuse by `make prompts-push`; edit prompts in Langfuse afterwards.

- [ ] **Step 2: Write the failing tests** in `tests/crew/test_prompts.py`, with a `FakeLangfuse`
  whose `get_prompt(name, *, label, type, cache_ttl_seconds)` returns
  `SimpleNamespace(prompt=..., version=...)` from a dict or raises a stored exception, and records
  calls:

```python
def test_file_has_exactly_the_crew_prompts() -> None:
    assert set(load_prompt_file()) == set(PROMPT_NAMES)
    assert len(PROMPT_NAMES) == 11

def test_only_the_task_prompt_uses_variables() -> None:
    texts = load_prompt_file()
    assert set(re.findall(r"\{\{\s*(\w+)\s*\}\}", texts["order-assistant/resolve-request"])) == TASK_VARIABLES
    others = [t for n, t in texts.items() if n != "order-assistant/resolve-request"]
    assert not any("{" in t or "}" in t for t in others)

def test_to_crewai() -> None:
    assert to_crewai("Hi {{message}} on {{ today }}") == "Hi {message} on {today}"

def test_fetch_converts_and_records_versions() -> None:
    client = FakeLangfuse({n: (t, 3) for n, t in load_prompt_file().items()})
    prompts = fetch_prompts(client)
    assert "{message}" in prompts["order-assistant/resolve-request"]
    assert prompts.versions["order-assistant/refund-agent/goal"] == 3
    assert all(c == {"label": "production", "type": "text", "cache_ttl_seconds": 60}
               for c in client.call_kwargs)

def test_fetch_failure_names_prompt() -> None:  # Review Focus 1
    client = FakeLangfuse({}, error=ConnectionError("down"))
    with pytest.raises(PromptsUnavailableError, match="order-assistant/resolve-request.*make prompts-push"):
        fetch_prompts(client)

def test_unknown_variable_rejected() -> None:  # Review Focus 3
    texts = load_prompt_file() | {"order-assistant/search-agent/goal": "Find {{customer}}"}
    with pytest.raises(PromptsUnavailableError, match="order-assistant/search-agent/goal"):
        fetch_prompts(FakeLangfuse({n: (t, 1) for n, t in texts.items()}))

def test_client_requires_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # Review Focus 2
    # chdir to tmp_path, set NORTHWIND_DB_PATH, delenv LANGFUSE_* keys, clear settings cache
    with pytest.raises(PromptsUnavailableError, match="LANGFUSE_PUBLIC_KEY"):
        langfuse_client()
```

  (`fetch_prompts` takes a `Langfuse`; pass the fake with `cast(Langfuse, client)`.)

- [ ] **Step 3: Run** `uv run pytest tests/crew/test_prompts.py -v` — expected: FAIL (module missing).

- [ ] **Step 4: Implement `prompts.py`.** Load the file with
  `importlib.resources.files(__package__) / "prompts.toml"` + `tomllib`. `fetch_prompts` fetches
  every name in `PROMPT_NAMES`; any exception from `get_prompt` becomes
  `PromptsUnavailableError(f"Prompt {name!r} could not be fetched from Langfuse (label "
  f"'production'); run `make prompts-push` to create it")` chained with `from exc`. It then checks
  each text's `{{var}}` set (must equal-or-subset `TASK_VARIABLES` for resolve-request, empty for
  all others, and no stray single braces left after `to_crewai`) and raises
  `PromptsUnavailableError` naming the prompt otherwise.

- [ ] **Step 5: Run** `make test` — expected: all pass.

### Task 2: Crew builds from fetched prompts; trace records versions

**Files:**
- Modify: `src/langfuse_agent_demo/crew/crew.py` (delete `RESOLVE_REQUEST`, `EXPECTED_ANSWER` and
  inline agent strings)
- Modify: `src/langfuse_agent_demo/observability.py` (`trace_order_request`)
- Test: `tests/crew/test_crew.py`, `tests/test_observability.py`

**Interfaces:**
- Consumes: `CrewPrompts`, `CrewPrompts.from_file`, `fetch_prompts`, `langfuse_client` (Task 1)
- Produces:
  - `build_crew(llm: LLM, prompts: CrewPrompts, verbose: bool = False) -> Crew`
  - `trace_order_request(message: str, prompt_versions: Mapping[str, int]) -> Iterator[Callable[[str], None]]`;
    the span gets `metadata={"prompts": dict(prompt_versions)}`
  - `run_order_assistant(message)`: `prompts = fetch_prompts(langfuse_client())` before
    `make_llm()`/`build_crew`, then `trace_order_request(message, prompts.versions)`

- [ ] **Step 1: Update tests.** `test_crew_structure` and `test_agents_in_one_crew_share_tools`
  pass `CrewPrompts.from_file()`; `test_crew_structure` also asserts
  `crew.agents[2].role == CrewPrompts.from_file()["order-assistant/refund-agent/role"]`.
  `test_run_is_wrapped_in_a_trace` monkeypatches `crew_module.langfuse_client` (returns a sentinel)
  and `crew_module.fetch_prompts` (returns `CrewPrompts(texts=..., versions={"x": 2})`), and its
  `fake_trace(message, prompt_versions)` records `prompt_versions`; assert it equals `{"x": 2}`.
  Add `test_run_fails_when_prompts_unavailable`: `langfuse_client` raises
  `PromptsUnavailableError` → `run_order_assistant` raises it and `make_llm` is never called.
  In `test_observability.py`, `test_request_span_records_message_and_answer` passes
  `{"order-assistant/resolve-request": 4}` and asserts `"order-assistant/resolve-request"` appears
  in `str(attributes)`; the no-op test passes `{}`.

- [ ] **Step 2: Run** `uv run pytest tests/crew/test_crew.py tests/test_observability.py -v` —
  expected: FAIL (signature mismatch).

- [ ] **Step 3: Implement** the Interfaces above. The module docstring of `crew.py` notes that
  prompts come from Langfuse (`crew/prompts.toml` seeds them).

- [ ] **Step 4: Run** `make test` — expected: all pass.

### Task 3: `prompts-push` setup command and docs

**Files:**
- Create: `src/langfuse_agent_demo/crew/push_prompts.py`
- Modify: `Makefile`, `README.md`, `.env.example` (Langfuse keys comment: now required to run the
  crew)
- Test: `tests/crew/test_push_prompts.py`

**Interfaces:**
- Consumes: `load_prompt_file`, `PROMPT_NAMES`, `LABEL`, `langfuse_client` (Task 1)
- Produces:
  - `push_prompts(client: Langfuse, texts: Mapping[str, str], force: bool = False) -> dict[str, str]`
    returning name → one of `"created"`, `"unchanged"`, `"differs"` (skipped), `"updated"`,
    `"error: <exception>"`
  - `main(argv: Sequence[str] | None = None) -> int` (argparse, `--force`); prints one line per
    prompt; returns `1` if any result is `"error..."`, else `0`
  - Makefile target `prompts-push: uv run python -m langfuse_agent_demo.crew.push_prompts $(ARGS)`
    (usage: `make prompts-push ARGS=--force`)

- [ ] **Step 1: Write the failing tests** with a `FakeLangfuse` that stores prompts by name,
  raises `langfuse.api.NotFoundError` for unknown names (construct it as the SDK does; check its
  `__init__`), and records `create_prompt` kwargs:

```python
def test_creates_missing_prompts() -> None:
    client = FakeLangfuse()
    assert set(push_prompts(client, TEXTS).values()) == {"created"}
    assert client.created[0]["labels"] == ["production"] and client.created[0]["type"] == "text"

def test_second_run_creates_nothing() -> None:  # Review Focus 4
    client = FakeLangfuse(); push_prompts(client, TEXTS)
    assert set(push_prompts(client, TEXTS).values()) == {"unchanged"}
    assert len(client.created) == len(TEXTS)

def test_edited_prompt_kept_without_force() -> None:
    client = FakeLangfuse(existing={NAME: "edited in Langfuse"})
    assert push_prompts(client, {NAME: "from file"}) == {NAME: "differs"}
    assert client.created == []

def test_force_creates_new_production_version() -> None:
    client = FakeLangfuse(existing={NAME: "edited in Langfuse"})
    assert push_prompts(client, {NAME: "from file"}, force=True) == {NAME: "updated"}
    assert client.created == [{"name": NAME, "prompt": "from file", "labels": ["production"], "type": "text"}]

def test_non_404_error_creates_nothing() -> None:  # Review Focus 5
    client = FakeLangfuse(error=ConnectionError("down"))
    assert push_prompts(client, {NAME: "x"})[NAME].startswith("error")
    assert client.created == []

def test_main_exit_code(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # monkeypatch push_prompts module's langfuse_client to return FakeLangfuse(error=...)
    assert main([]) == 1
    assert NAME in capsys.readouterr().out
```

  (`TEXTS = load_prompt_file()`, `NAME = "order-assistant/resolve-request"`.)

- [ ] **Step 2: Run** `uv run pytest tests/crew/test_push_prompts.py -v` — expected: FAIL.

- [ ] **Step 3: Implement `push_prompts.py`.** Read the current version with
  `client.get_prompt(name, label=LABEL, type="text", cache_ttl_seconds=0)`; compare its `.prompt`
  to the file text; create with `client.create_prompt(name=..., prompt=..., labels=[LABEL],
  type="text")` (plus `commit_message="make prompts-push"` — omit it from the test's expected dict
  or include it, but be consistent). `main` calls `langfuse_client()` and, if it raises
  `PromptsUnavailableError`, prints the message and returns `1`; it calls `client.flush()` before
  returning. Docstring explains the default-skip and `--force` behavior.

- [ ] **Step 4: Docs.** README Setup becomes: `make install`, `cp .env.example .env` (set the
  Langfuse keys and either the gateway or `OPENAI_API_KEY`), `make prompts-push`. Add a
  "Prompts" section: prompts live in Langfuse under `order-assistant/...`, label `production`,
  cached 60 s; `crew/prompts.toml` is the seed; `make prompts-push ARGS=--force` resets Langfuse to
  the file; without Langfuse the assistant answers 503. Update the settings table row for the
  Langfuse keys ("required: prompts are fetched from Langfuse; also enables tracing").

- [ ] **Step 5: Run** `make test` — expected: all pass.

- [ ] **Step 6: Live check (with the user's `.env`).** `make prompts-push` → 11 `created`;
  run again → 11 `unchanged`; then
  `uv run python -c "from langfuse_agent_demo.crew.crew import run_order_assistant; print(run_order_assistant('Hi, I am customer ALFKI. What were the items in my most recent order?'))"`
  returns an answer listing order items.
