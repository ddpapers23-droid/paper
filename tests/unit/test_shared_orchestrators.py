"""Unit tests for LogManager (shared_orchestrators.py) and enrich log schemas (P1 + P7)."""

from __future__ import annotations

from pathlib import Path

from log_schemas import ABSTRACT_LOG_FIELDS, DOI_LOG_FIELDS, PDF_LOG_FIELDS
from shared_orchestrators import LogManager

# ---------------------------------------------------------------------------
# log_schemas — schema contracts
# ---------------------------------------------------------------------------


def test_abstract_and_pdf_log_fields_are_canonical() -> None:
    """Both logs must share the same six-column structure in the same order
    so they are diff-friendly side-by-side. The old enrich_pdfs.py inline
    definition had source/status swapped — this pins the canonical form."""
    assert ABSTRACT_LOG_FIELDS == PDF_LOG_FIELDS
    assert ABSTRACT_LOG_FIELDS == [
        "run_date", "item_key", "doi", "title", "source", "status",
    ]


def test_doi_log_fields_includes_comparison_columns() -> None:
    """DOI log carries Zotero vs Crossref comparison columns so the CSV
    is an audit trail for applied / rejected DOI edits."""
    assert "zotero_doi" in DOI_LOG_FIELDS
    assert "crossref_doi" in DOI_LOG_FIELDS
    assert "status" in DOI_LOG_FIELDS


def test_all_enrich_schemas_start_with_run_date_item_key() -> None:
    """Provenance columns must be first so spreadsheet / grep workflows
    that read the first two columns get consistent output."""
    for schema in (ABSTRACT_LOG_FIELDS, PDF_LOG_FIELDS, DOI_LOG_FIELDS):
        assert schema[0] == "run_date", schema
        assert schema[1] == "item_key", schema


# ---------------------------------------------------------------------------
# LogManager — already_done
# ---------------------------------------------------------------------------


def test_already_done_returns_empty_when_log_missing(tmp_path: Path) -> None:
    m = LogManager(tmp_path / "nope.csv", ABSTRACT_LOG_FIELDS, done_status="updated")
    assert m.already_done() == set()


def test_already_done_returns_empty_when_no_done_status(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS)  # no done_status
    fh, w = m.open_writer()
    w.writerow({k: "" for k in ABSTRACT_LOG_FIELDS} | {"doi": "10.1/x", "status": "updated"})
    fh.close()
    assert m.already_done() == set()  # no filter applied


def test_already_done_filters_by_status(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS, done_status="updated")
    fh, w = m.open_writer()
    w.writerow({k: "" for k in ABSTRACT_LOG_FIELDS} | {"doi": "10.1/done", "status": "updated"})
    w.writerow({k: "" for k in ABSTRACT_LOG_FIELDS} | {"doi": "10.1/fail", "status": "error"})
    fh.close()
    assert m.already_done() == {"10.1/done"}


def test_already_done_normalises_doi_case(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS, done_status="updated")
    fh, w = m.open_writer()
    w.writerow({k: "" for k in ABSTRACT_LOG_FIELDS} | {"doi": "10.1016/J.UPPER", "status": "updated"})
    fh.close()
    assert "10.1016/j.upper" in m.already_done()


def test_already_done_uses_custom_done_key(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS, done_status="updated", done_key="item_key")
    fh, w = m.open_writer()
    w.writerow({k: "" for k in ABSTRACT_LOG_FIELDS} | {"item_key": "KEY1", "doi": "10.1/x", "status": "updated"})
    fh.close()
    assert "key1" in m.already_done()


# ---------------------------------------------------------------------------
# LogManager — open_writer
# ---------------------------------------------------------------------------


def test_open_writer_creates_parent_dirs(tmp_path: Path) -> None:
    log = tmp_path / "subdir" / "nested" / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS)
    fh, _ = m.open_writer()
    fh.close()
    assert log.exists()


def test_open_writer_writes_header_on_new_file(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS)
    fh, _ = m.open_writer()
    fh.close()
    lines = log.read_text().splitlines()
    assert lines[0] == ",".join(ABSTRACT_LOG_FIELDS)


def test_open_writer_appends_no_duplicate_header(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    m = LogManager(log, ABSTRACT_LOG_FIELDS)
    for _ in range(3):
        fh, w = m.open_writer()
        w.writerow({k: "v" for k in ABSTRACT_LOG_FIELDS})
        fh.close()
    lines = log.read_text().strip().splitlines()
    header_count = sum(1 for ln in lines if ln.startswith("run_date"))
    assert header_count == 1, "header should appear exactly once"
    assert len(lines) == 4  # 1 header + 3 data rows


def test_open_writer_returns_dictwriter_compatible_with_fields(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    fh, writer = LogManager(log, PDF_LOG_FIELDS, done_status="attached").open_writer()
    writer.writerow({"run_date": "2026-05-21", "item_key": "K1",
                     "doi": "10.1/x", "title": "T", "source": "s", "status": "attached"})
    fh.close()
    m2 = LogManager(log, PDF_LOG_FIELDS, done_status="attached")
    assert "10.1/x" in m2.already_done()
