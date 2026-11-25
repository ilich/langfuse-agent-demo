"""The crew's prompts, managed in Langfuse prompt management.

At run time every prompt comes from Langfuse (label ``production``); there is no fallback. The
prompts ship with the project in ``prompts.toml`` next to this module, which
``make prompts-push`` (``push_prompts.py``) loads into a Langfuse project.

Langfuse writes variables as ``{{name}}``; CrewAI interpolates ``{name}`` at kickoff, so fetched
texts are converted. The task prompt must use exactly the variables ``message`` and ``today``;
no other prompt may use any.
"""

import re
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any, Self

from langfuse import Langfuse
from langfuse.api import NotFoundError

from ..config import get_settings

LABEL = "production"
CACHE_TTL_SECONDS = 60
# A request waits at most about 2 x 5 s + 1 s before answering 503 when Langfuse is down.
MAX_RETRIES = 1
FETCH_TIMEOUT_SECONDS = 5

TASK_PROMPT = "order-assistant/resolve-request"
TASK_VARIABLES = {"message", "today"}

PROMPT_NAMES: tuple[str, ...] = (
    TASK_PROMPT,
    "order-assistant/expected-answer",
    *(
        f"order-assistant/{agent}/{field}"
        for agent in ("details-agent", "search-agent", "refund-agent")
        for field in ("role", "goal", "backstory")
    ),
)

_LANGFUSE_VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class PromptsUnavailableError(RuntimeError):
    """The crew's prompts cannot be fetched from Langfuse."""


def load_prompt_file() -> dict[str, str]:
    """The prompts shipped in ``prompts.toml``, in Langfuse syntax, keyed by Langfuse name."""
    data = tomllib.loads((resources.files(__package__) / "prompts.toml").read_text("utf-8"))
    return dict(_flatten(data))


def _flatten(table: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, str]]:
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            yield from _flatten(value, f"{name}/")
        else:
            yield name, value


def to_crewai(text: str) -> str:
    """Convert Langfuse ``{{name}}`` variables to CrewAI ``{name}``."""
    return _LANGFUSE_VARIABLE.sub(r"{\1}", text)


@dataclass(frozen=True)
class CrewPrompts:
    # Texts in CrewAI syntax, keyed by Langfuse prompt name.
    texts: Mapping[str, str]
    # Langfuse prompt version of each text, for the trace.
    versions: Mapping[str, int]

    def __getitem__(self, name: str) -> str:
        return self.texts[name]

    @classmethod
    def from_file(cls) -> Self:
        """The shipped prompts (version 0); for tests, never used at run time."""
        texts = load_prompt_file()
        return cls(
            texts={name: to_crewai(text) for name, text in texts.items()},
            versions=dict.fromkeys(texts, 0),
        )


@lru_cache
def langfuse_client() -> Langfuse:
    """The Langfuse client for prompt management; needs the Langfuse API keys."""
    settings = get_settings()
    if settings.langfuse_public_key is None or settings.langfuse_secret_key is None:
        raise PromptsUnavailableError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set: the crew's prompts come "
            "from Langfuse prompt management"
        )
    # Passed explicitly: pydantic-settings does not export .env values to os.environ.
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
    )


def fetch_prompts(client: Langfuse) -> CrewPrompts:
    """Fetch every crew prompt's production version, cached by the Langfuse client."""
    texts: dict[str, str] = {}
    versions: dict[str, int] = {}
    for name in PROMPT_NAMES:
        try:
            prompt = client.get_prompt(
                name,
                label=LABEL,
                type="text",
                cache_ttl_seconds=CACHE_TTL_SECONDS,
                max_retries=MAX_RETRIES,
                fetch_timeout_seconds=FETCH_TIMEOUT_SECONDS,
            )
        except NotFoundError as exc:
            raise PromptsUnavailableError(
                f"Prompt {name!r} with label {LABEL!r} does not exist in Langfuse; run "
                "`make prompts-push` to create it"
            ) from exc
        except Exception as exc:
            raise PromptsUnavailableError(
                f"Prompt {name!r} could not be fetched from Langfuse ({exc}); check "
                "LANGFUSE_BASE_URL and the Langfuse keys"
            ) from exc
        text = str(prompt.prompt)
        _check_variables(name, text)
        texts[name] = to_crewai(text)
        versions[name] = prompt.version
    return CrewPrompts(texts=texts, versions=versions)


def _check_variables(name: str, text: str) -> None:
    """Reject texts CrewAI could not interpolate, before the crew starts."""
    required = TASK_VARIABLES if name == TASK_PROMPT else set()
    found = set(_LANGFUSE_VARIABLE.findall(text))
    if unknown := found - required:
        raise PromptsUnavailableError(
            f"Prompt {name!r} in Langfuse uses unknown variables: {', '.join(sorted(unknown))}"
        )
    # Without {{message}} the crew would run without the customer's text and still answer.
    if missing := required - found:
        raise PromptsUnavailableError(
            f"Prompt {name!r} in Langfuse must use the variables: {', '.join(sorted(missing))}"
        )
    rest = _LANGFUSE_VARIABLE.sub("", text)
    if "{" in rest or "}" in rest:
        raise PromptsUnavailableError(
            f"Prompt {name!r} in Langfuse contains a single brace; variables are {{{{name}}}}"
        )
