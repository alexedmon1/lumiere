"""The vocabulary of the results specification (docs/RESULTS_SPEC.md).

Standard library only: this package is meant to run -- or be copied -- where
neurofaune's imaging dependencies are not installed (neurovrai, a reader's laptop).
"""
from __future__ import annotations

SPEC = "neurofaune.results"
SPEC_VERSION = "0.4.4"
#: The (major, minor) versions this package reads: every 0.x up to its own. A 0.1 folder
#: is checked by 0.1's rules; the rules added in 0.2 apply to folders that declare 0.2 or
#: later, and so on: each rule applies to folders declaring the version that added it or later.
READS = ((0, 1), (0, 2), (0, 3), (0, 4))

ANALYSIS_JSON = "analysis.json"
PROVENANCE_JSON = "provenance.json"

ANALYSIS_TYPES = ("tbss", "vbm", "tbm", "voxelwise", "roi", "covariance_network", "nbs", "graph",
                  "connectome", "fixel", "decoding", "radiomics", "spectroscopy",
                  # 0.4, for EEG: electrode-level, whole-brain source-space and directed-edge tests
                  "sensor", "vertex", "directed", "other")
#: The modality an analysis's data come from (0.2: required, one of these). An analysis
#: on several modalities says "multimodal" and lists them in ``modalities``.
MODALITIES = ("anat", "dwi", "func", "msme", "mrs", "asl", "eeg", "multimodal")
#: ``references`` labels with an agreed meaning (others are allowed, and opaque):
#: a pre-registered hypothesis the analysis tests, a recorded finding it reports, a DOI.
REFERENCE_LABELS = ("registration", "finding", "doi")
ROLES = ("confirmatory", "exploratory", "descriptive", "diagnostic")
P_KINDS = ("fwe", "fdr", "perm", "uncorrected", "none")
#: 0.4.1 adds ``recordings``: one row per recording (scan, EEG session), with its quality checks.
TABLE_ROLES = ("tests", "clusters", "elements", "descriptives", "recordings", "other")
CONTRACT_ROLES = ("tests", "clusters", "elements")
MAP_KINDS = ("stat", "p_corrected", "p_uncorrected", "effect", "mask", "background", "input",
             "other")
RUN_STATUSES = ("completed", "partial", "failed", "running")
DECISION_OUTCOMES = ("holds", "does_not_hold", "not_assessed")
TEST_KINDS = ("two_group", "one_sample", "regression", "interaction", "custom", "equivalence")
#: 0.4.1: what a declared contrast (``analysis.json`` ``contrasts``) is.
CONTRAST_KINDS = ("omnibus", "contrast", "equivalence", "regression", "other")
#: 0.4: the procedure a correction used, by name (``p_kind`` says only what it controls).
CORRECTION_METHODS = ("BH", "BY", "holm", "hochberg", "bonferroni", "tfce", "cluster", "maxT", "nbs",
                      "none", "other")
#: 0.4: a ``p_value`` column whose rows belong to families of different kinds says so as its PKind.
PER_FAMILY = "per_family"
#: 0.4: an ``effect_size`` column whose measure varies by row says so as its EffectMeasure, and
#: names each row's measure in an ``effect_measure`` column.
PER_ROW = "per_row"
#: 0.4: what a figure is, so a gallery can lay figures out and filter them.
FIGURE_KINDS = ("brain", "matrix", "spectrum", "distribution", "trajectory", "summary", "diagnostic",
                "other")
#: 0.4: who drew a figure: the analysis, with its results, or the tool when it built the gallery.
DRAWN_BY = ("analysis", "gallery")
#: 0.4: how a Bayes factor column is written.
BF_SCALES = ("log10", "linear")
TABLE_SUFFIXES = {".csv": ",", ".tsv": "\t"}
PLANES = ("axial", "coronal", "sagittal")
#: Each voxel axis runs toward one end of one of these pairs (S = superior / dorsal,
#: I = inferior / ventral for animals as for people).
AXIS_PAIRS = ("RL", "AP", "SI")


def valid_axes(code: str) -> bool:
    """Three letters, one from each of R/L, A/P, S/I, e.g. "LIA"."""
    if not isinstance(code, str) or len(code) != 3:
        return False
    used = [next((i for i, pair in enumerate(AXIS_PAIRS) if ch in pair), None) for ch in code.upper()]
    return None not in used and sorted(used) == [0, 1, 2]

#: Standard column terms -> the qualifiers each one requires in its dictionary entry.
STANDARD_TERMS: dict[str, tuple[str, ...]] = {
    "measure": (), "contrast": (), "contrast_label": (), "facet": (), "element": (),
    "test_kind": (), "tested_direction": (), "observed_direction": (),
    "group_a": (), "group_b": (), "n": (), "n_a": (), "n_b": (), "df": (),
    "effect_size": ("EffectMeasure",), "effect_ci_low": (), "effect_ci_high": (),
    "effect_selected": (), "estimate": (), "mean_a": (), "mean_b": (), "mean": (),
    "stat": ("StatName",), "p_value": ("PKind",), "significant": (),
    "n_significant": (), "frac_significant": (), "n_voxels": (), "volume_mm3": (), "n_edges": (),
    "peak_xyz_mm": ("Space",), "peak_region": (), "regions": (), "crosses_midline": (),
    "subgroup_effect": ("EffectMeasure", "Subgroup"), "subgroup_n": ("Subgroup",),
    # 0.3: what the design could have detected (RESULTS_SPEC.md §5.1)
    "se": (), "mde": ("Power", "Alpha"), "mde_percent": (), "mde_note": (),
    # 0.4 (RESULTS_SPEC.md §5.2-§5.6)
    "correction_family": (), "p_uncorrected": (), "effect_measure": (),
    "margin": ("Units",), "equivalent": (),
    "posterior_median": (), "hdi_low": ("CILevel",), "hdi_high": ("CILevel",), "p_direction": (),
    "p_rope": ("Rope",), "bf10": ("Scale",),
    "sesoi": ("Basis",), "reading": ("Levels",),
    # 0.4.1: a recordings table (§5.7)
    "subject": (), "group": (), "session": (), "qc_flag": ("Rule",),
}

#: Standard terms added after 0.1, with the (major, minor) version that added them. A folder
#: declaring an earlier version may not use them.
TERMS_SINCE: dict[str, tuple[int, int]] = {
    **dict.fromkeys(("se", "mde", "mde_percent", "mde_note"), (0, 3)),
    **dict.fromkeys(("correction_family", "p_uncorrected", "effect_measure", "margin", "equivalent",
                     "posterior_median", "hdi_low", "hdi_high", "p_direction", "p_rope", "bf10",
                     "sesoi", "reading", "subject", "group", "session", "qc_flag", "n_edges"), (0, 4)),
}
#: Every reason an ``mde`` is not given starts with this (``mde_note``).
NOT_COMPUTED = "not computed: "

#: Standard terms a table may carry once per subgroup (each column names its Subgroup).
PER_SUBGROUP = ("subgroup_effect", "subgroup_n")

#: Qualifier keys a dictionary entry may carry, besides BIDS's Description / Units / Levels.
QUALIFIERS = ("Standard", "EffectMeasure", "EffectScope", "CILevel", "StatName", "StatScope",
              "PKind", "PScope", "Alpha", "Power", "Space", "Subgroup",
              # 0.4
              "FacetName", "PercentOf", "Rope", "Scale", "Basis",
              # 0.4.1
              "Rule", "QCMetric",
              # 0.4.2
              "ElementName")
#: Qualifiers added after 0.3, with the version that added them. The checker reads versions
#: by (major, minor), so 0.4.1's and 0.4.2's additions, all optional, are checked in any 0.4 folder.
QUALIFIERS_SINCE: dict[str, tuple[int, int]] = dict.fromkeys(
    ("FacetName", "PercentOf", "Rope", "Scale", "Basis", "Rule", "QCMetric", "ElementName"), (0, 4))


# ── 0.2: identity and vocabulary ──────────────────────────────────────────────────

_SEGMENT = "abcdefghijklmnopqrstuvwxyz0123456789_"


def version_tuple(version: str) -> tuple[int, int] | None:
    """(major, minor) of a semver string, or None."""
    try:
        major, minor = (int(x) for x in str(version).split(".")[:2])
    except ValueError:
        return None
    return major, minor


def id_problem(analysis_id: str, modality: str, analysis_type: str) -> str | None:
    """Why an id does not follow ``<modality>/<analysis_type>/<name>`` (0.2), else None.

    The name may itself have ``/``-separated parts; every part is lowercase letters,
    digits and underscores (dots and hyphens also allowed in the name).
    """
    parts = str(analysis_id).split("/")
    if len(parts) < 3:
        return "is not <modality>/<analysis_type>/<name>"
    if parts[0] != modality:
        return f"starts with {parts[0]!r}, not its modality {modality!r}"
    if parts[1] != analysis_type:
        return f"has {parts[1]!r} second, not its analysis_type {analysis_type!r}"
    for part in parts[2:]:
        if not part or any(ch not in _SEGMENT + ".-" for ch in part):
            return f"name part {part!r} is not lowercase letters, digits, '_', '.' or '-'"
    return None


def measure_vocabulary() -> dict[str, dict]:
    """The measure vocabulary (vocab/measures.json): canonical name -> {modality,
    description, aliases}."""
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "vocab" / "measures.json").read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def domain_vocabulary() -> dict[str, dict]:
    """The domain vocabulary (vocab/domains.json, 0.4): name -> {modalities, description}."""
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "vocab" / "domains.json").read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


def entry_modalities(entry: dict) -> tuple[str, ...]:
    """The modalities a vocabulary entry belongs to: ``modality`` (one) or ``modalities``."""
    if entry.get("modalities"):
        return tuple(entry["modalities"])
    return (entry["modality"],) if entry.get("modality") else ()


def task_problem(task: str) -> str | None:
    """Why ``task`` is not a BIDS task label (letters and digits only), else None."""
    if not isinstance(task, str) or not task or not task.isascii() or not task.isalnum():
        return "is not a BIDS task label (letters and digits only, e.g. 'rest', 'assr40')"
    return None


def canonical_measure(name: str, vocabulary: dict[str, dict] | None = None) -> tuple[str | None, bool]:
    """(the canonical name ``name`` stands for, whether ``name`` already is it).

    (None, False) for a name the vocabulary does not know. A case variant or an alias of
    a known measure returns its canonical name and False.
    """
    vocab = vocabulary if vocabulary is not None else measure_vocabulary()
    if name in vocab:
        return name, True
    low = str(name).lower()
    for canon, entry in vocab.items():
        if low == canon.lower() or low in {a.lower() for a in entry.get("aliases", [])}:
            return canon, False
    return None, False


def analysis_id(modality: str, analysis_type: str, *name: str) -> str:
    """``<modality>/<analysis_type>/<name>``, each name part lowercased and anything but
    letters, digits, '_', '.' and '-' turned into '_' -- the id 0.2 asks for."""
    import re

    parts = [re.sub(r"[^a-z0-9_.-]+", "_", str(p).lower()).strip("_") for p in name]
    return "/".join([modality, analysis_type, *(p for p in parts if p)])


# ── 0.2: runs -- tests of one analysis run at different times ─────────────────────
#
# An analysis is one id; each time some of its tests are run, that run writes a folder
# of its own (never edited afterwards), whose analysis.json carries
# ``run: {id, label, supersedes}``. Readers show one analysis per id, its runs together.

def run_id_problem(run_id: str) -> str | None:
    """Why a run id is not lowercase letters, digits, '_', '.' or '-', else None."""
    if not isinstance(run_id, str) or not run_id or any(ch not in _SEGMENT + ".-" for ch in run_id):
        return "is not lowercase letters, digits, '_', '.' or '-'"
    return None


def default_run_id() -> str:
    """A run id from the current UTC time, e.g. ``2026-10-06_183248``."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def run_folder(root, analysis_id: str, run_id: str):
    """The recommended folder of one run: ``<root>/<analysis id>/<run id>``."""
    from pathlib import Path

    why = run_id_problem(run_id)
    if why:
        raise ValueError(f"run id {run_id!r} {why}")
    return Path(root).joinpath(*analysis_id.split("/"), run_id)
