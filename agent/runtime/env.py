"""Loads ANTHROPIC_API_KEY from the repo-root .env file, if present.

No python-dotenv dependency — that's not in the approved dependency list —
so this is a deliberately minimal parser for the one variable this project
needs. The key never leaves the process environment.
"""

from __future__ import annotations

import os
from pathlib import Path

import anthropic

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_dotenv_if_present() -> None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def make_client() -> anthropic.Anthropic:
    """Build the Anthropic client this project uses everywhere.

    Some Console API keys are identity-linked and require an
    anthropic-workspace-id header naming which workspace the request acts
    in; ANTHROPIC_WORKSPACE_ID in .env carries that when the key needs it.
    Plain project-scoped keys don't need this and the header is simply
    omitted.
    """
    load_dotenv_if_present()
    headers = {}
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id
    return anthropic.Anthropic(default_headers=headers or None)
