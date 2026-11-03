"""Conformance checker for the results specification (docs/RESULTS_SPEC.md §7).

``check(path)`` finds every analysis folder under ``path`` and returns one
:class:`Report` per folder: the JSON files against the schemas, every listed file
present and inside the folder, every table against its column dictionary, the
standard terms and their qualifiers, the reporting contract (§6), from 0.3 the
minimum detectable effect (§5.1), and from 0.4 the EEG extensions, correction families,
equivalence, Bayesian results, the smallest effect of interest and the new figure, decision,
map and design fields (§3.3-§3.5, §5.2-§5.6).

Standard library only.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from ._schema import load_schema, validate
from .spec import (ANALYSIS_JSON, CONTRACT_ROLES, MODALITIES, NOT_COMPUTED, PER_FAMILY, PER_ROW,
                   PER_SUBGROUP, PROVENANCE_JSON, QUALIFIERS_SINCE, READS, SPEC, SPEC_VERSION,
                   STANDARD_TERMS, TABLE_SUFFIXES, TERMS_SINCE, canonical_measure, domain_vocabulary,
                   entry_modalities, id_problem, measure_vocabulary, run_id_problem, task_problem,
                   valid_axes, version_tuple)

#: Analysis types whose tests are voxelwise, so a test row must state its extent.
VOXELWISE = ("tbss", "vbm", "tbm", "voxelwise", "fixel")
_TRUE, _FALSE = {"true", "True", "TRUE", "1"}, {"false", "False", "FALSE", "0"}


@dataclass
class Report:
    folder: Path
    id: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: what the cross-run check needs: version, modality, analysis_type, run, supersedes, tests
    meta: dict = field(default_factory=dict, repr=False)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def run(self) -> str | None:
        return self.meta.get("run")

    def as_dict(self) -> dict:
        return {"folder": str(self.folder), "id": self.id, "run": self.run, "ok": self.ok,
                "errors": self.errors, "warnings": self.warnings}


# ----------------------------------------------------------------- finding ---
def is_analysis(folder: Path) -> bool:
    f = Path(folder) / ANALYSIS_JSON
    if not f.is_file():
        return False
    try:
        return json.loads(f.read_text()).get("spec") == SPEC
    except (OSError, ValueError, AttributeError):
        return False


def find_analyses(root: Path) -> list[Path]:
    """Every analysis folder at or under ``root``, sorted."""
    root = Path(root)
    if is_analysis(root):
        return [root]
    return sorted(p.parent for p in root.rglob(ANALYSIS_JSON) if is_analysis(p.parent))


# ------------------------------------------------------------------ helpers ---
def _load_json(path: Path, rep: Report) -> dict | None:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        rep.errors.append(f"{path.name}: missing")
        return None
    except (OSError, ValueError) as exc:
        rep.errors.append(f"{path.name}: not valid JSON ({exc})")
        return None
    if not isinstance(value, dict):
        rep.errors.append(f"{path.name}: must be a JSON object")
        return None
    return value


def _inside(folder: Path, rel: str, what: str, rep: Report) -> Path | None:
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or "\\" in rel:
        rep.errors.append(f"{what} {rel!r}: paths must be relative and stay inside the folder")
        return None
    full = folder / rel
    if not full.exists():
        rep.errors.append(f"{what} {rel!r}: listed but not on disk")
        return None
    return full


def _version_ok(version: str, rep: Report) -> tuple[int, int] | None:
    """The folder's (major, minor) when this checker reads it, else None (and an error)."""
    got = version_tuple(version)
    if got is None:
        rep.errors.append(f"spec_version {version!r} is not semver")
        return None
    if got not in READS:
        rep.errors.append(f"spec_version {version} is not readable by checker {SPEC_VERSION}")
        return None
    return got


def _rules_0_2(analysis: dict, rep: Report) -> None:
    """What 0.2 adds (RESULTS_SPEC.md §3.1): identity and vocabulary."""
    modality, atype = analysis.get("modality"), analysis.get("analysis_type")
    if modality is None:
        rep.errors.append(f"{ANALYSIS_JSON}: modality is required from 0.2 (one of {', '.join(MODALITIES)})")
    elif modality not in MODALITIES:
        rep.errors.append(f"{ANALYSIS_JSON}: modality {modality!r} is not one of {', '.join(MODALITIES)}")
    mods = analysis.get("modalities")
    if modality == "multimodal":
        if not mods:
            rep.errors.append(f"{ANALYSIS_JSON}: a multimodal analysis lists its modalities")
        else:
            bad = [m for m in mods if m not in MODALITIES or m == "multimodal"]
            if bad:
                rep.errors.append(f"{ANALYSIS_JSON}: modalities {bad} are not modalities")
    elif mods:
        rep.errors.append(f"{ANALYSIS_JSON}: modalities is for multimodal analyses only")
    if isinstance(analysis.get("id"), str) and isinstance(modality, str) and isinstance(atype, str):
        why = id_problem(analysis["id"], modality, atype)
        if why:
            rep.errors.append(f"{ANALYSIS_JSON}: id {analysis['id']!r} {why}")
    run = analysis.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        rep.errors.append(f"{ANALYSIS_JSON}: run is required from 0.2 ({{id, label, supersedes}}; §3.2)")
    else:
        why = run_id_problem(run["id"])
        if why:
            rep.errors.append(f"{ANALYSIS_JSON}: run id {run['id']!r} {why}")
        if run["id"] in (run.get("supersedes") or []):
            rep.errors.append(f"{ANALYSIS_JSON}: run {run['id']!r} supersedes itself")
    vocab = measure_vocabulary()
    own = set(mods or []) if modality == "multimodal" else {modality}
    for m in analysis.get("measures") or []:
        canon, exact = canonical_measure(m, vocab)
        if canon is None:
            rep.warnings.append(f"{ANALYSIS_JSON}: measure {m!r} is not in the measure vocabulary "
                                "(neurobox/vocab/measures.json, in neurobox-dev) -- add it there")
        elif not exact:
            rep.errors.append(f"{ANALYSIS_JSON}: measure {m!r} is written {canon!r} in the vocabulary")
        elif not own & set(entry_modalities(vocab[canon])):
            rep.warnings.append(f"{ANALYSIS_JSON}: measure {m!r} is a {'/'.join(entry_modalities(vocab[canon]))} "
                                f"measure, in a {modality} analysis")


def _v(version: tuple[int, int]) -> str:
    return f"{version[0]}.{version[1]}"


def features_0_4(analysis: dict) -> list[str]:
    """The 0.4 features an analysis.json uses (for refusing them in older folders)."""
    used = [k for k in ("domain", "task", "atlas") if k in analysis]
    if analysis.get("modality") == "eeg" or "eeg" in (analysis.get("modalities") or []):
        used.append("modality 'eeg'")
    if analysis.get("analysis_type") in ("sensor", "vertex", "directed"):
        used.append(f"analysis_type {analysis['analysis_type']!r}")
    design = analysis.get("design") if isinstance(analysis.get("design"), dict) else {}
    used += [f"design.{k}" for k in ("sessions", "timepoints") if k in design]
    if "equivalence" in (design.get("test_kinds") or []):
        used.append("test kind 'equivalence'")
    inference = analysis.get("inference") if isinstance(analysis.get("inference"), dict) else {}
    if "families" in inference:
        used.append("inference.families")
    if isinstance(inference.get("correction"), dict) and "method" in inference["correction"]:
        used.append("inference.correction.method")
    effect = analysis.get("effect") if isinstance(analysis.get("effect"), dict) else {}
    if "sesoi" in effect:
        used.append("effect.sesoi")
    if effect.get("measure") == PER_ROW:
        used.append(f"effect.measure {PER_ROW!r}")
    for kind, keys in (("tables", ("threshold",)), ("maps", ("space_derivation",)),
                       ("figures", ("facets", "kind", "shows", "headline", "drawn_by"))):
        for item in analysis.get(kind) or []:
            if isinstance(item, dict):
                used += [f"{kind}[].{k}" for k in keys if k in item]
    decision = analysis.get("decision") if isinstance(analysis.get("decision"), dict) else {}
    used += [f"decision.{k}" for k in ("calibration", "rests_on") if k in decision]
    return sorted(set(used))


def _families(analysis: dict) -> dict[str, dict]:
    inference = analysis.get("inference") if isinstance(analysis.get("inference"), dict) else {}
    return {f["id"]: f for f in inference.get("families") or [] if isinstance(f, dict) and f.get("id")}


def _rules_inference(analysis: dict, version: tuple[int, int] | None, rep: Report) -> None:
    """One correction (every version), or from 0.4 correction families (§5.2): one or the other."""
    inference = analysis.get("inference")
    if not isinstance(inference, dict):
        return
    has_corr, has_fams = "correction" in inference, "families" in inference
    if version is None or version < (0, 4):
        if not has_corr:
            rep.errors.append(f"{ANALYSIS_JSON}.inference: missing required field 'correction'")
        return
    if has_corr == has_fams:
        rep.errors.append(f"{ANALYSIS_JSON}: inference gives {'both' if has_corr else 'neither'} "
                          "'correction' and 'families' -- one correction, or the families its tests "
                          "are corrected in (§5.2)")
    ids = [f.get("id") for f in inference.get("families") or [] if isinstance(f, dict)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        rep.errors.append(f"{ANALYSIS_JSON}: correction families {dup} are declared more than once")


def _rules_0_4(analysis: dict, rep: Report) -> None:
    """What 0.4 adds to analysis.json (RESULTS_SPEC.md §3.1, §3.3-§3.5)."""
    modality = analysis.get("modality")
    domain = analysis.get("domain")
    if isinstance(domain, str):
        vocab = domain_vocabulary()
        own = set(analysis.get("modalities") or []) if modality == "multimodal" else {modality}
        if domain not in vocab:
            rep.warnings.append(f"{ANALYSIS_JSON}: domain {domain!r} is not in the domain vocabulary "
                                "(neurobox/vocab/domains.json) -- add it there")
        elif not own & set(entry_modalities(vocab[domain])):
            rep.warnings.append(f"{ANALYSIS_JSON}: domain {domain!r} is for "
                                f"{'/'.join(entry_modalities(vocab[domain]))}, in a {modality} analysis")
    if "task" in analysis:
        why = task_problem(analysis["task"])
        if why:
            rep.errors.append(f"{ANALYSIS_JSON}: task {analysis['task']!r} {why}")
    effect = analysis.get("effect") if isinstance(analysis.get("effect"), dict) else {}
    sesoi = effect.get("sesoi")
    if isinstance(sesoi, dict) and isinstance(sesoi.get("value"), (int, float)) and not sesoi["value"] > 0:
        rep.errors.append(f"{ANALYSIS_JSON}: effect.sesoi.value must be above 0")
    decision = analysis.get("decision") if isinstance(analysis.get("decision"), dict) else {}
    cal = decision.get("calibration")
    if isinstance(cal, dict) and isinstance(cal.get("null_rate"), (int, float)) and not 0 <= cal["null_rate"] <= 1:
        rep.errors.append(f"{ANALYSIS_JSON}: decision.calibration.null_rate {cal['null_rate']} is not in [0, 1]")
    listed = {t.get("path") for t in analysis.get("tables") or [] if isinstance(t, dict)}
    for path in decision.get("rests_on") or []:
        if path not in listed:
            rep.errors.append(f"{ANALYSIS_JSON}: decision rests on {path!r}, which is not one of its tables")
    figures = [f for f in analysis.get("figures") or [] if isinstance(f, dict)]
    if sum(1 for f in figures if f.get("headline")) > 1:
        rep.errors.append(f"{ANALYSIS_JSON}: more than one headline figure")
    for f in figures:
        if f.get("shows") and f["shows"] not in listed:
            rep.errors.append(f"figure {f.get('path')!r}: shows {f['shows']!r}, which is not one of its tables")
    has_elements = any(isinstance(t, dict) and t.get("role") == "elements" for t in analysis.get("tables") or [])
    if has_elements and any(f.get("kind") == "brain" for f in figures) and "atlas" not in analysis:
        rep.errors.append(f"{ANALYSIS_JSON}: a brain figure of an elements table needs the atlas its "
                          "elements are parcels of ('atlas': {name, version})")


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Header and rows of a spec table (CSV or TSV by extension)."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=TABLE_SUFFIXES[path.suffix.lower()])
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _in_unit(v: str) -> bool:
    x = _num(v)
    return x is not None and 0 <= x <= 1


def _mde_rules(std: dict, dictionary: dict, rows: list, role: str, version: tuple[int, int] | None,
               where: str, dict_name: str, rep: Report) -> None:
    """The minimum detectable effect (0.3, RESULTS_SPEC.md §5.1).

    A folder declaring an earlier version may not use the 0.3 terms. Where ``mde`` or
    ``mde_note`` is given: an ``mde`` is a positive number and its ``Power`` / ``Alpha``
    lie in (0, 1); a row whose ``mde`` is blank says why in ``mde_note`` ("not computed:
    ..."), and a row that gives one leaves the note empty; ``mde_percent`` is a positive
    number, only beside an ``mde``; ``se`` is a number >= 0. A 0.3 tests table with no
    ``mde`` at all is warned about, not refused: other producers adopt it at their pace.
    """
    if any(t in std for t in ("se", "mde", "mde_percent", "mde_note")) and version is not None \
            and version < (0, 3):
        return                                       # refused in _check_table
    mcol, ncol, pcol, scol = (std.get(t) for t in ("mde", "mde_note", "mde_percent", "se"))
    if role == "tests" and not (mcol or ncol) and version is not None and version >= (0, 3):
        rep.warnings.append(f"{where} (tests): no 'mde' -- the smallest effect the design detects "
                            "(§5.1); give it, or an 'mde_note' saying why not")
    if pcol and version is not None and version >= (0, 4) and not (dictionary.get(pcol) or {}).get("PercentOf"):
        rep.warnings.append(f"{dict_name}: {pcol!r} (mde_percent) should say what it is a percent of "
                            "('PercentOf', e.g. \"the controls' mean of the measure\"; §5.1)")
    if mcol:
        for q in ("Power", "Alpha"):
            x = (dictionary.get(mcol) or {}).get(q)
            if isinstance(x, (int, float)) and not 0 < x < 1:
                rep.errors.append(f"{dict_name}: {mcol!r} {q} {x} is not between 0 and 1")

    def positive(v: str, allow_zero: bool = False) -> bool:
        x = _num(v)
        return x is not None and math.isfinite(x) and (x >= 0 if allow_zero else x > 0)

    bad_mde, both, unexplained, bad_note, bad_pct, lone_pct, bad_se = [], 0, 0, [], [], 0, []
    for r in rows:
        m = r.get(mcol, "") if mcol else ""
        note = (r.get(ncol) or "").strip() if ncol else ""
        if note and not note.startswith(NOT_COMPUTED):
            bad_note.append(note)
        if m != "":
            if not positive(m):
                bad_mde.append(m)
            elif note:
                both += 1
        elif (mcol or ncol) and not note:
            unexplained += 1
        if pcol and r.get(pcol, "") != "":
            if not positive(r[pcol]):
                bad_pct.append(r[pcol])
            if m == "":
                lone_pct += 1
        if scol and r.get(scol, "") != "" and not positive(r[scol], allow_zero=True):
            bad_se.append(r[scol])
    if bad_mde:
        rep.errors.append(f"{where}: {mcol!r} (mde) is not a positive number: {bad_mde[:3]}")
    if unexplained:
        rep.errors.append(f"{where}: {unexplained} row(s) give no mde and no mde_note saying why "
                          f"(\"{NOT_COMPUTED}...\")")
    if both:
        rep.errors.append(f"{where}: {both} row(s) give an mde and an mde_note; the note is for an mde "
                          "not computed")
    if bad_note:
        rep.errors.append(f"{where}: {ncol!r} (mde_note) does not start {NOT_COMPUTED!r}: {bad_note[:3]}")
    if bad_pct:
        rep.errors.append(f"{where}: {pcol!r} (mde_percent) is not a positive number: {bad_pct[:3]}")
    if lone_pct:
        rep.errors.append(f"{where}: {lone_pct} row(s) give an mde_percent without an mde")
    if bad_se:
        rep.errors.append(f"{where}: {scol!r} (se) is not a number >= 0: {bad_se[:3]}")


# ------------------------------------------------------------------ tables ---
def _check_table(folder: Path, entry: dict, analysis: dict, rep: Report,
                 version: tuple[int, int] | None = None) -> tuple[str, dict, list] | None:
    rel = entry.get("path", "")
    path = _inside(folder, rel, "table", rep)
    if path is None:
        return None
    if path.suffix.lower() not in TABLE_SUFFIXES:
        rep.errors.append(f"table {rel!r}: must be .csv or .tsv")
        return None
    where = f"table {rel!r}"
    cols, rows = read_table(path)
    if not cols:
        rep.errors.append(f"{where}: no header row")
        return None
    dict_path = path.with_suffix(".json")
    dictionary = _load_json(dict_path, rep) if dict_path.exists() else None
    if dictionary is None:
        if not dict_path.exists():
            rep.errors.append(f"{where}: no column dictionary {dict_path.name} beside it")
        return None
    rep.errors += [f"{dict_path.name}{e[1:]}" for e in validate(dictionary, load_schema("columns"))]
    missing = [c for c in cols if c not in dictionary]
    absent = [c for c in dictionary if c not in cols]
    if missing:
        rep.errors.append(f"{where}: columns without a dictionary entry: {missing}")
    if absent:
        rep.errors.append(f"{dict_path.name}: entries for columns the table does not have: {absent}")

    std: dict[str, str] = {}
    early: dict[tuple[str, tuple[int, int]], set[str]] = {}   # (kind, version) -> names
    named_facets = [c for c, m in dictionary.items() if isinstance(m, dict) and m.get("Standard") == "facet"]
    for col, meta in dictionary.items():
        if not isinstance(meta, dict):
            continue
        for q, since in QUALIFIERS_SINCE.items():
            if q in meta and version is not None and version < since:
                early.setdefault(("qualifiers", since), set()).add(q)
        for q, value in (("PKind", PER_FAMILY), ("EffectMeasure", PER_ROW)):
            if meta.get(q) == value and version is not None and version < (0, 4):
                early.setdefault(("values", (0, 4)), set()).add(f"{q} {value}")
        term = meta.get("Standard")
        if not term:
            continue
        if term in TERMS_SINCE and version is not None and version < TERMS_SINCE[term]:
            early.setdefault(("standard terms", TERMS_SINCE[term]), set()).add(term)
        if term == "facet" and (len(named_facets) > 1 or meta.get("FacetName")):  # 0.4, §5.2
            name = meta.get("FacetName")
            if not name:
                rep.errors.append(f"{dict_path.name}: a table with several facet columns names each "
                                  f"one ('FacetName'); {col!r} has none")
                continue
            key = f"facet:{name}"
            if key in std:
                rep.errors.append(f"{dict_path.name}: facet {name!r} claimed by both {std[key]!r} and {col!r}")
            std[key] = col
            continue
        if term in std and term not in PER_SUBGROUP:
            rep.errors.append(f"{dict_path.name}: standard term {term!r} claimed by both "
                              f"{std[term]!r} and {col!r}")
            continue
        for q in STANDARD_TERMS.get(term, ()):
            if not meta.get(q):
                rep.errors.append(f"{dict_path.name}: {col!r} is {term!r} and must state {q}")
        if term in PER_SUBGROUP:                     # once per subgroup, not once per table
            key = f"{term}:{meta.get('Subgroup')}"
            if key in std:
                rep.errors.append(f"{dict_path.name}: {term!r} for subgroup {meta.get('Subgroup')!r} "
                                  f"claimed by both {std[key]!r} and {col!r}")
            std[key] = col
            continue
        std[term] = col

    for (kind, since), names in sorted(early.items()):
        rep.errors.append(f"{dict_path.name}: {kind} {sorted(names)} are from {_v(since)}; the folder "
                          f"declares {_v(version) if version else '?'}")
    if "n_rows" in entry and entry["n_rows"] != len(rows):
        rep.errors.append(f"{where}: {len(rows)} rows, analysis.json says {entry['n_rows']}")
    for term in ("p_value", "frac_significant", "p_uncorrected", "p_direction", "p_rope"):
        col = std.get(term)
        if col and col in cols:
            bad = [r[col] for r in rows if r[col] != "" and not _in_unit(r[col])]
            if bad:
                rep.errors.append(f"{where}: {col!r} ({term}) has values outside [0, 1]: {bad[:3]}")
    for term in ("significant", "effect_selected", "crosses_midline", "equivalent"):
        col = std.get(term)
        if col and col in cols:
            bad = [r[col] for r in rows if r[col] not in _TRUE | _FALSE | {""}]
            if bad:
                rep.errors.append(f"{where}: {col!r} ({term}) is not true/false: {bad[:3]}")
    _mde_rules(std, dictionary, rows, entry.get("role", ""), version, where, dict_path.name, rep)
    if version is not None and version >= (0, 4):
        _table_rules_0_4(std, dictionary, rows, analysis, where, dict_path.name, rep)
    if entry.get("role") in CONTRACT_ROLES:
        _contract(entry["role"], std, rows, analysis, where, rep)
    return entry.get("role", ""), std, rows


def _table_rules_0_4(std: dict, dictionary: dict, rows: list, analysis: dict, where: str,
                     dict_name: str, rep: Report) -> None:
    """What 0.4 adds to tables (RESULTS_SPEC.md §5.2-§5.6)."""
    def col_values(term):
        col = std.get(term)
        return col, ([r.get(col, "") for r in rows] if col else [])

    # §5.2 correction families
    fams = _families(analysis)
    pcol = std.get("p_value")
    pkind = (dictionary.get(pcol) or {}).get("PKind") if pcol else None
    fcol, fvals = col_values("correction_family")
    if fcol and not fams:
        rep.errors.append(f"{where}: {fcol!r} names correction families, but inference declares none")
    if fams and pcol:
        if fcol:
            unknown = sorted({v for v in fvals if v and v not in fams})
            if unknown:
                rep.errors.append(f"{where}: {fcol!r} names families inference does not declare: {unknown[:3]}")
            unnamed = sum(1 for r in rows if r.get(pcol, "") != "" and r.get(fcol, "") == "")
            if unnamed:
                rep.errors.append(f"{where}: {unnamed} row(s) give a p-value but no correction family")
        elif len(fams) > 1:
            rep.errors.append(f"{where}: inference declares {len(fams)} correction families, so each row "
                              "names its own -- needs a column marked 'correction_family'")
        used = {v for v in fvals if v} if fcol else set(fams)
        kinds = {fams[f].get("p_kind") for f in used if f in fams}
        if pkind == PER_FAMILY and len(kinds) <= 1 and not fcol:
            rep.errors.append(f"{dict_name}: {pcol!r} says PKind {PER_FAMILY!r} but no column names the families")
        elif pkind not in (None, PER_FAMILY) and kinds - {pkind}:
            rep.errors.append(f"{dict_name}: {pcol!r} says PKind {pkind!r}, but its rows' families are "
                              f"{sorted(map(str, kinds))} -- say {PER_FAMILY!r}")
    elif pkind == PER_FAMILY:
        rep.errors.append(f"{dict_name}: {pcol!r} says PKind {PER_FAMILY!r}, but inference declares no families")

    # §5.2 named facets: nothing more here; §5.4 effect measures that vary by row
    ecol = std.get("effect_size")
    if ecol and (dictionary.get(ecol) or {}).get("EffectMeasure") == PER_ROW:
        mcol = std.get("effect_measure")
        if not mcol:
            rep.errors.append(f"{where}: {ecol!r} has EffectMeasure {PER_ROW!r} -- needs a column marked "
                              "'effect_measure' naming each row's measure")
        else:
            blank = sum(1 for r in rows if r.get(ecol, "") != "" and r.get(mcol, "") == "")
            if blank:
                rep.errors.append(f"{where}: {blank} row(s) give an effect but not its measure ({mcol!r})")

    # §5.3 equivalence: a row tested for equivalence states its margin
    kcol = std.get("test_kind")
    eq_rows = [r for r in rows if kcol and r.get(kcol) == "equivalence"]
    if eq_rows:
        mcol = std.get("margin") or std.get("sesoi")
        if not mcol:
            rep.errors.append(f"{where}: {len(eq_rows)} equivalence row(s) -- needs a column marked 'margin' "
                              "(or 'sesoi') giving the bound")
        else:
            blank = sum(1 for r in eq_rows if r.get(mcol, "") == "")
            if blank:
                rep.errors.append(f"{where}: {blank} equivalence row(s) give no margin")

    # numbers that must be positive or finite
    for term, test, says in (("margin", lambda x: x > 0, "above 0"), ("sesoi", lambda x: x > 0, "above 0")):
        col, vals = col_values(term)
        bad = [v for v in vals if v != "" and not ((x := _num(v)) is not None and math.isfinite(x) and test(x))]
        if bad:
            rep.errors.append(f"{where}: {col!r} ({term}) is not a number {says}: {bad[:3]}")
    bcol, bvals = col_values("bf10")
    if bcol:
        log = (dictionary.get(bcol) or {}).get("Scale") == "log10"
        bad = [v for v in bvals if v != "" and not ((x := _num(v)) is not None and math.isfinite(x)
                                                     and (log or x > 0))]
        if bad:
            rep.errors.append(f"{where}: {bcol!r} (bf10) is not a {'finite number' if log else 'number above 0'}: "
                              f"{bad[:3]}")
    # §5.5 the posterior median lies within its interval
    med, lo, hi = std.get("posterior_median"), std.get("hdi_low"), std.get("hdi_high")
    if med and lo and hi:
        outside = 0
        for r in rows:
            m, a, b = _num(r.get(med, "")), _num(r.get(lo, "")), _num(r.get(hi, ""))
            if None not in (m, a, b) and not a <= m <= b:
                outside += 1
        if outside:
            rep.errors.append(f"{where}: {outside} row(s) with a posterior median outside its HDI")
    # §5.6 a reading is one of its Levels
    rcol = std.get("reading")
    if rcol:
        levels = set((dictionary.get(rcol) or {}).get("Levels") or {})
        bad = sorted({r.get(rcol, "") for r in rows} - levels - {""})
        if bad:
            rep.errors.append(f"{where}: {rcol!r} (reading) has values its Levels do not define: {bad[:3]}")


def facet_key(std: dict, row: dict) -> str:
    """A row's facet, as a test is identified by it: the one facet's value, named or not (so a
    test keeps its 0.3 identity), or from 0.4, with several named facets, ``name=value`` for
    each, sorted and joined with ';' (a figure's ``facets`` is matched the same way)."""
    named = sorted((k.split(":", 1)[1], c) for k, c in std.items() if k.startswith("facet:"))
    if len(named) == 1:
        return row.get(named[0][1], "")
    if named:
        return ";".join(f"{n}={row.get(c, '')}" for n, c in named)
    col = std.get("facet")
    return row.get(col, "") if col else ""


def _contract(role: str, std: dict, rows: list, analysis: dict, where: str, rep: Report) -> None:
    """The reporting contract, §6."""
    def need(*terms, why):
        if not any(t in std for t in terms):
            rep.errors.append(f"{where} ({role}): {why} -- needs a column marked "
                              + " or ".join(repr(t) for t in terms))

    need("contrast", why="which test")
    if len(analysis.get("measures") or []) > 1:
        need("measure", why="which measure (the analysis has several)")
    has_effect = (analysis.get("effect") or {}).get("measure") is not None
    bayes = str((analysis.get("inference") or {}).get("method", "")).lower() == "bayesian"

    if bayes and role in ("tests", "elements"):
        # 0.4, §5.5: a Bayesian row's magnitude is its posterior median with an HDI, and its
        # evidence is p_direction (p_rope and bf10 are optional), in place of effect and p.
        for term in ("posterior_median", "hdi_low", "hdi_high", "p_direction"):
            need(term, why="a Bayesian result")
            col = std.get(term)
            blank = sum(1 for r in rows if r.get(col, "") == "") if col else 0
            if blank:
                rep.errors.append(f"{where} ({role}): {blank} row(s) with no {term}; every Bayesian row "
                                  "carries it")
        if role == "tests":
            if "tested_direction" not in std and not ("test_kind" in std and "group_a" in std
                                                        and "group_b" in std):
                rep.errors.append(f"{where} (tests): direction -- needs 'tested_direction', or "
                                  "'test_kind' with 'group_a' and 'group_b'")
            if "n" not in std and not ("n_a" in std and "n_b" in std):
                rep.errors.append(f"{where} (tests): sample size -- needs 'n', or 'n_a' and 'n_b'")
        else:
            need("element", why="which element")
        return

    if role == "tests":
        if "tested_direction" not in std and not ("test_kind" in std and "group_a" in std
                                                    and "group_b" in std):
            rep.errors.append(f"{where} (tests): direction -- needs 'tested_direction', or "
                              "'test_kind' with 'group_a' and 'group_b'")
        if has_effect:
            need("effect_size", why="magnitude")
            if "effect_size" in std:
                need("effect_ci_low", why="uncertainty of the effect")
                need("effect_ci_high", why="uncertainty of the effect")
                blank = sum(1 for r in rows if r.get(std["effect_size"], "") == "")
                if blank:
                    rep.warnings.append(f"{where}: {blank} test row(s) with no effect size")
                lo, hi = std.get("effect_ci_low"), std.get("effect_ci_high")
                if lo and hi:
                    no_ci = sum(1 for r in rows if r.get(std["effect_size"], "") != ""
                                and (r.get(lo, "") == "" or r.get(hi, "") == ""))
                    if no_ci:
                        rep.errors.append(f"{where} (tests): {no_ci} row(s) give an effect without its "
                                          "interval -- the columns exist but the values are blank")
        if "n" not in std and not ("n_a" in std and "n_b" in std):
            rep.errors.append(f"{where} (tests): sample size -- needs 'n', or 'n_a' and 'n_b'")
        if "p_value" not in std and "equivalent" in std and "margin" in std:
            pass                                     # 0.4: an equivalence-only table (§5.3)
        else:
            need("p_value", why="significance")
        if analysis.get("analysis_type") in VOXELWISE:
            need("n_significant", "frac_significant", why="extent of a voxelwise test")
    elif role == "clusters":
        need("n_voxels", "volume_mm3", why="extent")
        need("peak_xyz_mm", why="location")
        need("peak_region", why="named location")
        need("stat", "effect_size", why="magnitude")
        if "effect_size" in std:
            need("effect_selected", why="cluster effects are selected; say so")
        need("p_value", why="significance")
    elif role == "elements":
        need("element", why="which element")
        need("effect_size", "stat", why="magnitude")
        need("p_value", why="significance")


# ----------------------------------------------------------------- analysis ---
def check_analysis(folder: Path) -> Report:
    folder = Path(folder)
    rep = Report(folder)
    analysis = _load_json(folder / ANALYSIS_JSON, rep)
    if analysis is None:
        return rep
    rep.id = analysis.get("id")
    rep.errors += [f"{ANALYSIS_JSON}{e[1:]}" for e in validate(analysis, load_schema("analysis"))]
    known = set(load_schema("analysis")["properties"])
    unknown = sorted(set(analysis) - known)
    if unknown:
        rep.warnings.append(f"{ANALYSIS_JSON}: fields this checker does not know: {unknown}")
    version = _version_ok(analysis["spec_version"], rep) if isinstance(analysis.get("spec_version"), str) else None
    v02 = version is not None and version >= (0, 2)
    if v02:
        _rules_0_2(analysis, rep)
    _rules_inference(analysis, version, rep)
    if version is not None and version >= (0, 4):
        _rules_0_4(analysis, rep)
    elif version is not None:
        used = features_0_4(analysis)
        if used:
            rep.errors.append(f"{ANALYSIS_JSON}: {used} are from 0.4; the folder declares {_v(version)}")

    prov = _load_json(folder / PROVENANCE_JSON, rep)
    if prov is not None:
        rep.errors += [f"{PROVENANCE_JSON}{e[1:]}" for e in validate(prov, load_schema("provenance"))]
        status = (prov.get("run") or {}).get("status")
        if status and status != "completed":
            rep.warnings.append(f"run status is {status!r}, not completed")

    effect = analysis.get("effect") or {}
    if isinstance(effect, dict):
        if effect.get("measure") is None and not effect.get("reason"):
            rep.errors.append(f"{ANALYSIS_JSON}: effect.measure is null without a reason")
        if effect.get("measure") is not None and not effect.get("definition"):
            rep.errors.append(f"{ANALYSIS_JSON}: effect.definition is required with a measure")

    tables = [t for t in analysis.get("tables") or [] if isinstance(t, dict)]
    if sum(1 for t in tables if t.get("headline")) > 1:
        rep.errors.append(f"{ANALYSIS_JSON}: more than one headline table")
    tested: set[tuple[str, str, str]] = set()
    facet_names: set[str] = set()
    listed = set(analysis.get("measures") or [])
    for entry in tables:
        got = _check_table(folder, entry, analysis, rep, version)
        if v02 and got and got[0] in CONTRACT_ROLES and "measure" in got[1] and listed:
            # 0.2: a table names its measures as analysis.json lists them
            col = got[1]["measure"]
            unlisted = sorted({r.get(col, "") for r in got[2]} - listed - {""})
            if unlisted:
                rep.errors.append(f"table {entry.get('path')!r}: measures {unlisted} are not in "
                                  "analysis.json's measures")
        if got:
            facet_names |= {k.split(":", 1)[1] for k in got[1] if k.startswith("facet:")}
        if got and got[0] == "tests":
            _role, std, rows = got
            mcol, ccol = std.get("measure"), std.get("contrast")
            if ccol:
                tested |= {(r.get(mcol, "") if mcol else "", r.get(ccol, ""), facet_key(std, r)) for r in rows}
    for item in analysis.get("maps") or []:
        if isinstance(item, dict) and "axes" in item and not valid_axes(item["axes"]):
            rep.errors.append(f"map {item.get('path')!r}: axes {item['axes']!r} is not three letters, "
                              "one from each of R/L, A/P, S/I")
        if isinstance(item, dict) and item.get("kind") in ("p_corrected", "p_uncorrected") \
                and "values" not in item:
            rep.warnings.append(f"map {item.get('path')!r}: a p map should say whether it holds "
                                "p or 1 - p ('values')")
    for kind in ("maps", "figures"):
        for item in analysis.get(kind) or []:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            _inside(folder, item["path"], kind[:-1], rep)
            facets = item.get("facets") if isinstance(item.get("facets"), dict) else None
            if facets and version is not None and version >= (0, 4):
                unknown = sorted(set(facets) - facet_names)
                if unknown:
                    rep.warnings.append(f"{kind[:-1]} {item['path']!r}: facets {unknown} are not named by "
                                        "any of the analysis's tables (FacetName)")
            if tested and item.get("contrast"):
                if facets and len(facets) == 1:
                    fkey = next(iter(facets.values()))
                elif facets:
                    fkey = ";".join(f"{k}={v}" for k, v in sorted(facets.items()))
                else:
                    fkey = item.get("facet", "")
                key = (item.get("measure", ""), item["contrast"], fkey)
                if key not in tested and ("", item["contrast"], fkey) not in tested:
                    rep.warnings.append(f"{kind[:-1]} {item['path']!r}: names a test with no "
                                        f"row in the tests table: {key}")
    for rec in (analysis.get("design") or {}).get("records") or []:
        if isinstance(rec, str):
            _inside(folder, rec, "design record", rep)
    nested = sorted(p.parent for p in folder.rglob(ANALYSIS_JSON)
                    if p.parent != folder and is_analysis(p.parent))
    if nested:
        rep.errors.append(f"analysis folders must not nest: {[str(p) for p in nested[:3]]}")
    run = analysis.get("run") if isinstance(analysis.get("run"), dict) else {}
    rep.meta = {"v02": v02, "modality": analysis.get("modality"), "analysis_type": analysis.get("analysis_type"),
                "run": run.get("id"), "supersedes": list(run.get("supersedes") or []), "tests": tested}
    return rep


def check_runs(reports: list[Report]) -> None:
    """Across folders (§3.2): an id names one analysis; each of its folders is one run.

    Runs of one id share modality and analysis_type and have distinct run ids; a run
    supersedes only runs of its own id; a test (measure, contrast, facet) in two runs is
    an error unless the later run lists the earlier in ``supersedes`` -- then the earlier
    run's copy of that test is superseded, and its other tests stay current. 0.1 folders
    have no runs: their ids must be unique. Errors are added to the reports in place.
    """
    from itertools import combinations

    by_id: dict[str, list[Report]] = {}
    for r in reports:
        if r.id:
            by_id.setdefault(r.id, []).append(r)
    for aid, reps in by_id.items():
        if len(reps) < 2:
            continue
        if not all(r.meta.get("v02") for r in reps):
            for r in reps:
                r.errors.append(f"id {aid!r} is used by {len(reps)} folders; only 0.2 folders, each one "
                                "run (§3.2), may share an id")
            continue
        for key in ("modality", "analysis_type"):
            values = {r.meta.get(key) for r in reps}
            if len(values) > 1:
                for r in reps:
                    r.errors.append(f"runs of {aid!r} disagree on {key}: {sorted(map(str, values))}")
        runs: dict[str, Report] = {}
        for r in reps:
            if r.run in runs:
                for x in (r, runs[r.run]):
                    x.errors.append(f"run {r.run!r} of {aid!r} is in two folders: {runs[r.run].folder}, {r.folder}")
            elif r.run:
                runs[r.run] = r
        superseded: set[tuple[str, tuple]] = set()
        for r in reps:
            for old in r.meta.get("supersedes") or []:
                if old not in runs:
                    r.errors.append(f"run {r.run!r} supersedes {old!r}, which is not a run of {aid!r}")
                    continue
                if r.run in (runs[old].meta.get("supersedes") or []):
                    r.errors.append(f"runs {r.run!r} and {old!r} of {aid!r} supersede each other")
                    continue
                overlap = r.meta["tests"] & runs[old].meta["tests"]
                if not overlap:
                    r.warnings.append(f"run {r.run!r} supersedes {old!r} but repeats none of its tests")
                superseded |= {(old, k) for k in overlap}
        for a, b in combinations([r for r in reps if r.run], 2):
            clash = sorted(k for k in a.meta["tests"] & b.meta["tests"]
                           if (a.run, k) not in superseded and (b.run, k) not in superseded)
            if clash:
                for x in (a, b):
                    x.errors.append(f"runs {a.run!r} and {b.run!r} of {aid!r} both hold {len(clash)} test(s), "
                                    f"e.g. {clash[0]}; the later run must list the earlier in supersedes")


def check(path: Path) -> list[Report]:
    """One report per analysis folder at or under ``path`` (empty when there are none),
    the runs of each analysis checked against each other (``check_runs``)."""
    reports = [check_analysis(f) for f in find_analyses(Path(path))]
    check_runs(reports)
    return reports
