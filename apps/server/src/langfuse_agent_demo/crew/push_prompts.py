"""Load the crew's prompts from ``prompts.toml`` into Langfuse prompt management.

Run from ``apps/server`` with the Langfuse keys in ``.env``::

    make prompts-push                # create missing prompts
    make prompts-push ARGS=--force   # also reset edited prompts to the file

Each missing prompt is created as a text prompt labelled ``production``. A prompt that already
exists is left alone, so edits made in Langfuse survive; with ``--force``, a prompt whose
``production`` text differs from the file gets a new ``production`` version with the file text.
"""

import argparse
import logging
from collections.abc import Mapping, Sequence

from langfuse import Langfuse
from langfuse.api import NotFoundError

from .prompts import LABEL, PromptsUnavailableError, langfuse_client, load_prompt_file


def push_prompts(client: Langfuse, texts: Mapping[str, str], force: bool = False) -> dict[str, str]:
    """Push each prompt; returns name -> created / unchanged / differs / updated / error: ..."""
    results: dict[str, str] = {}
    for name, text in texts.items():
        try:
            current = client.get_prompt(
                name, label=LABEL, type="text", cache_ttl_seconds=0, max_retries=0
            )
        except NotFoundError:
            current = None
        except Exception as exc:
            results[name] = f"error: {exc}"
            continue
        if current is not None and current.prompt == text:
            results[name] = "unchanged"
        elif current is not None and not force:
            results[name] = "differs"
        else:
            try:
                client.create_prompt(
                    name=name,
                    prompt=text,
                    labels=[LABEL],
                    type="text",
                    commit_message="make prompts-push",
                )
            except Exception as exc:
                results[name] = f"error: {exc}"
                continue
            results[name] = "created" if current is None else "updated"
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="give prompts whose Langfuse text differs from the file a new production version",
    )
    args = parser.parse_args(argv)
    # The SDK logs a warning for every prompt not found yet; results are printed below instead.
    logging.getLogger("langfuse").setLevel(logging.ERROR)
    try:
        client = langfuse_client()
    except PromptsUnavailableError as exc:
        print(exc)
        return 1
    results = push_prompts(client, load_prompt_file(), force=args.force)
    client.flush()
    for name, result in results.items():
        print(f"{name}: {result}")
    if "differs" in results.values():
        print("Prompts marked 'differs' were edited in Langfuse and kept; use --force to reset.")
    return 1 if any(result.startswith("error") for result in results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
