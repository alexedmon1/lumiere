"""The significance summary (lumiere.gallery.digest), read from the tables' standard terms."""
import json

import pandas as pd
import pytest

from lumiere import check, gallery, provenance, write_analysis, write_columns
from lumiere.gallery.digest import digest


def _cols(element_name=None, element=True, equivalence=False):
    cols = {
        "hypothesis": {"Description": "contrast id", "Standard": "contrast"},
        "band": {"Description": "band", "Standard": "facet", "FacetName": "band"},
        "measure": {"Description": "measure", "Standard": "measure"},
        "g": {"Description": "effect", "Standard": "effect_size", "EffectMeasure": "per_row"},
        "g_type": {"Description": "its measure", "Standard": "effect_measure"},
        "q": {"Description": "BH q", "Standard": "p_value", "PKind": "fdr"},
        "sig": {"Description": "q < 0.05", "Standard": "significant", "Alpha": 0.05},
    }
    if element:
        cols["spatial"] = {"Description": "where", "Standard": "element",
                           **({"ElementName": element_name} if element_name else {})}
    if equivalence:
        cols["equivalent"] = {"Description": "TOST concludes equivalence", "Standard": "equivalent"}
    return cols


def _table(folder, name, rows, **kw):
    df = pd.DataFrame(rows)
    cols = _cols(**kw)
    df = df[[c for c in cols if c in df.columns]]
    df.to_csv(folder / name, index=False)
    write_columns(folder / name, {c: cols[c] for c in df.columns})
    return {"path": name, "role": "elements" if kw.get("element", True) else "tests", "rows": "a test",
            "description": name}


def _row(h, band, g, q, spatial=None, measure="band_power", gt="hedges_g", **extra):
    r = {"hypothesis": h, "band": band, "measure": measure, "g": g, "g_type": gt, "q": q, "sig": q < 0.05, **extra}
    if spatial is not None:
        r["spatial"] = spatial
    return r


CONTRASTS = [
    {"id": "omnibus", "label": "Omnibus", "kind": "omnibus", "tier": "phenotype"},
    {"id": "disease", "label": "Disease (KO vs WT)", "kind": "contrast", "tier": "phenotype",
     "group_a": "KO", "group_b": "WT"},
    {"id": "norm", "label": "Normalized to WT", "kind": "equivalence", "tier": "normalization"},
    {"id": "dose", "label": "Dose", "kind": "contrast", "tier": "exploratory"},
]


@pytest.fixture
def eeg(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    tables = [
        _table(f, "global.csv", [_row("omnibus", "Alpha", 0.30, 0.001, gt="omega2_partial"),
                                 _row("disease", "Alpha", -0.9, 0.01), _row("disease", "Beta", 0.2, 0.6),
                                 _row("dose", "Alpha", 0.1, 0.9),
                                 _row("norm", "Alpha", -1.5, 0.03, equivalent=False),
                                 _row("norm", "Beta", 0.05, 0.9, equivalent=True)],
               element=False, equivalence=True),
        _table(f, "region.csv", [_row("disease", "Alpha", -1.1, 0.02, "Frontal"),
                                 _row("disease", "Alpha", -0.2, 0.7, "Visual")], element_name="region"),
        _table(f, "roi.csv", [_row("disease", "Alpha", -2.0, 0.001, f"ROI{i}") for i in range(10)]
               + [_row("disease", "Beta", 1.4, 0.04, "ROI_b")], element_name="ROI"),
    ]
    return f, {"id": "eeg/roi/psd/x", "contrasts": CONTRASTS, "tables": tables}


def test_each_contrast_lists_its_significant_tests_at_every_level(eeg):
    folder, analysis = eeg
    d = digest(folder, analysis)
    assert [lv["name"] for lv in d["levels"]] == [None, "region", "ROI"]
    disease = next(c for c in d["contrasts"] if c["id"] == "disease")
    assert (disease["n_tests"], disease["n_significant"]) == (2, 2)
    alpha = disease["tests"][0]                                    # the strongest test first
    assert (alpha["facets"], alpha["measure"]) == (["Alpha"], "band_power")
    levels = {lv["level"]: lv for lv in alpha["levels"]}
    assert levels[""]["rows"][0]["effect"] == -0.9
    assert levels["region"]["n"] == 1 and levels["region"]["rows"][0]["element"] == "Frontal"
    assert levels["ROI"]["n"] == 10 and len(levels["ROI"]["rows"]) == 8   # named up to NAMED, counted beyond
    assert d["counts"] == {"": 3, "region": 1, "ROI": 11}   # omnibus, disease and norm Alpha overall
    assert next(c for c in d["contrasts"] if c["id"] == "dose")["n_significant"] == 0
    assert d["p_kind"] == "fdr"


def test_the_lead_is_the_strongest_overall_effect_of_a_directed_contrast(eeg):
    folder, analysis = eeg
    s = digest(folder, analysis)["strongest"]
    # not the omnibus (no direction), not the equivalence contrast, not an ROI's larger g
    assert (s["contrast"], s["facets"], s["row"]["effect"]) == ("disease", ["Alpha"], -0.9)


def test_equivalence_counts_what_concluded_and_lists_what_still_differs(eeg):
    folder, analysis = eeg
    norm = next(c for c in digest(folder, analysis)["contrasts"] if c["id"] == "norm")
    assert norm["kind"] == "equivalence" and norm["n_equivalent"] == 1 and norm["n_tests"] == 2
    assert [t["facets"] for t in norm["tests"]] == [["Alpha"]]


def test_an_element_table_row_naming_no_element_is_not_an_element(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    tables = [_table(f, "roi.csv", [_row("omnibus", "Alpha", 0.3, 0.001, "", gt="omega2_partial"),
                                    _row("disease", "Alpha", 1.0, 0.01, "R1")], element_name="ROI")]
    d = digest(f, {"contrasts": CONTRASTS, "tables": tables})
    assert next(c for c in d["contrasts"] if c["id"] == "omnibus")["n_significant"] == 0
    assert d["counts"] == {"ROI": 1}


def test_unsigned_effects_have_no_direction(eeg):
    folder, analysis = eeg
    omni = next(c for c in digest(folder, analysis)["contrasts"] if c["id"] == "omnibus")
    assert omni["tests"][0]["levels"][0]["rows"][0]["signed"] is False


def test_decoding_accuracy_has_no_direction(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    tables = [_table(f, "dec.csv", [_row("disease", "Alpha", 0.81, 0.01, gt="balanced_accuracy")], element=False)]
    d = digest(f, {"contrasts": CONTRASTS, "tables": tables})
    (row,) = next(c for c in d["contrasts"] if c["id"] == "disease")["tests"][0]["levels"][0]["rows"]
    assert row["signed"] is False and d["strongest"] is None      # no direction, so no "strongest" lead


def test_unnamed_element_tables_stay_apart(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    tables = [_table(f, "a.csv", [_row("disease", "Alpha", 1.0, 0.01, "R1")]),
              _table(f, "b.csv", [_row("disease", "Alpha", 1.2, 0.01, "Frontal")])]
    d = digest(f, {"contrasts": CONTRASTS, "tables": tables})
    assert [lv["id"] for lv in d["levels"]] == ["element:a.csv", "element:b.csv"]
    assert d["strongest"] is None                                  # no overall level


def test_significance_from_p_and_alpha_without_a_significant_column(tmp_path):
    """An MRI tests table (TBSS) states p and its correction, not a significant column."""
    f = tmp_path / "an"
    f.mkdir()
    pd.DataFrame({"measure": ["FA", "MD"], "contrast": ["A>B", "A>B"], "d": [0.8, -0.1],
                  "p": [0.02, 0.07]}).to_csv(f / "tests.csv", index=False)
    write_columns(f / "tests.csv", {"measure": {"Description": "m", "Standard": "measure"},
                                    "contrast": {"Description": "c", "Standard": "contrast"},
                                    "d": {"Description": "d", "Standard": "effect_size", "EffectMeasure": "d"},
                                    "p": {"Description": "p", "Standard": "p_value", "PKind": "fwe"}})
    a = {"tables": [{"path": "tests.csv", "role": "tests"}],
         "inference": {"correction": {"p_kind": "fwe", "alpha": 0.05}}}
    d = digest(f, a)
    (c,) = d["contrasts"]
    assert (c["label"], c["n_tests"], c["n_significant"]) == ("A>B", 2, 1)
    assert d["strongest"]["row"]["effect"] == 0.8 and d["p_kind"] == "fwe"
    a["inference"]["correction"]["alpha"] = 0.1
    assert digest(f, a)["contrasts"][0]["n_significant"] == 2


def test_no_summary_without_contrasts(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    pd.DataFrame({"m": ["FA"], "v": [1.0]}).to_csv(f / "d.csv", index=False)
    write_columns(f / "d.csv", {"m": {"Description": "m", "Standard": "measure"},
                                "v": {"Description": "v", "Standard": "effect_size", "EffectMeasure": "d"}})
    assert digest(f, {"tables": [{"path": "d.csv", "role": "tests"}]}) is None


def test_element_name_is_a_qualifier_the_checker_reads(eeg):
    folder, analysis = eeg
    a = {"id": "eeg/roi/psd/x", "title": "x", "description": "x", "analysis_type": "roi", "modality": "eeg",
         "measures": ["band_power"], "role": "exploratory", "design": {"n": 2},
         "inference": {"method": "lmm", "correction": {"p_kind": "fdr", "family": "band", "statement": "BH"}},
         "effect": {"measure": "per_row", "definition": "g or omega2"}, "run": {"id": "r1"},
         "tables": analysis["tables"]}
    write_analysis(folder, a, provenance([{"Name": "demo", "Version": "1"}], status="completed", start="2026"),
                   strict=False)
    errors = [e for rep in check(folder) for e in rep.errors]
    assert not [e for e in errors if "ElementName" in e]
    cols = json.loads((folder / "roi.json").read_text())
    cols["spatial"]["ElementName"] = ""
    (folder / "roi.json").write_text(json.dumps(cols))
    assert any("ElementName" in e for rep in check(folder) for e in rep.errors)


def test_the_gallery_carries_the_summary_and_survives_a_broken_one(tmp_path, monkeypatch):
    from test_gallery import (  # a conforming folder: FA, A>B, d=0.5, q=0.01
        _analysis_folder,
        _manifest,
    )

    _analysis_folder(tmp_path / "study" / "results", "dwi/tbss/h1", "r1", atype="tbss")
    settings = {"paths": {"results": "results"}}
    m = _manifest(gallery.build(tmp_path / "study", settings))
    assert not m["not_shown"], m["not_shown"]
    (an,) = m["analyses"].values()
    (c,) = an["digest"]["contrasts"]
    assert (c["id"], c["n_significant"]) == ("A>B", 1)
    assert an["digest"]["strongest"]["row"]["effect"] == 0.5

    def boom(*_a, **_k):
        raise ValueError("bad table")
    monkeypatch.setattr(gallery, "significance_digest", boom)
    with pytest.warns(UserWarning, match="no significance summary: bad table"):
        m = _manifest(gallery.build(tmp_path / "study", settings))
    assert next(iter(m["analyses"].values()))["digest"] is None


def test_a_network_component_says_its_size_and_direction(tmp_path):
    """An NBS component has no effect size: the summary shows its edges and which way they went."""
    f = tmp_path / "an"
    f.mkdir()
    cols = {
        "hypothesis": {"Description": "contrast id", "Standard": "contrast"},
        "band": {"Description": "band", "Standard": "facet", "FacetName": "band"},
        "measure": {"Description": "measure", "Standard": "measure"},
        "component_id": {"Description": "component", "Standard": "element", "ElementName": "component"},
        "n_edges": {"Description": "its edges", "Standard": "n_edges"},
        "direction": {"Description": "which way", "Standard": "observed_direction"},
        "component_p": {"Description": "FWE p", "Standard": "p_value", "PKind": "fwe"},
        "significant": {"Description": "p < 0.05", "Standard": "significant", "Alpha": 0.05},
    }
    pd.DataFrame([
        {"hypothesis": "disease", "band": "Beta", "measure": "coherence", "component_id": 1, "n_edges": 27,
         "direction": "mixed", "component_p": 0.049, "significant": True},
        {"hypothesis": "disease", "band": "Alpha", "measure": "aec", "component_id": 1, "n_edges": 3,
         "direction": "increase", "component_p": 0.6, "significant": False},
    ]).to_csv(f / "nbs.csv", index=False)
    write_columns(f / "nbs.csv", cols)
    tables = [{"path": "nbs.csv", "role": "elements", "rows": "a component", "description": "nbs"}]
    d = digest(f, {"contrasts": CONTRASTS, "tables": tables})
    (test,) = next(c for c in d["contrasts"] if c["id"] == "disease")["tests"]
    (row,) = test["levels"][0]["rows"]
    assert row["extent"] == {"value": 27.0, "unit": "edge"} and row["direction"] == "mixed"
    assert row["effect"] is None and d["counts"] == {"component": 1}
