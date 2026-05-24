#!/usr/bin/env python3
"""Pre-flight probe for academic-research skills.

Prints 'configured' if the plugin has usable credentials, 'NOT CONFIGURED'
otherwise. Skills call this before running so they can hand off to the setup
wizard on first use.

Credential sources checked in order:
  1. ~/.config/academic-research/config.toml  (local wizard output)
  2. Environment variables                     (cloud/CI sessions)

A session is considered configured if EITHER the config file exists OR the
minimum required env vars are all non-empty (ZOTERO_API_KEY + ZOTERO_GROUP
+ ANTHROPIC_API_KEY). Database-search keys (SCOPUS_API_KEY etc.) are not
required here — they are checked per-script at runtime.

Kept as a script (not an inline `python -c`) so the wizard's existing
`Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/**)` allow rule covers it —
no per-session permission prompt at skill load time.
"""
from __future__ import annotations

import os
from pathlib import Path

_CONFIG_FILE = Path.home() / ".config" / "academic-research" / "config.toml"

_REQUIRED_ENV_VARS = (
    "ZOTERO_API_KEY",
    "ZOTERO_GROUP",
    "ANTHROPIC_API_KEY",
)


def _env_configured() -> bool:
    return all(os.environ.get(v, "").strip() for v in _REQUIRED_ENV_VARS)


if _CONFIG_FILE.is_file() or _env_configured():
    print("configured")
else:
    print("NOT CONFIGURED")
