"""Guard test: every publisher / KeySpec / source has a matching live test.

Runs on every `pytest` invocation (no marker). If a new entry is
added to `publishers.registry.DEFAULT_PUBLISHERS`, a new `KeySpec`
added to `scripts/setup/wizard.py:KEYS`, or a new fetcher class added
to `scripts/pipelines/fetchers/*.py` without a matching live test, this
test fails with an actionable message.

The policy is documented in the project memory at
`feedback_every_source_has_a_test.md`:

> Every publisher / source / API key has a live test — adding a new
> registry entry, KeySpec, or source module must ship with a matching
> live test; a default-run guard test enforces the invariant at PR
> time.

P9 migration note: the abstract / PDF source guards previously walked
`legacy/fetch_abstracts.py` and `legacy/attach_pdfs.py` for `fetch_from_*`
/ `fetch_*_pdf` function names. They now walk `fetchers/*.py` and
enumerate `AbstractFetcher` / `PdfFetcher` subclasses by their `name`
class attribute. The legacy/ scripts can be deleted once no other guard
or skill references them.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))


def _load_wizard():
    spec = importlib.util.spec_from_file_location(
        "wizard", SCRIPTS_ROOT / "setup" / "wizard.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wizard"] = mod
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Publishers ↔ test_browser_publishers.py
# ---------------------------------------------------------------------------


def test_every_publisher_in_registry_has_a_known_doi() -> None:
    """test_browser_publishers.py is parametrized from the registry; the
    corresponding DOI must exist in KNOWN_DOIS."""
    from publishers.registry import DEFAULT_PUBLISHERS

    conftest = _read(REPO / "tests" / "live" / "conftest.py")
    # Parse KNOWN_DOIS keys from conftest source (not importable without
    # pytest session setup). Accept both "key": and 'key':
    known_keys = set(re.findall(r"[\"']([a-zA-Z_0-9]+)[\"']\s*:\s*\"10\.", conftest))

    missing = []
    for pub_key in DEFAULT_PUBLISHERS:
        if pub_key not in known_keys:
            missing.append(pub_key)
    assert not missing, (
        f"Registry publishers without a KNOWN_DOIS entry: {missing}. "
        f"Add DOIs to tests/live/conftest.py so test_browser_publishers.py "
        f"can exercise them."
    )


# ---------------------------------------------------------------------------
# KeySpecs ↔ test_auth_workflows.py
# ---------------------------------------------------------------------------


def test_every_keyspec_has_an_auth_test() -> None:
    """Every KeySpec in wizard.py:KEYS has a test in test_auth_workflows.py."""
    wizard = _load_wizard()
    env_vars = {spec.env_var for spec in wizard.KEYS}

    auth_tests = _read(REPO / "tests" / "live" / "test_auth_workflows.py")

    missing = []
    for env_var in env_vars:
        # The auth test either references the env var name directly or in a
        # comment/docstring. Accept any mention as sufficient.
        if env_var not in auth_tests:
            missing.append(env_var)
    assert not missing, (
        f"KeySpecs without a matching test in test_auth_workflows.py: "
        f"{missing}. Add a test_auth_{{name}} function that calls the "
        f"matching _verify_* helper."
    )


# ---------------------------------------------------------------------------
# Helpers — enumerate fetcher subclasses from source files
# ---------------------------------------------------------------------------

FETCHERS_DIR = REPO / "scripts" / "pipelines" / "fetchers"

# Files that define base classes or helpers, not concrete sources.
_FETCHER_NON_SOURCES = frozenset({
    "base.py", "_title_match.py", "doi_resolver.py", "library_resolver.py",
    "__init__.py",
})


def _fetcher_names(base_cls: str) -> list[tuple[str, str]]:
    """Walk fetchers/*.py and return (filename, name) for every class that
    lists *base_cls* in its inheritance list and declares a ``name`` attr.

    Parses source with regex — no imports, no side effects — so this works
    in the unit-test environment where optional dependencies are absent.
    The ``fetchers/browser/`` sub-package is intentionally excluded;
    browser publisher coverage is enforced by the registry guard above.
    """
    results: list[tuple[str, str]] = []
    cls_re = re.compile(
        rf"^class\s+\w+\s*\([^)]*{re.escape(base_cls)}[^)]*\)\s*:",
        re.MULTILINE,
    )
    name_re = re.compile(r'^\s{4}name\s*=\s*"([^"]+)"', re.MULTILINE)
    for py_file in sorted(FETCHERS_DIR.glob("*.py")):
        if py_file.name in _FETCHER_NON_SOURCES:
            continue
        src = py_file.read_text(encoding="utf-8")
        for cls_match in cls_re.finditer(src):
            # Search for the name attribute in the first 400 chars of the
            # class body (before any method definitions).
            snippet = src[cls_match.end(): cls_match.end() + 400]
            name_match = name_re.search(snippet)
            if name_match:
                results.append((py_file.name, name_match.group(1)))
    return results


# ---------------------------------------------------------------------------
# Abstract sources ↔ test_abstract_endpoints.py
# ---------------------------------------------------------------------------

# Maps fetcher source name → expected live-test function name.
# None = explicitly not a source requiring its own abstract test
# (e.g. PDF-only sources that inherit PdfFetcher but not AbstractFetcher).
# Add a new row whenever a new AbstractFetcher subclass is added.
_ABSTRACT_ALIAS: dict[str, str | None] = {
    "core": "test_core_abstract",
    "crossref": "test_crossref_abstract",
    "europe_pmc": "test_europe_pmc_abstract",
    "openalex": "test_openalex_grobid_abstract",
    "sciencedirect": "test_sciencedirect_abstract",
    "scopus": "test_scopus_abstract",
    "semantic_scholar": "test_semantic_scholar_abstract",
    "wos": "test_wos_abstract_direct_doi",
}


def test_every_abstract_source_has_a_live_test() -> None:
    """Every AbstractFetcher subclass in fetchers/*.py has a matching live test.

    The source list is derived from the refactored fetcher classes (P9),
    not from legacy/fetch_abstracts.py. Alias map lives in
    _ABSTRACT_ALIAS above — update it when a new fetcher is added.
    """
    sources = _fetcher_names("AbstractFetcher")
    abstract_tests = _read(REPO / "tests" / "live" / "test_abstract_endpoints.py")

    missing = []
    for filename, name in sources:
        if name not in _ABSTRACT_ALIAS:
            missing.append(
                f"{filename}:{name} not in _ABSTRACT_ALIAS — add an entry "
                f"in test_live_coverage.py (map to test name or None if "
                f"no abstract endpoint)."
            )
            continue
        expected = _ABSTRACT_ALIAS[name]
        if expected and expected not in abstract_tests:
            missing.append(
                f"{filename}:{name} → expected {expected} in "
                f"test_abstract_endpoints.py"
            )
    assert not missing, (
        f"AbstractFetcher sources without a matching live test: {missing}. "
        f"Add a test to tests/live/test_abstract_endpoints.py and update "
        f"_ABSTRACT_ALIAS in test_live_coverage.py."
    )


# ---------------------------------------------------------------------------
# PDF sources ↔ test_pdf_endpoints.py
# ---------------------------------------------------------------------------

# Maps fetcher source name → expected live-test function name.
# None = explicitly exempt (generic helper / not a standalone source).
# Add a new row whenever a new PdfFetcher subclass is added.
_PDF_ALIAS: dict[str, str | None] = {
    "core": "test_core_pdf_download_url",
    "crossref": "test_crossref_tdm_link_present",
    "europe_pmc": "test_europe_pmc_pdf",
    "openalex": "test_openalex_content_api_returns_pdf_bytes",
    "sciencedirect": "test_elsevier_sciencedirect_reachable",
    "pubmed_central": "test_pmc_doi_to_pmcid_resolves",
    "springer": "test_springer_reachable",
    "unpaywall": "test_unpaywall_returns_pdf_url",
    "wiley": "test_wiley_tdm_downloads_pdf",
}


def test_every_pdf_source_has_a_live_test() -> None:
    """Every PdfFetcher subclass in fetchers/*.py has a matching live test.

    The source list is derived from the refactored fetcher classes (P9),
    not from legacy/attach_pdfs.py. Alias map lives in _PDF_ALIAS above.
    """
    sources = _fetcher_names("PdfFetcher")
    pdf_tests = _read(REPO / "tests" / "live" / "test_pdf_endpoints.py")

    missing = []
    for filename, name in sources:
        if name not in _PDF_ALIAS:
            missing.append(
                f"{filename}:{name} not in _PDF_ALIAS — add an entry in "
                f"test_live_coverage.py (map to test name or None if exempt)."
            )
            continue
        expected = _PDF_ALIAS[name]
        if expected and expected not in pdf_tests:
            missing.append(
                f"{filename}:{name} → expected {expected} in "
                f"test_pdf_endpoints.py"
            )
    assert not missing, (
        f"PdfFetcher sources without a matching live test: {missing}. "
        f"Add a test to tests/live/test_pdf_endpoints.py and update "
        f"_PDF_ALIAS in test_live_coverage.py."
    )
