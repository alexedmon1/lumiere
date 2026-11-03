"""The results specification (docs/RESULTS_SPEC.md): schemas, checker and writer.

Copied from neurofaune's tests/unit/test_results_spec.py when the package moved here
(2026-11-03); the two tests that need neurofaune's read-out and atlas code stay there.
"""


import json
import subprocess
import sys

import pandas as pd
import pytest

from neurobox import (
    SPEC_VERSION,
    STANDARD_TERMS,
    NonConformingResults,
    _schema,
    check,
    columns_for,
    provenance,
    spec,
    write_analysis,
    write_columns,
)
from neurobox.__main__ import main as cli

COLUMNS = {
    "measure": {"Description": "measure", "Standard": "measure"},
    "contrast": {"Description": "test id", "Standard": "contrast"},
    "direction": {"Description": "what positive means", "Standard": "tested_direction"},
    "n": {"Description": "subjects", "Standard": "n"},
    "d": {"Description": "Cohen's d", "Standard": "effect_size", "EffectMeasure": "d"},
    "lo": {"Description": "CI low", "Standard": "effect_ci_low"},
    "hi": {"Description": "CI high", "Standard": "effect_ci_high"},
    "p": {"Description": "p", "Standard": "p_value", "PKind": "fdr"},
}


def _analysis(**over):
    a = {"id": "dwi/roi/demo", "title": "Demo", "description": "a demonstration", "analysis_type": "roi",
         "modality": "dwi",
         "measures": ["FA", "MD"], "role": "exploratory", "design": {"n": 20, "groups": {"A": 10, "B": 10}},
         "inference": {"method": "Welch t", "correction": {"p_kind": "fdr", "family": "ROIs x measures",
                                                           "statement": "BH-FDR q < 0.05 over ROIs x measures"}},
         "effect": {"measure": "d", "definition": "pooled-SD Cohen's d", "ci_level": 0.95},
         "tables": [{"path": "tests.tsv", "role": "tests", "rows": "one measure in one ROI",
                     "description": "every test", "headline": True, "n_rows": 2}]}
    a.update(over)
    return a


def _prov():
    return provenance([{"Name": "demo", "Version": "1.0"}], status="completed", start="2026-10-06T00:00:00")


@pytest.fixture
def folder(tmp_path):
    f = tmp_path / "an"
    f.mkdir()
    pd.DataFrame({"measure": ["FA", "MD"], "contrast": ["A>B", "A>B"], "direction": ["A > B"] * 2,
                  "n": [20, 20], "d": [0.8, -0.1], "lo": [0.1, -0.8], "hi": [1.5, 0.6],
                  "p": [0.02, 0.7]}).to_csv(f / "tests.tsv", sep="\t", index=False)
    write_columns(f / "tests.tsv", COLUMNS)
    return f


def _errors(folder):
    (rep,) = check(folder)
    return " | ".join(rep.errors)


def test_package_needs_only_the_standard_library():
    code = ("import sys, neurobox, neurobox.__main__; "
            "heavy = {'numpy', 'pandas', 'nibabel', 'scipy', 'nipype', 'neurofaune'} & set(sys.modules); "
            "print(sorted(heavy))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def _walk(schema, where="$"):
    yield where, schema
    for key in ("properties",):
        for k, v in schema.get(key, {}).items():
            yield from _walk(v, f"{where}.{k}")
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            yield from _walk(schema[key], f"{where}.{key}")


@pytest.mark.parametrize("name", ["analysis", "provenance", "columns"])
def test_schemas_use_only_keywords_the_checker_understands(name):
    for where, node in _walk(_schema.load_schema(name)):
        unknown = set(node) - _schema._KEYWORDS - _schema._ANNOTATIONS
        assert not unknown, f"{name} {where}: {unknown}"


def test_schemas_and_vocabulary_agree():
    a, c = _schema.load_schema("analysis"), _schema.load_schema("columns")
    assert tuple(a["properties"]["analysis_type"]["enum"]) == spec.ANALYSIS_TYPES
    assert tuple(a["properties"]["role"]["enum"]) == spec.ROLES
    assert tuple(a["properties"]["tables"]["items"]["properties"]["role"]["enum"]) == spec.TABLE_ROLES
    assert tuple(a["properties"]["maps"]["items"]["properties"]["kind"]["enum"]) == spec.MAP_KINDS
    assert tuple(c["additionalProperties"]["properties"]["PKind"]["enum"]) == (*spec.P_KINDS, spec.PER_FAMILY)
    assert tuple(a["properties"]["figures"]["items"]["properties"]["kind"]["enum"]) == spec.FIGURE_KINDS
    assert tuple(a["properties"]["figures"]["items"]["properties"]["drawn_by"]["enum"]) == spec.DRAWN_BY
    assert tuple(a["properties"]["design"]["properties"]["test_kinds"]["items"]["enum"]) == spec.TEST_KINDS
    for node in (a["properties"]["inference"]["properties"]["correction"],
                 a["properties"]["inference"]["properties"]["families"]["items"],
                 a["properties"]["tables"]["items"]["properties"]["threshold"]):
        assert tuple(node["properties"]["p_kind"]["enum"]) == spec.P_KINDS
        assert tuple(node["properties"]["method"]["enum"]) == spec.CORRECTION_METHODS
    assert tuple(c["additionalProperties"]["properties"]["Scale"]["enum"]) == spec.BF_SCALES
    assert set(c["additionalProperties"]["properties"]["Standard"]["enum"]) == set(STANDARD_TERMS)
    assert set(spec.QUALIFIERS) <= set(c["additionalProperties"]["properties"])


MDE_COLUMNS = {
    "se": {"Description": "SE of the difference", "Standard": "se"},
    "mde": {"Description": "minimum detectable difference", "Standard": "mde", "Power": 0.8, "Alpha": 0.05},
    "mde_pct": {"Description": "mde, percent of B's mean", "Standard": "mde_percent", "Units": "%",
                "PercentOf": "group B's mean of the measure"},
    "mde_note": {"Description": "why no mde", "Standard": "mde_note"},
}


def _with_mde(folder, **values):
    """Give the fixture's tests table the 0.3 MDE columns (``values`` overrides them)."""
    df = pd.read_csv(folder / "tests.tsv", sep="\t")
    cols = {"se": [0.02, 0.03], "mde": [0.056, 0.084], "mde_pct": [12.0, 9.0], "mde_note": ["", ""], **values}
    for k, v in cols.items():
        df[k] = v
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    write_columns(folder / "tests.tsv", {**COLUMNS, **MDE_COLUMNS})
    return folder


def test_a_complete_folder_conforms_and_reads_without_neurofaune(folder):
    _with_mde(folder)
    rep = write_analysis(folder, _analysis(), _prov())
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)

    # The "no lightbox" read: plain json + pandas, knowing only the specification.
    a = json.loads((folder / "analysis.json").read_text())
    assert a["spec"] == "neurofaune.results"   # the identifier stays until the final name
    head = next(t for t in a["tables"] if t.get("headline"))
    cols = json.loads((folder / head["path"]).with_suffix(".json").read_text())
    role = {m["Standard"]: c for c, m in cols.items() if "Standard" in m}
    df = pd.read_csv(folder / head["path"], sep="\t" if head["path"].endswith(".tsv") else ",")
    assert df[role["effect_size"]].tolist() == [0.8, -0.1]
    assert cols[role["effect_size"]]["EffectMeasure"] == "d"
    assert cols[role["p_value"]]["PKind"] == "fdr"
    assert (cols[role["mde"]]["Power"], cols[role["mde"]]["Alpha"]) == (0.8, 0.05)
    assert a["inference"]["correction"]["statement"].startswith("BH-FDR")
    prov = json.loads((folder / "provenance.json").read_text())
    assert prov["generated_by"][0]["Name"] == "demo" and prov["run"]["status"] == "completed"


def test_strict_writing_refuses_a_nonconforming_folder(folder):
    with pytest.raises(NonConformingResults, match="effect_ci_low"):
        cols = {k: v for k, v in COLUMNS.items() if k != "lo"}
        pd.read_csv(folder / "tests.tsv", sep="\t").drop(columns="lo").to_csv(
            folder / "tests.tsv", sep="\t", index=False)
        write_columns(folder / "tests.tsv", cols)
        write_analysis(folder, _analysis(), _prov())


def test_every_column_needs_a_dictionary_entry():
    with pytest.raises(KeyError, match="mystery"):
        columns_for(["d", "mystery"], COLUMNS)


@pytest.mark.parametrize("drop, message", [
    ("direction", "direction"),
    ("d", "magnitude"),
    ("hi", "uncertainty"),
    ("n", "sample size"),
    ("p", "significance"),
    ("measure", "which measure"),
    ("contrast", "which test"),
])
def test_tests_tables_must_state_the_contract(folder, drop, message):
    df = pd.read_csv(folder / "tests.tsv", sep="\t").drop(columns=drop)
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    write_columns(folder / "tests.tsv", COLUMNS)
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert message in _errors(folder)


def test_a_p_value_must_name_its_correction(folder):
    write_columns(folder / "tests.tsv", COLUMNS, {"p": {"Description": "p", "Standard": "p_value"}})
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "must state PKind" in _errors(folder)


def test_no_effect_needs_a_reason(folder):
    write_analysis(folder, _analysis(effect={"measure": None}), _prov(), strict=False)
    assert "without a reason" in _errors(folder)


def test_voxelwise_tests_must_state_extent(folder):
    write_analysis(folder, _analysis(analysis_type="vbm"), _prov(), strict=False)
    assert "extent" in _errors(folder)


def test_cluster_tables_must_state_location_and_selection(folder):
    pd.DataFrame({"measure": ["FA"], "contrast": ["A>B"], "n_voxels": [12], "d": [1.2],
                  "p": [0.01]}).to_csv(folder / "clusters.csv", index=False)
    write_columns(folder / "clusters.csv", {**COLUMNS, "n_voxels": {
        "Description": "extent", "Standard": "n_voxels", "Units": "voxels"}},
        {"p": {"Description": "p", "Standard": "p_value", "PKind": "fwe"}})
    tables = _analysis()["tables"] + [{"path": "clusters.csv", "role": "clusters",
                                        "rows": "one cluster", "description": "clusters"}]
    write_analysis(folder, _analysis(tables=tables), _prov(), strict=False)
    errs = _errors(folder)
    assert "location" in errs and "named location" in errs and "selected" in errs


def test_dictionary_must_match_the_table(folder):
    cols = json.loads((folder / "tests.json").read_text())
    cols["ghost"] = {"Description": "not in the table"}
    del cols["n"]
    (folder / "tests.json").write_text(json.dumps(cols))
    write_analysis(folder, _analysis(), _prov(), strict=False)
    errs = _errors(folder)
    assert "without a dictionary entry: ['n']" in errs and "['ghost']" in errs


def test_listed_paths_must_stay_inside_and_exist(folder):
    maps = [{"path": "../elsewhere.nii.gz", "kind": "stat", "description": "x"},
            {"path": "missing.nii.gz", "kind": "stat", "description": "y"}]
    write_analysis(folder, _analysis(maps=maps), _prov(), strict=False)
    errs = _errors(folder)
    assert "stay inside" in errs and "not on disk" in errs


def test_row_count_is_checked_when_declared(folder):
    tables = [{**_analysis()["tables"][0], "n_rows": 3}]
    write_analysis(folder, _analysis(tables=tables), _prov(), strict=False)
    assert "2 rows, analysis.json says 3" in _errors(folder)


def test_a_standard_term_is_claimed_once(folder):
    write_columns(folder / "tests.tsv", COLUMNS, {"lo": {"Description": "x", "Standard": "effect_size",
                                                         "EffectMeasure": "d"}})
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "claimed by both" in _errors(folder)


@pytest.mark.parametrize("version, ok", [(SPEC_VERSION, True), ("0.1.7", True), ("0.2.0", True),
                                         ("0.3.0", True), ("0.4.0", True), ("0.5.0", False),
                                         ("1.0.0", False)])
def test_spec_version(folder, version, ok):
    write_analysis(folder, {**_analysis(), "spec_version": version}, _prov(), strict=False)
    assert ("not readable" not in _errors(folder)) is ok


def test_analysis_folders_do_not_nest(folder):
    write_analysis(folder, _analysis(), _prov())
    inner = folder / "inner"
    inner.mkdir()
    (inner / "tests.tsv").write_bytes((folder / "tests.tsv").read_bytes())
    (inner / "tests.json").write_bytes((folder / "tests.json").read_bytes())
    write_analysis(inner, _analysis(id="dwi/roi/inner"), _prov())
    outer = next(r for r in check(folder.parent) if r.folder == folder)
    assert any("must not nest" in e for e in outer.errors)


def test_unfinished_runs_are_flagged(folder):
    write_analysis(folder, _analysis(), provenance([{"Name": "x", "Version": "1"}], status="partial",
                                                   start="2026-10-06T00:00:00"))
    (rep,) = check(folder)
    assert rep.ok and any("partial" in w for w in rep.warnings)


def test_cli(folder, capsys):
    write_analysis(folder, _analysis(), _prov())
    assert cli(["check", str(folder.parent)]) == 0
    assert "OK   dwi/roi/demo" in capsys.readouterr().out
    (folder / "provenance.json").unlink()
    assert cli(["check", str(folder), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["ok"] is False
    assert cli(["check", str(folder / "tests.tsv")]) == 1        # nothing to check is not a pass


def test_an_effect_needs_its_interval_values_not_just_the_columns(folder):
    df = pd.read_csv(folder / "tests.tsv", sep="\t")
    df.loc[0, "lo"] = None
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "without its interval" in _errors(folder)


@pytest.mark.parametrize("code, ok", [("LIA", True), ("ras", True), ("RRA", False), ("LI", False),
                                      ("XYZ", False), ("SIA", False)])
def test_axes_codes(code, ok):
    assert spec.valid_axes(code) is ok


def test_a_bad_axes_code_fails(folder):
    maps = [{"path": "tests.tsv", "kind": "other", "description": "x", "axes": "LIX"}]
    write_analysis(folder, _analysis(maps=maps, display={"plane": "coronal"}), _prov(), strict=False)
    assert "three letters" in _errors(folder)


def test_subgroup_terms_repeat_once_per_subgroup(folder):
    df = pd.read_csv(folder / "tests.tsv", sep="\t")
    df["d_X"], df["d_Y"], df["n_X"] = [0.6, -0.2], [0.9, 0.1], [8, 8]
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    extra = {"d_X": {"Description": "d in X", "Standard": "subgroup_effect", "EffectMeasure": "d",
                     "Subgroup": "X"},
             "d_Y": {"Description": "d in Y", "Standard": "subgroup_effect", "EffectMeasure": "d",
                     "Subgroup": "Y"},
             "n_X": {"Description": "n in X", "Standard": "subgroup_n", "Subgroup": "X"}}
    write_columns(folder / "tests.tsv", COLUMNS, extra)
    assert write_analysis(folder, _analysis(), _prov()).ok
    extra["d_Y"]["Subgroup"] = "X"                                 # the same subgroup twice
    write_columns(folder / "tests.tsv", COLUMNS, extra)
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "for subgroup 'X' claimed by both" in _errors(folder)
    del extra["d_Y"]["Subgroup"]                                   # a subgroup effect must name it
    write_columns(folder / "tests.tsv", COLUMNS, extra)
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "must state Subgroup" in _errors(folder)


def test_a_0_1_folder_is_still_read_by_0_1_rules(folder):
    old = {k: v for k, v in _analysis(id="roi/demo").items() if k != "modality"}
    write_analysis(folder, {**old, "spec_version": "0.1.0"}, _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok, rep.errors


@pytest.mark.parametrize("over, says", [
    ({"modality": None}, "modality is required"),
    ({"modality": "DWI"}, "is not one of"),
    ({"id": "roi/demo"}, "is not <modality>/<analysis_type>/<name>"),
    ({"id": "func/roi/demo"}, "not its modality"),
    ({"id": "dwi/tbss/demo"}, "not its analysis_type"),
    ({"id": "dwi/roi/Demo Run"}, "is not lowercase"),
    ({"modality": "multimodal", "id": "multimodal/roi/demo"}, "lists its modalities"),
    ({"modalities": ["dwi", "func"]}, "for multimodal analyses only"),
    ({"measures": ["FA", "NDI"]}, "is written 'FICVF'"),
    ({"measures": ["fa", "MD"]}, "is written 'FA'"),
])
def test_0_2_identity_and_vocabulary(folder, over, says):
    a = _analysis(**over)
    if a.get("modality") is None:
        a.pop("modality")
    write_analysis(folder, a, _prov(), strict=False)
    assert says in _errors(folder)


def test_0_2_multimodal_and_unknown_measures_warn_not_fail(folder):
    write_analysis(folder, _analysis(id="multimodal/roi/demo", modality="multimodal",
                                     modalities=["dwi", "func"], measures=["FA", "MD", "Zeta"]),
                   _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok, rep.errors
    assert any("'Zeta' is not in the measure vocabulary" in w for w in rep.warnings)


def test_0_2_a_measure_of_another_modality_warns(folder):
    write_analysis(folder, _analysis(id="func/roi/demo", modality="func"), _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok and any("is a dwi measure, in a func analysis" in w for w in rep.warnings)


def test_0_2_a_table_names_only_listed_measures(folder):
    write_analysis(folder, _analysis(measures=["FA"]), _prov(), strict=False)
    assert "measures ['MD'] are not in analysis.json's measures" in _errors(folder)


def test_analysis_id_helper():
    from neurobox.spec import analysis_id, id_problem

    got = analysis_id("func", "voxelwise", "H1j ReHo", "p60 to p90")
    assert got == "func/voxelwise/h1j_reho/p60_to_p90"
    assert id_problem(got, "func", "voxelwise") is None


def test_the_measure_vocabulary_is_packaged_and_consistent():
    from neurobox.spec import MODALITIES, canonical_measure, measure_vocabulary

    vocab = measure_vocabulary()
    assert {"FA", "MK", "FICVF", "T2", "MWF", "ReHo", "fALFF", "logJ_local", "Cr+PCr"} <= set(vocab)
    assert all(spec.entry_modalities(v) and set(spec.entry_modalities(v)) <= set(MODALITIES) - {"multimodal"}
               for v in vocab.values())
    names = {k.lower() for k in vocab}
    aliases = [a.lower() for v in vocab.values() for a in v.get("aliases", [])]
    assert len(aliases) == len(set(aliases)) and not names & set(aliases)
    assert canonical_measure("CSFF") == ("CSWF", False) and canonical_measure("Glx") == ("Glu+Gln", False)


def _run(root, run_id, contrasts=("A>B",), measures=("FA", "MD"), **over):
    """One run of dwi/roi/demo under ``root``, with the given contrasts on the given measures."""
    from neurobox.spec import run_folder

    f = run_folder(root, "dwi/roi/demo", run_id)
    f.mkdir(parents=True)
    rows = [(m, c) for c in contrasts for m in measures]
    pd.DataFrame({"measure": [m for m, _ in rows], "contrast": [c for _, c in rows],
                  "direction": ["A > B"] * len(rows), "n": [20] * len(rows), "d": [0.5] * len(rows),
                  "lo": [0.1] * len(rows), "hi": [0.9] * len(rows), "p": [0.04] * len(rows)}
                 ).to_csv(f / "tests.tsv", sep="\t", index=False)
    write_columns(f / "tests.tsv", COLUMNS)
    a = _analysis(measures=list(measures), run={"id": run_id, **over})
    a["tables"][0]["n_rows"] = len(rows)
    write_analysis(f, a, _prov(), strict=False)
    return f


def _by_run(root):
    return {r.run: r for r in check(root)}


def test_runs_with_different_tests_are_one_analysis(tmp_path):
    _run(tmp_path, "2026-10-05", contrasts=("A>B",))
    _run(tmp_path, "2026-10-08", contrasts=("B>A",), label="added later")
    reps = _by_run(tmp_path)
    assert set(reps) == {"2026-10-05", "2026-10-08"} and all(r.ok for r in reps.values()), \
        [r.errors for r in reps.values()]
    assert {r.id for r in reps.values()} == {"dwi/roi/demo"}


def test_a_test_in_two_runs_needs_supersedes(tmp_path):
    _run(tmp_path, "2026-10-05")
    _run(tmp_path, "2026-10-08")
    reps = _by_run(tmp_path)
    assert all("the later run must list the earlier in supersedes" in " ".join(r.errors) for r in reps.values())


def test_supersedes_replaces_only_the_repeated_tests(tmp_path):
    _run(tmp_path, "2026-10-05", contrasts=("A>B", "B>A"))
    _run(tmp_path, "2026-10-08", contrasts=("A>B",), supersedes=["2026-10-05"])
    reps = _by_run(tmp_path)
    assert all(r.ok for r in reps.values()), [r.errors for r in reps.values()]


@pytest.mark.parametrize("over, says", [
    ({"supersedes": ["2026-01-01"]}, "which is not a run of"),
    ({"supersedes": ["2026-10-08"]}, "supersedes itself"),
])
def test_supersedes_names_another_existing_run(tmp_path, over, says):
    _run(tmp_path, "2026-10-05", contrasts=("A>B",))
    _run(tmp_path, "2026-10-08", contrasts=("B>A",), **over)
    assert says in " ".join(_by_run(tmp_path)["2026-10-08"].errors)


def test_runs_agree_on_modality_and_have_distinct_ids(tmp_path):
    _run(tmp_path, "2026-10-05", contrasts=("A>B",))
    f = _run(tmp_path, "2026-10-08", contrasts=("B>A",))
    a = json.loads((f / "analysis.json").read_text())
    a.update(modality="func", id="dwi/roi/demo")          # contradicts its id too; both reported
    (f / "analysis.json").write_text(json.dumps(a))
    assert "disagree on modality" in " ".join(_by_run(tmp_path)["2026-10-05"].errors)
    g = tmp_path / "elsewhere"
    g.mkdir()
    for name in ("tests.tsv", "tests.json", "provenance.json"):
        (g / name).write_bytes((f / name).read_bytes())
    a.update(modality="dwi")
    (g / "analysis.json").write_text(json.dumps(a))
    assert any("is in two folders" in " ".join(r.errors) for r in check(tmp_path))


def test_the_writer_names_a_run_and_checks_its_siblings(tmp_path):
    _run(tmp_path, "2026-10-05")
    f = _run(tmp_path, "2026-10-08")
    from neurobox.check import check_analysis

    assert check_analysis(f).ok                 # alone it conforms; beside its sibling it does not
    a = json.loads((f / "analysis.json").read_text())
    with pytest.raises(Exception, match="supersedes"):
        write_analysis(f, a, _prov())
    a.pop("run")
    g = tmp_path / "dwi" / "roi" / "other" / "x"
    g.mkdir(parents=True)
    for name in ("tests.tsv", "tests.json"):
        (g / name).write_bytes((f / name).read_bytes())
    write_analysis(g, {**a, "id": "dwi/roi/other"}, _prov())
    assert json.loads((g / "analysis.json").read_text())["run"]["id"]       # filled in


def test_0_1_folders_have_no_runs_and_unique_ids(tmp_path):
    for name in ("a", "b"):
        f = tmp_path / name
        f.mkdir()
        pd.DataFrame({"measure": ["FA", "MD"], "contrast": ["A>B"] * 2, "direction": ["A > B"] * 2,
                      "n": [20, 20], "d": [0.8, -0.1], "lo": [0.1, -0.8], "hi": [1.5, 0.6],
                      "p": [0.02, 0.7]}).to_csv(f / "tests.tsv", sep="\t", index=False)
        write_columns(f / "tests.tsv", COLUMNS)
        old = {k: v for k, v in _analysis(id="roi/demo").items() if k != "modality"}
        write_analysis(f, {**old, "spec_version": "0.1.0"}, _prov(), strict=False)
    assert all("only 0.2 folders" in " ".join(r.errors) for r in check(tmp_path))


def test_a_0_2_folder_without_a_run_is_reported(folder):
    write_analysis(folder, _analysis(), _prov(), strict=False)
    a = json.loads((folder / "analysis.json").read_text())
    a.pop("run")
    (folder / "analysis.json").write_text(json.dumps(a))
    assert "run is required" in _errors(folder)


def test_0_3_a_tests_table_without_an_mde_is_warned_about_not_refused(folder):
    write_analysis(folder, _analysis(), _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok and any("no 'mde'" in w for w in rep.warnings)


def test_0_3_an_mde_note_alone_answers_the_warning(folder):
    df = pd.read_csv(folder / "tests.tsv", sep="\t")
    df["mde_note"] = ["not computed: permutation test with no standard error"] * 2
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    write_columns(folder / "tests.tsv", {**COLUMNS, "mde_note": MDE_COLUMNS["mde_note"]})
    rep = write_analysis(folder, _analysis(), _prov())
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)


def test_0_3_an_mde_not_computed_says_why(folder):
    _with_mde(folder, mde=[0.056, None], mde_pct=[12.0, None],
              mde_note=["", "not computed: zero residual variance"])
    rep = write_analysis(folder, _analysis(), _prov())
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)


@pytest.mark.parametrize("values, says", [
    ({"mde": [0.056, -0.1]}, "is not a positive number"),
    ({"mde": [0.056, 0]}, "is not a positive number"),
    ({"mde": [0.056, None], "mde_pct": [12.0, None]}, "give no mde and no mde_note"),
    ({"mde": [0.056, None], "mde_pct": [12.0, None], "mde_note": ["", "too few animals"]},
     "does not start 'not computed: '"),
    ({"mde_note": ["", "not computed: but given anyway"]}, "give an mde and an mde_note"),
    ({"mde": [0.056, None], "mde_note": ["", "not computed: x"]}, "mde_percent without an mde"),
    ({"mde_pct": [12.0, -3]}, "(mde_percent) is not a positive number"),
    ({"se": [0.02, -1]}, "(se) is not a number >= 0"),
])
def test_0_3_mde_values_are_checked(folder, values, says):
    _with_mde(folder, **values)
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert says in _errors(folder)


@pytest.mark.parametrize("entry, says", [
    ({"Power": None}, "must state Power"),
    ({"Alpha": None}, "must state Alpha"),
    ({"Power": 80}, "Power 80 is not between 0 and 1"),
])
def test_0_3_an_mde_states_its_power_and_alpha(folder, entry, says):
    _with_mde(folder)
    mde = {k: v for k, v in {**MDE_COLUMNS["mde"], **entry}.items() if v is not None}
    write_columns(folder / "tests.tsv", {**COLUMNS, **MDE_COLUMNS}, {"mde": mde})
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert says in _errors(folder)


def test_0_3_terms_are_not_for_older_folders(folder):
    write_analysis(folder, {**_analysis(), "spec_version": "0.2.0"}, _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)    # 0.2 asks for no mde
    _with_mde(folder)
    write_analysis(folder, {**_analysis(), "spec_version": "0.2.0"}, _prov(), strict=False)
    assert "are from 0.3; the folder declares 0.2" in _errors(folder)


# ── 0.4: EEG, correction families, equivalence, Bayesian results, smallest effects ──────

EEG_COLUMNS = {
    "measure": {"Description": "aperiodic parameter", "Standard": "measure"},
    "contrast": {"Description": "group pair", "Standard": "contrast"},
    "band": {"Description": "frequency band", "Standard": "facet", "FacetName": "band"},
    "tier": {"Description": "spatial tier", "Standard": "facet", "FacetName": "tier"},
    "roi": {"Description": "parcel", "Standard": "element"},
    "direction": {"Description": "what positive means", "Standard": "tested_direction"},
    "n": {"Description": "subjects", "Standard": "n"},
    "g": {"Description": "effect", "Standard": "effect_size", "EffectMeasure": "per_row"},
    "g_measure": {"Description": "the row's effect measure", "Standard": "effect_measure"},
    "lo": {"Description": "CI low", "Standard": "effect_ci_low"},
    "hi": {"Description": "CI high", "Standard": "effect_ci_high"},
    "p_raw": {"Description": "uncorrected p", "Standard": "p_uncorrected"},
    "p": {"Description": "corrected p, in the row's family", "Standard": "p_value", "PKind": "per_family"},
    "family": {"Description": "the row's correction family", "Standard": "correction_family"},
    "mde_note": {"Description": "why no mde", "Standard": "mde_note"},
}
FAMILIES = [
    {"id": "posthoc", "p_kind": "fwe", "method": "holm", "scope": "roi", "statement": "Holm over ROIs"},
    {"id": "alpha_bh", "p_kind": "fdr", "method": "BH", "scope": "band", "members": "roi[2]",
     "members_hash": "ab12", "statement": "BH-FDR q < 0.05 over ROIs within the band"},
]


def _eeg(**over):
    a = {"id": "eeg/roi/aperiodic_rest", "title": "Aperiodic", "description": "1/f fits per ROI",
         "analysis_type": "roi", "modality": "eeg", "domain": "aperiodic", "task": "rest",
         "atlas": {"name": "allen26", "version": "1"},
         "measures": ["aperiodic_exponent", "aperiodic_offset"], "role": "exploratory",
         "design": {"n": 24, "groups": {"KO": 12, "WT": 12}, "sessions": 24, "timepoints": ["p60"]},
         "inference": {"method": "LMM + emmeans", "families": FAMILIES},
         "effect": {"measure": "per_row", "definition": "Hedges' g for contrasts, omega2 for omnibus rows",
                    "ci_level": 0.95},
         "tables": [{"path": "tests.csv", "role": "tests", "rows": "one contrast in one ROI and band",
                     "description": "every test", "headline": True}],
         "figures": [{"path": "fig.png", "caption": "g per ROI", "kind": "brain", "measure": "aperiodic_exponent",
                      "contrast": "KO-WT", "facets": {"band": "alpha", "tier": "roi"}, "shows": "tests.csv",
                      "headline": True, "drawn_by": "analysis"}]}
    a.update(over)
    return a


def _eeg_table(f, columns=None, **values):
    rows = {"measure": ["aperiodic_exponent", "aperiodic_offset"], "contrast": ["KO-WT"] * 2,
            "band": ["alpha", "alpha"], "tier": ["roi", "roi"], "roi": ["V1", "M1"],
            "direction": ["KO > WT"] * 2, "n": [24, 24], "g": [0.9, 0.1], "g_measure": ["g", "omega2"],
            "lo": [0.1, -0.5], "hi": [1.7, 0.7], "p_raw": [0.01, 0.6], "p": [0.02, 0.6],
            "family": ["posthoc", "alpha_bh"], "mde_note": ["not computed: mixed model"] * 2, **values}
    pd.DataFrame(rows).to_csv(f / "tests.csv", index=False)
    write_columns(f / "tests.csv", {**EEG_COLUMNS, **(columns or {})})


@pytest.fixture
def eeg(tmp_path):
    f = tmp_path / "eeg"
    f.mkdir()
    _eeg_table(f)
    (f / "fig.png").write_bytes(b"\x89PNG")
    return f


def _check_eeg(f, analysis=None, version=None):
    a = analysis or _eeg()
    if version:
        a = {**a, "spec_version": version}
    write_analysis(f, a, _prov(), strict=False)
    (rep,) = check(f)
    return rep


def test_0_4_an_eeg_analysis_conforms(eeg):
    rep = _check_eeg(eeg)
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)


def test_0_4_a_0_3_folder_is_read_as_before_and_bumping_it_only_warns(folder):
    """The step-2 rule: a 0.3 folder keeps conforming, and declaring 0.4 adds warnings at most."""
    _with_mde(folder)
    plain = dict(MDE_COLUMNS["mde_pct"])
    plain.pop("PercentOf")
    write_columns(folder / "tests.tsv", {**COLUMNS, **MDE_COLUMNS}, {"mde_pct": plain})
    for version, warned in (("0.3.0", False), ("0.4.0", True)):
        write_analysis(folder, {**_analysis(), "spec_version": version}, _prov(), strict=False)
        (rep,) = check(folder)
        assert rep.ok, rep.errors
        assert any("PercentOf" in w for w in rep.warnings) is warned


def test_0_4_features_are_not_for_older_folders(eeg):
    rep = _check_eeg(eeg, version="0.3.0")
    joined = " | ".join(rep.errors)
    assert "are from 0.4; the folder declares 0.3" in joined
    for feature in ("'atlas'", "'domain'", "'task'", "modality 'eeg'", "inference.families",
                    "figures[].kind", "design.sessions"):
        assert feature in joined, feature
    assert "standard terms ['correction_family', 'effect_measure', 'p_uncorrected']" in joined
    assert "qualifiers ['FacetName']" in joined
    assert "values ['EffectMeasure per_row', 'PKind per_family']" in joined


@pytest.mark.parametrize("inference, says", [
    ({"method": "LMM", "families": FAMILIES, "correction": {"p_kind": "fdr", "family": "x", "statement": "x"}},
     "gives both 'correction' and 'families'"),
    ({"method": "LMM"}, "gives neither 'correction' and 'families'"),
    ({"method": "LMM", "families": FAMILIES + [FAMILIES[0]]}, "declared more than once"),
    ({"method": "LMM", "families": FAMILIES[:1]}, "names families inference does not declare: ['alpha_bh']"),
])
def test_0_4_correction_families(eeg, inference, says):
    assert says in " | ".join(_check_eeg(eeg, _eeg(inference=inference)).errors)


def test_0_3_still_needs_its_one_correction(folder):
    a = _analysis()
    a["inference"] = {"method": "Welch t"}
    write_analysis(folder, {**a, "spec_version": "0.3.0"}, _prov(), strict=False)
    assert "inference: missing required field 'correction'" in _errors(folder)


def test_0_4_rows_name_their_family_when_there_are_several(eeg):
    _eeg_table(eeg, family=["posthoc", ""])
    assert "1 row(s) give a p-value but no correction family" in " | ".join(_check_eeg(eeg).errors)
    cols = {k: v for k, v in EEG_COLUMNS.items() if k != "family"}
    pd.read_csv(eeg / "tests.csv").drop(columns="family").to_csv(eeg / "tests.csv", index=False)
    write_columns(eeg / "tests.csv", cols)
    assert "needs a column marked 'correction_family'" in " | ".join(_check_eeg(eeg).errors)


def test_0_4_a_p_value_kind_agrees_with_its_families(eeg):
    _eeg_table(eeg, columns={"p": {**EEG_COLUMNS["p"], "PKind": "fdr"}})
    assert "says PKind 'fdr', but its rows' families are ['fdr', 'fwe']" in " | ".join(_check_eeg(eeg).errors)
    _eeg_table(eeg, family=["alpha_bh", "alpha_bh"], columns={"p": {**EEG_COLUMNS["p"], "PKind": "fdr"}})
    assert _check_eeg(eeg).ok


def test_0_4_per_family_needs_families(folder):
    write_columns(folder / "tests.tsv", COLUMNS, {"p": {**COLUMNS["p"], "PKind": "per_family"}})
    write_analysis(folder, _analysis(), _prov(), strict=False)
    assert "but inference declares no families" in _errors(folder)


def test_0_4_several_facets_are_each_named(eeg):
    _eeg_table(eeg, columns={"tier": {"Description": "tier", "Standard": "facet"}})
    assert "names each one ('FacetName'); 'tier' has none" in " | ".join(_check_eeg(eeg).errors)
    _eeg_table(eeg, columns={"tier": {**EEG_COLUMNS["tier"], "FacetName": "band"}})
    assert "facet 'band' claimed by both 'band' and 'tier'" in " | ".join(_check_eeg(eeg).errors)


def test_0_4_figures_name_facets_and_tests_the_tables_have(eeg):
    a = _eeg()
    a["figures"][0]["facets"] = {"band": "alpha", "window": "early"}
    rep = _check_eeg(eeg, a)
    assert rep.ok and any("facets ['window'] are not named by" in w for w in rep.warnings), rep.warnings
    a["figures"][0]["facets"] = {"band": "gamma", "tier": "roi"}
    rep = _check_eeg(eeg, a)
    assert any("names a test with no row in the tests table" in w for w in rep.warnings), rep.warnings


@pytest.mark.parametrize("figure, says", [
    ({"shows": "other.csv"}, "shows 'other.csv', which is not one of its tables"),
])
def test_0_4_a_figure_shows_a_listed_table(eeg, figure, says):
    a = _eeg()
    a["figures"][0].update(figure)
    assert says in " | ".join(_check_eeg(eeg, a).errors)


def test_0_4_one_headline_figure_and_brain_figures_name_their_atlas(eeg):
    a = _eeg()
    a["figures"].append({**a["figures"][0], "path": "fig.png"})
    assert "more than one headline figure" in " | ".join(_check_eeg(eeg, a).errors)
    a = _eeg(tables=[{**_eeg()["tables"][0], "role": "elements"}])
    a.pop("atlas")
    assert "needs the atlas its elements are parcels of" in " | ".join(_check_eeg(eeg, a).errors)


def test_0_4_a_per_row_effect_names_each_rows_measure(eeg):
    _eeg_table(eeg, g_measure=["g", ""])
    assert "1 row(s) give an effect but not its measure" in " | ".join(_check_eeg(eeg).errors)


@pytest.mark.parametrize("over, says", [
    ({"domain": "vibes"}, "domain 'vibes' is not in the domain vocabulary"),
    ({"domain": "metabolites"}, "domain 'metabolites' is for mrs, in a eeg analysis"),
])
def test_0_4_domains_warn_not_fail(eeg, over, says):
    rep = _check_eeg(eeg, _eeg(**over))
    assert rep.ok and any(says in w for w in rep.warnings), (rep.errors, rep.warnings)


def test_0_4_task_is_a_bids_label(eeg):
    assert "is not a BIDS task label" in " | ".join(_check_eeg(eeg, _eeg(task="resting state")).errors)


def test_0_4_graph_metrics_belong_to_several_modalities(folder):
    write_analysis(folder, _analysis(id="func/roi/demo", modality="func", measures=["global_efficiency"]),
                   _prov(), strict=False)
    (rep,) = check(folder)
    assert not any("global_efficiency" in w for w in rep.warnings), rep.warnings


def test_0_4_eeg_measures_are_written_by_their_canonical_names(eeg):
    a = _eeg(measures=["exponent", "aperiodic_offset"])
    assert "measure 'exponent' is written 'aperiodic_exponent'" in " | ".join(_check_eeg(eeg, a).errors)


EQ = {"kind": {"Description": "test kind", "Standard": "test_kind"},
      "margin": {"Description": "equivalence bound", "Standard": "margin", "Units": "Hedges' g"},
      "equivalent": {"Description": "TOST concludes equivalence", "Standard": "equivalent"}}


def test_0_4_an_equivalence_row_states_its_margin(eeg):
    _eeg_table(eeg, columns=EQ, kind=["two_group", "equivalence"], margin=["", "0.5"], equivalent=["", "true"])
    assert _check_eeg(eeg).ok
    _eeg_table(eeg, columns=EQ, kind=["two_group", "equivalence"], margin=["", ""], equivalent=["", "true"])
    assert "1 equivalence row(s) give no margin" in " | ".join(_check_eeg(eeg).errors)
    _eeg_table(eeg, columns=EQ, kind=["two_group", "equivalence"], margin=["", "-1"], equivalent=["", "maybe"])
    errors = " | ".join(_check_eeg(eeg).errors)
    assert "(margin) is not a number above 0" in errors and "(equivalent) is not true/false" in errors


BAYES = {
    "post": {"Description": "posterior median of g", "Standard": "posterior_median"},
    "hdi_lo": {"Description": "HDI low", "Standard": "hdi_low", "CILevel": 0.95},
    "hdi_hi": {"Description": "HDI high", "Standard": "hdi_high", "CILevel": 0.95},
    "pd": {"Description": "probability of direction", "Standard": "p_direction"},
    "bf": {"Description": "Bayes factor", "Standard": "bf10", "Scale": "log10"},
    "rope": {"Description": "share in the ROPE", "Standard": "p_rope", "Rope": "|g| < 0.1"},
}


def _bayes(eeg, scale="log10", **values):
    cols = {k: v for k, v in EEG_COLUMNS.items() if k not in ("p", "p_raw", "family", "g", "g_measure", "lo", "hi")}
    rows = {"measure": ["aperiodic_exponent", "aperiodic_offset"], "contrast": ["KO-WT"] * 2,
            "band": ["alpha"] * 2, "tier": ["roi"] * 2, "roi": ["V1", "M1"], "direction": ["KO > WT"] * 2,
            "n": [24, 24], "mde_note": ["not computed: Bayesian"] * 2, "post": [0.8, 0.1],
            "hdi_lo": [0.2, -0.4], "hdi_hi": [1.4, 0.6], "pd": [0.99, 0.6], "bf": [1.2, -0.3],
            "rope": [0.01, 0.4], **values}
    pd.DataFrame(rows).to_csv(eeg / "tests.csv", index=False)
    write_columns(eeg / "tests.csv", {**cols, **BAYES}, {"bf": {**BAYES["bf"], "Scale": scale}})
    a = _eeg(inference={"method": "bayesian", "correction": {"p_kind": "none", "family": "none",
                                                             "statement": "no correction: posterior summaries"}},
             effect={"measure": "g", "definition": "posterior of Hedges' g"})
    return _check_eeg(eeg, a)


def test_0_4_a_bayesian_analysis_reports_posteriors_not_p_values(eeg):
    rep = _bayes(eeg)
    assert rep.ok and not rep.warnings, (rep.errors, rep.warnings)
    rep = _bayes(eeg, pd=[0.99, ""])
    assert "1 row(s) with no p_direction; every Bayesian row carries it" in " | ".join(rep.errors)
    rep = _bayes(eeg, post=[0.8, 0.9])
    assert "1 row(s) with a posterior median outside its HDI" in " | ".join(rep.errors)


def test_0_4_a_linear_bayes_factor_is_positive(eeg):
    assert _bayes(eeg, scale="linear", bf=[3.0, 0.5]).ok
    rep = _bayes(eeg, scale="linear")
    assert rep.errors == ["table 'tests.csv': 'bf' (bf10) is not a number above 0: ['-0.3']"], rep.errors


def test_0_4_smallest_effect_of_interest_and_readings(eeg):
    cols = {"sesoi": {"Description": "within-rat scatter", "Standard": "sesoi", "Basis": "repeat scans"},
            "reading": {"Description": "what the row shows", "Standard": "reading",
                        "Levels": {"effect": "beyond the scatter", "below_scatter": "detectable but smaller"}}}
    _eeg_table(eeg, columns=cols, sesoi=[0.3, 0.3], reading=["effect", "below_scatter"])
    rep = _check_eeg(eeg, _eeg(effect={**_eeg()["effect"], "sesoi": {"value": 0.3, "basis": "repeat scans"}}))
    assert rep.ok, rep.errors
    _eeg_table(eeg, columns=cols, sesoi=[0.3, 0], reading=["effect", "noise"])
    errors = " | ".join(_check_eeg(eeg).errors)
    assert "(sesoi) is not a number above 0" in errors
    assert "(reading) has values its Levels do not define: ['noise']" in errors
    _eeg_table(eeg, columns={"sesoi": {"Description": "x", "Standard": "sesoi"}}, sesoi=[0.3, 0.3])
    assert "'sesoi' is 'sesoi' and must state Basis" in " | ".join(_check_eeg(eeg).errors)
    a = _eeg(effect={**_eeg()["effect"], "sesoi": {"value": 0, "basis": "x"}})
    assert "effect.sesoi.value must be above 0" in " | ".join(_check_eeg(eeg, a).errors)


def test_0_4_a_decision_states_how_often_it_holds_with_no_effect(eeg):
    decision = {"rule": "any cluster counts", "outcome": "holds",
                "calibration": {"null_rate": 0.66, "datasets": 200, "method": "label reshuffles"},
                "rests_on": ["tests.csv"]}
    threshold = {"p_kind": "uncorrected", "alpha": 0.05, "statement": "TFCE p < 0.05 uncorrected"}
    tables = [{**_eeg()["tables"][0], "threshold": threshold}]
    assert _check_eeg(eeg, _eeg(decision=decision, tables=tables)).ok
    bad = {**decision, "calibration": {"null_rate": 66, "method": "x"}, "rests_on": ["clusters.csv"]}
    errors = " | ".join(_check_eeg(eeg, _eeg(decision=bad)).errors)
    assert "null_rate 66 is not in [0, 1]" in errors
    assert "rests on 'clusters.csv', which is not one of its tables" in errors


def test_0_4_a_map_says_how_its_space_derives_from_a_template(folder):
    (folder / "t.nii.gz").write_bytes(b"x")
    m = {"path": "t.nii.gz", "kind": "stat", "description": "t", "space": "SIGMA_study",
         "space_derivation": {"from": "SIGMA", "how": "transpose and two flips of the distributed template"}}
    write_analysis(folder, _analysis(maps=[m], design={"n": 20, "sessions": 40, "timepoints": ["p60", "p90"]}),
                   _prov(), strict=False)
    (rep,) = check(folder)
    assert rep.ok, rep.errors


def test_0_4_one_named_facet_keeps_the_tests_0_3_identity(folder):
    df = pd.read_csv(folder / "tests.tsv", sep="\t")
    df["window"] = ["p60_to_p90", "p60_to_p90"]
    df.to_csv(folder / "tests.tsv", sep="\t", index=False)
    (folder / "fig.png").write_bytes(b"x")
    write_columns(folder / "tests.tsv", COLUMNS,
                  {"window": {"Description": "window", "Standard": "facet", "FacetName": "window"}})
    for figure in ({"facets": {"window": "p60_to_p90"}}, {"facet": "p60_to_p90"}):
        fig = {"path": "fig.png", "caption": "x", "measure": "FA", "contrast": "A>B", **figure}
        write_analysis(folder, _analysis(figures=[fig]), _prov(), strict=False)
        (rep,) = check(folder)
        others = [w for w in rep.warnings if "no 'mde'" not in w]     # the fixture gives no MDE
        assert rep.ok and not others, (figure, rep.errors, rep.warnings)
