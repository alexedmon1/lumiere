"""The study gallery shell (lumiere.gallery): one static folder from a study's analysis folders."""
import json
import re

import pandas as pd
import pytest

from lumiere import gallery, provenance, write_analysis, write_columns

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


def test_the_page_carries_lumieres_name_and_mark(study):
    page = gallery.build(study, SETTINGS).read_text(encoding="utf-8")
    assert "<title>Lumière - " in page and '<span class="word"><b>L</b>UMIÈRE</span>' in page
    assert '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' in page  # loads nothing
    # the stylesheet and script are addressed by their content, so no browser keeps a stale copy
    assert re.search(r'href="assets/gallery.css\?v=[0-9a-f]{10}"', page)
    assert re.search(r'src="assets/gallery.js\?v=[0-9a-f]{10}"', page)


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
    from lumiere.__main__ import main

    (study / "gallery.json").write_text(json.dumps(SETTINGS))
    assert main(["gallery", str(study)]) == 0
    assert capsys.readouterr().out.strip().endswith("index.html")


def test_a_gallery_built_under_the_old_name_is_still_rebuilt(study):
    """Galleries built before 2026-11-10 carry .neurobox-gallery; they are Lumière's too."""
    old = study / "gallery"
    old.mkdir()
    (old / "index.html").write_text("built before the rename")
    (old / ".neurobox-gallery").write_text("built")
    gallery.build(study, SETTINGS)
    assert (old / ".lumiere-gallery").is_file() and not (old / ".neurobox-gallery").exists()


def test_the_old_name_forwards_to_lumiere():
    import neurobox.gallery
    from neurobox.spec import analysis_id

    import lumiere
    import lumiere.spec
    import neurobox

    assert neurobox.gallery is lumiere.gallery and analysis_id is lumiere.spec.analysis_id
    assert neurobox.write_analysis is lumiere.write_analysis


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


def test_a_gallery_off_the_standard_place_is_warned_about(study, tmp_path):
    with pytest.warns(UserWarning, match="not the standard place"):
        gallery.build(study, SETTINGS, out=tmp_path / "scratch-gallery")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        gallery.build(study, SETTINGS)                       # <study>/gallery: no warning


def _made_by(folder, *generated_by):
    p = json.loads((folder / "provenance.json").read_text())
    p["generated_by"] = list(generated_by)
    (folder / "provenance.json").write_text(json.dumps(p))


def test_findings_that_cite_an_analysis_and_its_code_against_the_pin(tmp_path):
    """DUET #165's findings, from duet/status.json, and the producer's version against study.toml."""
    top = tmp_path / "study"
    res = top / "results"
    old = _analysis_folder(res, "eeg/roi/psd", "r1", modality="eeg", domain="spectral")
    same = _analysis_folder(res, "eeg/roi/aperiodic", "r1", modality="eeg", domain="aperiodic")
    later = _analysis_folder(res, "eeg/connectome/ppc", "r1", modality="eeg", atype="connectome")
    _made_by(old, {"Name": "source-analytics", "Version": "v0.7.0-3-g8135954"}, {"Name": "R", "Version": "4.6.1"})
    _made_by(same, {"Name": "source_analytics", "Version": "0.8.2"})
    _made_by(later, {"Name": "source-analytics", "Version": "v0.8.2-12-g0c7052e-dirty"})
    (top / "study.toml").write_text('[study]\nname = "s"\n[packages]\n'
                                    'source-analytics = "git+https://github.com/me/source-analytics.git@v0.8.2"\n')
    (top / "duet").mkdir()
    (top / "duet" / "status.json").write_text(json.dumps({"records": [
        {"id": "F001", "kind": "finding", "status": "recorded", "text": "Gamma is up", "link": "record.html#/finding/F001",
         "analysis": ["eeg/roi/psd"]},
        {"id": "CL001", "kind": "claim", "analysis": ["eeg/roi/psd"]},
    ]}))
    m = _manifest(gallery.build(top, {"paths": {"results": "results"}}))
    by_id = {a["id"]: a for a in m["analyses"].values()}
    assert by_id["eeg/roi/psd"]["findings"] == [{"id": "F001", "text": "Gamma is up", "status": "recorded",
                                                 "href": "../duet/record.html#/finding/F001"}]
    assert by_id["eeg/roi/aperiodic"]["findings"] == []
    assert by_id["eeg/roi/psd"]["code"]["state"] == "older"
    assert by_id["eeg/roi/aperiodic"]["code"]["state"] == "current"
    assert by_id["eeg/connectome/ppc"]["code"]["state"] == "uncommitted"
    assert m["code"] == {"current": 1, "older": 1, "uncommitted": 1} and m["findings"] == 1
    page = (top / "gallery" / "assets" / "gallery.js").read_text()
    assert 'parts[0] === "id"' in page and "made with older code" in page


def test_code_state_reads_releases_describes_and_commits():
    from lumiere.gallery.links import code_state

    def state(version, ref, commit=None):
        gb = {"Name": "tool", "Version": version, **({"CommitID": commit} if commit else {})}
        return (code_state([gb], {"tool": ref}) or {}).get("state")

    assert state("0.7.0", "v0.7.0") == "current"
    assert state("v0.7.0-2-gabcdef1", "v0.7.0") == "newer"
    assert state("0.6.9", "v0.7") == "older"
    assert state("v0.8.2-8-g8135954", "8135954aa") == "current"
    assert state("0.8.2", "8135954aa") == "unknown"
    assert state("0.8.2", "8135954aa", commit="8135954aa00") == "current"
    assert state("weird", "v1") == "unknown"
    assert code_state([{"Name": "other", "Version": "1"}], {"tool": "v1"}) is None
    assert code_state([], {"tool": "v1"}) is None


def test_pins_are_read_without_a_toml_reader_too():
    """Python 3.10 has no tomllib; the [packages] table is read directly, to the same result."""
    from lumiere.gallery.links import _packages_310

    text = ('[study]\nname = "s"  # the study\n[packages]\n'
            'source-analytics = "git+https://x/source-analytics.git@v0.8.2"\n'
            "neurofaune = 'git+https://x/neurofaune.git@9ec3a7f'  # by commit\n[other]\nnope = \"x\"\n")
    assert _packages_310(text) == {"source-analytics": "git+https://x/source-analytics.git@v0.8.2",
                                   "neurofaune": "git+https://x/neurofaune.git@9ec3a7f"}
