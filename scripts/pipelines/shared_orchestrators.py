"""Shared helpers for the enrich_* pipeline orchestrators (P1 in BACKLOG.md).

Centralises the append-only CSV log pattern that was previously duplicated
across enrich_abstracts.py, enrich_pdfs.py, and enrich_dois.py. Adding a
log column now requires one edit (in log_schemas.py) plus updating the
``LOG_FIELDS`` alias in the relevant script — not three parallel edits.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path


class LogManager:
    """Append-only CSV run log with resume / done-tracking support.

    Parameters
    ----------
    log_path:
        Path to the CSV file (created on first write if absent).
    fields:
        Column list — passed verbatim to ``csv.DictWriter``.  Import
        from ``log_schemas`` rather than defining inline.
    done_status:
        When given, ``already_done()`` returns the set of *done_key*
        values whose latest row has this ``status`` value.  Pass
        ``None`` (default) for orchestrators that don't skip already-
        processed items (e.g. enrich_dois in validate-only mode).
    done_key:
        Column to key the done-set on (default ``"doi"``).
    """

    def __init__(
        self,
        log_path: str | Path,
        fields: list[str],
        *,
        done_status: str | None = None,
        done_key: str = "doi",
    ) -> None:
        self.path = str(log_path)
        self.fields = fields
        self._done_status = done_status
        self._done_key = done_key

    def already_done(self) -> set[str]:
        """Return the set of *done_key* values that are already complete.

        Reads the existing log (if any) and collects every row whose
        ``status`` equals *done_status*.  Returns an empty set when no
        log exists or when *done_status* was not supplied.
        """
        if not self._done_status or not os.path.exists(self.path):
            return set()
        with open(self.path, newline="", encoding="utf-8") as fh:
            return {
                (row.get(self._done_key) or "").strip().lower()
                for row in csv.DictReader(fh)
                if row.get("status") == self._done_status
            }

    def open_writer(self) -> tuple:
        """Open the log for appending.  Write the header row if the file
        is new.

        Returns
        -------
        (fh, writer)
            The raw file handle (caller must close it) and a
            ``csv.DictWriter`` pre-configured with *fields*.  The same
            tuple shape the old ``_open_log()`` helpers returned, so
            existing call sites need no structural change.
        """
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        is_new = not os.path.exists(self.path)
        fh = open(self.path, "a", newline="", encoding="utf-8")  # noqa: SIM115
        writer = csv.DictWriter(fh, fieldnames=self.fields)
        if is_new:
            writer.writeheader()
        return fh, writer
