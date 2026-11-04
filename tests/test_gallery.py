"""The study gallery shell (neurobox.gallery): one static folder from a study's analysis folders."""
import json
import re

import pandas as pd
import pytest

from neurobox import gallery, provenance, write_analysis, write_columns

COLUMNS = {
    "measure": {"Description": "measure", "Standard": "measure"},
    "contrast": {"Description": "test id", "Standard": "contrast"},
    "direction": {"Description": "what positive means", "Standard": "tested_direction"},
    "n": {"Description": "subjects", "Standard": "n"},
    "d": {"Description": "d", "Standard": "effect_size", "EffectMeasure": "d"},
    "lo": {"Description": "CI low", "Standard": "effect_ci_low"},
    "hi": {"Description": "CI high", "Standard": "effect_ci_high"},
    "p": {"Description": "p", "Standard": "p_value", "PKind": "fdr"},
    "mde_note": {"Description": "why no mde", "Standard": "mde_note"},
    "report": {"Description": "a per-recording report"},
    "frac": {"Description": "share of the mask significant", "Standard": "frac_significant"},
}


def _analysis_folder(root, aid, run, modality="dwi", atype="roi", title="Demo", domain=None, report=True,
                     supersedes=None, **extra):
    f = root.joinpath(*aid.split("/"), run)
    f.mkdir(parents=True)
    (f / "reports").mkdir()
    (f / "reports" / "a.html").write_text("<p>report</p>")
    pd.DataFrame({"measure": ["FA"], "contrast": ["A>B"], "direction": ["A > B"], "n": [20], "d": [0.5],
                  "lo": [0.1], "hi": [0.9], "p": [0.01], "mde_note": ["not computed: demo"], "frac": [0.1],
                  "report": ["reports/a.html" if report else "nowhere.html"]}).to_csv(f / "tests.csv", index=False)
    write_columns(f / "tests.csv", COLUMNS)
    (f / "fig.png").write_bytes(b"\x89PNG")
    a = {"id": aid, "title": title, "description": "a demonstration", "analysis_type": atype,
         "modality": modality, "measures": ["FA"], "role": "exploratory", "design": {"n": 20},
         "inference": {"method": "t", "correction": {"p_kind": "fdr", "family": "x", "statement": "BH"}},
         "effect": {"measure": "d", "definition": "Cohen's d"},
         "run": {"id": run, **({"supersedes": [supersedes]} if supersedes else {})},
         "tables": [{"path": "tests.csv", "role": "tests", "rows": "a test", "description": "tests"}],
         "figures": [{"path": "fig.png", "caption": "a figure", "kind": "summary"}]}
    if domain:
        a["domain"] = domain
    a.update(extra)
    write_analysis(f, a, provenance([{"Name": "demo", "Version": "1"}], status="completed", start="2026"))
    return f


def _manifest(index):
    text = index.read_text()
    return json.loads(re.search(r"window\.GALLERY = (.*);</script>", text).group(1).replace("<\\/", "</"))


@pytest.fixture
def study(tmp_path):
    res = tmp_path / "study" / "results"
    _analysis_folder(res, "dwi/tbss/h1", "2026-10-01", atype="tbss")
    _analysis_folder(res, "dwi/tbss/h1", "2026-10-05", atype="tbss", supersedes="2026-10-01")  # a later run
    _analysis_folder(res, "anat/roi/volumes", "r1", modality="anat")
    _analysis_folder(res, "eeg/roi/aperiodic", "r1", modality="eeg", domain="aperiodic")
    bad = res / "broken"
    bad.mkdir()
    (bad / "analysis.json").write_text(json.dumps({"spec": "neurofaune.results", "spec_version": "0.4.0"}))
    return tmp_path / "study"


SETTINGS = {"name": "Demo study", "paths": {"results": "results", "gallery": "gallery"},
            "links": [{"label": "QC", "path": "qc/index.html"}],
            "groups": {"A": "Group A"},
            "sections": [{"key": "tbss", "label": "TBSS", "group": "Diffusion", "note": "read the caveat",
                          "match": {"analysis_type": "tbss", "modality": "dwi"}},
                         {"key": "msme", "label": "Relaxometry", "match": {"modality": "msme"}},
                         {"key": "eeg", "label": "EEG", "match": {"id": "eeg/*"}}]}


def test_a_gallery_is_built_from_the_analysis_folders(study):
    index = gallery.build(study, SETTINGS)
    assert index == study / "gallery" / "index.html"
    m = _manifest(index)
    sections = {s["key"]: s for s in m["sections"]}
    assert len(sections["tbss"]["analyses"]) == 1 and sections["tbss"]["note"] == "read the caveat"
    assert sections["msme"]["analyses"] == []                            # shown as "no results yet"
    assert [m["analyses"][k]["id"] for k in sections["eeg"]["analyses"]] == ["eeg/roi/aperiodic"]
    assert [m["analyses"][k]["id"] for k in sections["other"]["analyses"]] == ["anat/roi/volumes"]
    h1 = m["analyses"][sections["tbss"]["analyses"][0]]
    assert h1["run"]["id"] == "2026-10-05" and len(h1["earlier_runs"]) == 1  # newest run, others listed
    assert [f["id"] for f in m["not_shown"]] == [None] and m["not_shown"][0]["errors"]
    assert m["links"] == [{"label": "QC", "href": "../qc/index.html"}]
    t = h1["tables"][0]
    assert (study / "gallery" / t["path"]).is_file() and (study / "gallery" / h1["figures"][0]["path"]).is_file()
    assert t["columns"]["d"]["Standard"] == "effect_size" and t["rows"][0][4] == "0.5"
    # a column of paths that exist beside the analysis becomes links, relative to the page
    assert (study / "gallery" / t["links"]["report"][0][0]).resolve().read_text() == "<p>report</p>"
    assert (study / "gallery" / "assets" / "gallery.js").is_file()


def test_paths_that_do_not_exist_stay_text(study, tmp_path):
    _analysis_folder(study / "results", "anat/roi/thick", "r1", modality="anat", report=False)
    m = _manifest(gallery.build(study, SETTINGS))
    a = next(a for a in m["analyses"].values() if a["id"] == "anat/roi/thick")
    assert a["tables"][0]["links"] == {}


def test_default_sections_are_by_modality_and_domain(study):
    m = _manifest(gallery.build(study, {"paths": {"results": "results"}}))
    labels = {(s["group"], s["label"]) for s in m["sections"]}
    assert ("EEG", "Aperiodic") in labels and ("DWI", "Tbss") in labels


def test_text_from_results_cannot_close_the_script(study):
    _analysis_folder(study / "results", "anat/roi/evil", "r1", modality="anat",
                     title="</script><script>alert(1)</script>")
    text = gallery.build(study, SETTINGS).read_text()
    assert "</script><script>alert" not in text
    assert _manifest(study / "gallery" / "index.html")


def test_the_gallery_never_replaces_the_study(study):
    with pytest.raises(gallery.GalleryError):
        gallery.build(study, {"paths": {"results": "results", "gallery": "."}})
    with pytest.raises(gallery.GalleryError):
        gallery.build(study, {"paths": {"results": "results"}, "sections": [{"key": "x", "match": {"colour": 1}}]})


def test_cli_builds_from_a_json_settings_file(study, capsys):
    from neurobox.__main__ import main

    (study / "gallery.json").write_text(json.dumps(SETTINGS))
    assert main(["gallery", str(study)]) == 0
    assert capsys.readouterr().out.strip().endswith("index.html")


def test_a_folder_the_shell_did_not_build_is_never_replaced(study):
    other = study / "gallery"
    other.mkdir()
    (other / "index.html").write_text("another tool's gallery")
    with pytest.raises(gallery.GalleryError, match="was not built by this shell"):
        gallery.build(study, SETTINGS)
    assert (other / "index.html").read_text() == "another tool's gallery"
    (other / "index.html").unlink()
    gallery.build(study, SETTINGS)                        # empty: fine
    gallery.build(study, SETTINGS)                        # its own: rebuilt
    assert (other / gallery.MARKER).is_file()


def test_the_page_gets_variants_contrasts_and_the_vocabularies(tmp_path):
    """What the ported lightbox front end reads instead of guessing (spec 0.4.1)."""
    res = tmp_path / "study" / "results"
    contrasts = [{"id": "A>B", "label": "A over B", "kind": "contrast", "tier": "phenotype"}]
    for value, label in (("roi_based", "ROI-based"), ("cartesian_mc", "MC Cartesian")):
        _analysis_folder(res, f"eeg/roi/psd/{value}", "r1", modality="eeg", domain="spectral", contrasts=contrasts,
                         measures=["FA", "band_power"],
                         variant={"of": "eeg/roi/psd", "axis": "reconstruction", "value": value, "label": label})
    _analysis_folder(res, "eeg/roi/aperiodic", "r1", modality="eeg", domain="aperiodic", measures=["FA", "aperiodic_exponent"])
    settings = {"paths": {"results": "results"}, "variants": {"reconstruction": ["roi_based", "cartesian_mc"]}}
    index = gallery.build(tmp_path / "study", settings)
    m = _manifest(index)
    psd = [a for a in m["analyses"].values() if a["id"].startswith("eeg/roi/psd/")]
    assert {a["variant"]["value"] for a in psd} == {"roi_based", "cartesian_mc"}
    assert psd[0]["contrasts"] == contrasts
    assert [d["name"] for d in m["domains"]] == ["spectral", "aperiodic"]          # the vocabulary's order
    assert set(m["measures"]) == {"FA", "band_power", "aperiodic_exponent"} and m["measures"]["band_power"]
    assert m["variant_order"] == {"reconstruction": ["roi_based", "cartesian_mc"]}
    assets = index.parent / "assets"
    for name in ("gallery.js", "gallery.css", "vendor/glightbox.min.js", "vendor/glightbox.min.css",
                 "vendor/tablesort.min.js", "vendor/NOTICE.md"):
        assert (assets / name).is_file(), name
    page = index.read_text()
    assert "assets/vendor/glightbox.min.js" in page and 'id="sidebar-nav"' in page
