"""The results specification: what an analysis writes so anyone can read it.

See docs/RESULTS_SPEC.md (the specification) and docs/RESULTS_PRODUCERS.md (how
neurofaune, neurovrai, source-analytics and study scripts meet it). Standard library only,
so it runs where no producer's stack is installed: ``python -m neurobox check <folder>``.
neurofaune re-exports it as ``neurofaune.results``, where it lived until 2026-11.
"""
from .check import Report, check, check_analysis, find_analyses, read_table
from .spec import SPEC, SPEC_VERSION, STANDARD_TERMS
from .write import (NonConformingResults, columns_for, provenance,
                    write_analysis, write_columns)

__all__ = ["SPEC", "SPEC_VERSION", "STANDARD_TERMS", "Report", "check", "check_analysis",
           "find_analyses", "read_table", "NonConformingResults", "columns_for", "provenance",
           "write_analysis", "write_columns"]
