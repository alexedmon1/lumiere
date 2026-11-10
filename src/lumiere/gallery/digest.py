"""An analysis's significance summary, from its tables' standard terms (Esprit's results plan, 5b.2).

What source-lightbox's digests showed, read from declared fields instead of column and file
names, so it works for any producer and modality: for each declared contrast, each test
(``measure`` and every facet) with a significant result, at every level the analysis
reports. The overall level is a contract table with no ``element`` column (EEG's
whole-brain row, a TBSS skeleton's test); each table with an ``element`` column is a level
of its own, named by the column's ``ElementName`` (0.4.2: ROI, region, electrode, edge,
cluster), else "element".

A row counts as significant by its ``significant`` column, else by its ``p_value`` below the
alpha its family or correction states (0.05 when none does). An equivalence row says two
things: whether it concludes equivalence (``equivalent``), counted per contrast, and whether
the difference is significant, listed like any other result (the group still differs).
A table whose element column names no ``ElementName`` is a level of its own, so two
unnamed tables (regions and ROIs, say) are never merged. The summary is computed when
the gallery is built, from whole tables (the page embeds at most ``MAX_ROWS`` of each), and
the page draws it. Standard library only.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ..check import read_table

#: Element names listed per test and level; the rest are counted.
NAMED = 8
#: Effect measures that have no direction: shown without an arrow.
UNSIGNED = {"eta2", "eta2_partial", "omega2", "omega2_partial", "epsilon2", "f2", "r2", "auc", "accuracy",
            "balanced_accuracy", "cramers_v", "w"}
CONTRACT = ("tests", "clusters", "elements")
_TRUE = {"true", "1", "yes"}


def _float(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in _TRUE


def _alpha(analysis: dict, family: str | None) -> float:
    inf = analysis.get("inference") or {}
    for f in inf.get("families") or []:
        if family is not None and f.get("id") == family and _float(f.get("alpha")) is not None:
            return float(f["alpha"])
    corr = inf.get("correction") or {}
    if _float(corr.get("alpha")) is not None:
        return float(corr["alpha"])
    return 0.05


class _Table:
    """One contract table's standard columns."""

    def __init__(self, folder: Path, entry: dict):
        self.path = folder / entry["path"]
        self.entry = entry
        try:
            self.columns: dict[str, dict] = json.loads(self.path.with_suffix(".json").read_text())
        except (OSError, ValueError):
            self.columns = {}
        self.std: dict[str, str] = {}
        self.facets: list[tuple[str, str]] = []           # (name, column), in the table's order
        for col, meta in self.columns.items():
            term = (meta or {}).get("Standard") if isinstance(meta, dict) else None
            if term == "facet":
                self.facets.append((meta.get("FacetName") or "facet", col))
            elif term and term not in self.std:
                self.std[term] = col
        elem = self.std.get("element")
        self.name = (self.columns.get(elem) or {}).get("ElementName") if elem else None
        #: the level's key: "" overall, the element name, or the table's own path when unnamed
        self.level = "" if not elem else (self.name or f"element:{entry['path']}")
        eff = self.columns.get(self.std.get("effect_size", ""), {})
        self.effect_measure = eff.get("EffectMeasure")
        sig = self.columns.get(self.std.get("significant", ""), {})
        self.sig_alpha = _float(sig.get("Alpha"))
        self.p_kind = self.columns.get(self.std.get("p_value", ""), {}).get("PKind")

    def get(self, row: dict, term: str) -> str:
        col = self.std.get(term)
        return row.get(col, "") if col else ""


def _row_effect(t: _Table, row: dict) -> tuple[float | None, str | None]:
    measure = t.effect_measure
    if measure == "per_row":
        measure = t.get(row, "effect_measure") or None
    return _float(t.get(row, "effect_size")), measure


def _significant(t: _Table, row: dict, analysis: dict) -> bool:
    if t.std.get("significant"):
        return _truthy(t.get(row, "significant"))
    p = _float(t.get(row, "p_value"))
    alpha = t.sig_alpha or _alpha(analysis, t.get(row, "correction_family") or None)
    return p is not None and p < alpha


#: A row's extent, by the term that gives it, and the word for its unit.
EXTENT_TERMS = (("n_edges", "edge"), ("n_voxels", "voxel"), ("volume_mm3", "mm³"))
#: observed_direction words read as up, down or mixed (a network's edges going both ways).
DIRECTION_WORDS = {"increase": "up", "higher": "up", "up": "up", "positive": "up",
                   "decrease": "down", "lower": "down", "down": "down", "negative": "down",
                   "mixed": "mixed", "both": "mixed"}


def _extent(t: Any, row: dict) -> dict:
    """How big a significant element is (a component's edges, a cluster's voxels) and which way it
    went, where its table says: what a cluster or network row shows in place of an effect size."""
    out: dict = {}
    for term, unit in EXTENT_TERMS:
        size = _float(t.get(row, term))
        if size is not None:
            out["extent"] = {"value": size, "unit": unit}
            break
    word = (t.get(row, "observed_direction") or "").strip().lower()
    if word in DIRECTION_WORDS:
        out["direction"] = DIRECTION_WORDS[word]
    return out


def digest(folder: Path, analysis: dict) -> dict | None:
    """The analysis's significance summary for the gallery page, or None when its tables
    declare no contrast to summarize (no ``contrast`` column and no declared ``contrasts``)."""
    folder = Path(folder)
    tables = [_Table(folder, e) for e in analysis.get("tables") or []
              if e.get("role") in CONTRACT and (folder / e.get("path", "")).is_file()]
    tables = [t for t in tables if t.std.get("effect_size") or t.std.get("significant") or t.std.get("p_value")]
    declared = {c["id"]: c for c in analysis.get("contrasts") or [] if isinstance(c, dict) and c.get("id")}
    if not tables or not (declared or any(t.std.get("contrast") for t in tables)):
        return None

    # levels: the overall one first, then each element level in the order its tables are listed
    levels: list[dict] = []
    for t in sorted(tables, key=lambda t: t.level != ""):
        if t.level not in [lv["id"] for lv in levels]:
            levels.append({"id": t.level, "name": None if t.level == "" else (t.name or "element")})

    order = list(declared)
    labels: dict[str, str] = {}
    kinds: dict[str, str] = {}
    tested: dict[str, set] = {}            # contrast -> test keys seen
    equivalent: dict[str, set] = {}        # contrast -> test keys concluding equivalence (any level)
    hits: dict[tuple, dict] = {}           # (contrast, key) -> {"label", "levels": {level: [rows]}}
    p_kinds: set[str] = set()
    for t in tables:
        if t.p_kind:
            p_kinds.add(t.p_kind)
        _, rows = read_table(t.path)
        for row in rows:
            cid = t.get(row, "contrast") or ""
            if cid not in declared and cid not in order:
                order.append(cid)
            if cid and cid not in labels and t.get(row, "contrast_label"):
                labels[cid] = t.get(row, "contrast_label")
            kind = (declared.get(cid) or {}).get("kind") or ""
            if not kind and t.get(row, "test_kind") == "equivalence":
                kind = "equivalence"
            kinds.setdefault(cid, kind)
            facets = [(name, row.get(col, "")) for name, col in t.facets]
            measure = t.get(row, "measure")
            key = (measure, *(v for _, v in facets))
            tested.setdefault(cid, set()).add(key)
            if t.std.get("equivalent") and _truthy(t.get(row, "equivalent")):
                equivalent.setdefault(cid, set()).add(key)
            if not _significant(t, row, analysis):
                continue
            if t.level and not t.get(row, "element"):
                continue                   # a row of an element table that names no element (its omnibus)
            effect, effect_measure = _row_effect(t, row)
            p = _float(t.get(row, "p_value"))
            hit = hits.setdefault((cid, key), {
                "measure": measure, "facets": [v for _, v in facets if v], "levels": {}})
            hit["levels"].setdefault(t.level, []).append({
                "element": t.get(row, "element") if t.level else None,
                "effect": effect, "effect_measure": effect_measure, "p": p,
                "signed": (effect_measure or "").lower() not in UNSIGNED,
                **_extent(t, row),
            })

    contrasts = []
    strongest = None
    counts = {lv["id"]: 0 for lv in levels}
    for cid in order:
        c = declared.get(cid) or {}
        tests = []
        for (hc, _key), hit in hits.items():
            if hc != cid:
                continue
            out_levels = []
            peak = 0.0
            for lv in (lv["id"] for lv in levels):
                rows = hit["levels"].get(lv)
                if not rows:
                    continue
                rows.sort(key=lambda r: -abs(r["effect"] or 0.0))
                peak = max(peak, abs(rows[0]["effect"] or 0.0))
                counts[lv] += len(rows)
                out_levels.append({"level": lv, "n": len(rows), "rows": rows[:NAMED] if lv else rows[:1]})
                if lv == "" and kinds.get(cid) not in ("omnibus", "equivalence") and rows[0]["signed"] \
                        and rows[0]["effect"] is not None \
                        and (strongest is None or abs(rows[0]["effect"]) > abs(strongest["row"]["effect"])):
                    strongest = {"contrast": cid, "measure": hit["measure"], "facets": hit["facets"],
                                 "row": rows[0]}
            tests.append({"measure": hit["measure"], "facets": hit["facets"], "levels": out_levels, "peak": peak})
        tests.sort(key=lambda x: -x["peak"])
        contrasts.append({
            "id": cid, "label": c.get("label") or labels.get(cid) or cid or "(one test)",
            "tier": c.get("tier"), "kind": kinds.get(cid) or c.get("kind") or "contrast",
            "role": c.get("role"), "gate_on": c.get("gate_on") or [],
            "group_a": c.get("group_a"), "group_b": c.get("group_b"),
            "n_tests": len(tested.get(cid, ())), "n_significant": len(tests), "tests": tests,
            "n_equivalent": len(equivalent.get(cid, ())),
        })
    return {
        "levels": levels, "counts": counts, "strongest": strongest, "contrasts": contrasts,
        "p_kind": next(iter(p_kinds)) if len(p_kinds) == 1 else ("per_family" if p_kinds else None),
        "named": NAMED,
    }
