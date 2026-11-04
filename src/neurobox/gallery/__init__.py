"""One study's gallery: a static folder built from its analysis folders.

Every analysis tool builds its studies' galleries the same way: it writes its
analysis folders (``analysis.json``, tables with column dictionaries, the figures
it draws, listed in ``analysis.json``), then calls :func:`build` with the study's
gallery settings (``gallery.yaml`` at the study's top, parsed by the tool). The
shell reads only those files; nothing tool-specific crosses over.

The gallery is one folder with an ``index.html`` that works from the file system
(no server, no fetch): the manifest is inlined, and each analysis's listed tables
and figures are copied beside it. Rebuilt, never edited.

``gallery.yaml``::

    name: FORGE treatment                    # the gallery's title
    description: ...                         # optional
    paths:
      results: [analyses/results, preprocessing/derivatives/rest_shell_mc/qc]
      gallery: ./gallery                     # where the gallery is written
    links: [{label: Preprocessing QC, path: ../preprocessing/qc/index.html}]
    groups: {WT_VEH: WT vehicle}             # optional labels for design groups
    group_order: [WT_VEH, KO_VEH]
    variants: {reconstruction: [roi_based, cartesian_mc]}   # optional order of each axis's values
    sections:                                # optional; default: by modality, then domain
      - key: dwi_tbss
        label: TBSS (randomise)
        group: Diffusion
        match: {analysis_type: tbss, modality: dwi}   # a value, or a list of values
        note: shown at the top of the section

An analysis is listed under the first section it matches, on ``analysis_type``,
``modality``, ``domain``, ``role``, ``task``, ``measures`` (any in common) or
``id`` (shell-style pattern); one matching none goes under "Other". Paths are
relative to the settings file. Standard library only.
"""
from __future__ import annotations

import fnmatch
import html
import json
import os
import shutil
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..check import check, read_table
from ..spec import (
    ANALYSIS_JSON,
    PROVENANCE_JSON,
    SPEC_VERSION,
    domain_vocabulary,
    measure_vocabulary,
)

HERE = Path(__file__).parent
#: Marks a folder this shell built, which a rebuild may replace.
MARKER = ".neurobox-gallery"
#: Rows of a table embedded in the page; the full table is copied and linked.
MAX_ROWS = 500
MATCH_FIELDS = ("analysis_type", "modality", "domain", "role", "task", "measures", "id")


class GalleryError(ValueError):
    """Settings the shell cannot build from."""


def load_settings(path: Path) -> dict:
    """A ``gallery.yaml`` (with PyYAML installed) or ``gallery.json``, as a dict."""
    path = Path(path)
    text = path.read_text()
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:                     # pragma: no cover - depends on install
        raise GalleryError(f"{path.name}: reading YAML needs PyYAML; pass the settings as JSON") from exc
    return yaml.safe_load(text) or {}


def _paths(value: Any) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else [str(v) for v in value]


def matches(analysis: dict, match: dict) -> bool:
    """Whether an analysis meets every condition of a section's ``match``."""
    for key, want in (match or {}).items():
        if key not in MATCH_FIELDS:
            raise GalleryError(f"section match on {key!r}: one of {', '.join(MATCH_FIELDS)}")
        wanted = want if isinstance(want, list) else [want]
        have = analysis.get(key)
        if key == "measures":
            if not set(have or []) & set(wanted):
                return False
        elif key == "id":
            if not any(fnmatch.fnmatchcase(str(have), str(w)) for w in wanted):
                return False
        elif have not in wanted:
            return False
    return True


def _default_sections(analyses: list[dict]) -> list[dict]:
    """By modality, then domain (or analysis type): what a study gallery groups by
    when its settings name no sections."""
    seen: dict[str, dict] = {}
    for a in analyses:
        modality = a.get("modality") or "other"
        sub = a.get("domain") or a.get("analysis_type") or "other"
        key = f"{modality}_{sub}"
        if key not in seen:
            seen[key] = {"key": key, "group": modality.upper() if len(modality) <= 4 else modality.title(),
                         "label": sub.replace("_", " ").capitalize(),
                         "match": {"modality": modality, **({"domain": sub} if a.get("domain") else
                                                            {"analysis_type": sub})}}
    return sorted(seen.values(), key=lambda s: (s["group"], s["label"]))


def _slug(text: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text.lower())
    return out.strip("_") or "analysis"


def _link_columns(folder: Path, headers: list[str], rows: list[dict], index_dir: Path) -> dict[str, list]:
    """Columns whose every value is a relative path to a file beside the analysis (a
    recording's report, say): column -> its values rewritten relative to the gallery's
    page, each a list (a cell may list several, separated by '; '). Only paths that
    exist become links."""
    out: dict[str, list] = {}
    for h in headers:
        values = [r.get(h, "") for r in rows]
        cells = [[x for x in v.split("; ") if x] for v in values]
        flat = [x for c in cells for x in c]
        if not flat or any("://" in x or x.startswith(("/", "\\")) for x in flat):
            continue
        sample = flat[:20]
        if not all("." in Path(x).name and (folder / x).is_file() for x in sample):
            continue
        out[h] = [[Path(os.path.relpath((folder / x).resolve(), index_dir)).as_posix() for x in c] for c in cells]
    return out


def _table(folder: Path, entry: dict, dest: Path, rel: str, index_dir: Path | None = None) -> dict | None:
    src = folder / entry.get("path", "")
    if not src.is_file():
        return None
    target = dest / entry["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    dictionary = {}
    if src.with_suffix(".json").is_file():
        shutil.copy2(src.with_suffix(".json"), target.with_suffix(".json"))
        dictionary = json.loads(src.with_suffix(".json").read_text())
    headers, rows = read_table(src)
    links = _link_columns(folder, headers, rows[:MAX_ROWS], index_dir) if index_dir else {}
    return {
        "path": f"{rel}/{entry['path']}", "name": Path(entry["path"]).name,
        "role": entry.get("role"), "rows_are": entry.get("rows"), "description": entry.get("description"),
        "headline": bool(entry.get("headline")), "threshold": entry.get("threshold"),
        "columns": {c: {k: v for k, v in (dictionary.get(c) or {}).items()
                        if k in ("Description", "Standard", "Units", "EffectMeasure", "PKind", "Levels")}
                    for c in headers},
        "headers": headers, "rows": [[r.get(h, "") for h in headers] for r in rows[:MAX_ROWS]],
        "total_rows": len(rows), "links": links,
    }


def _figure(folder: Path, entry: dict, dest: Path, rel: str) -> dict | None:
    src = folder / entry.get("path", "")
    if not src.is_file():
        return None
    target = dest / entry["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    keep = ("caption", "kind", "measure", "contrast", "facet", "facets", "shows", "headline", "drawn_by")
    return {"path": f"{rel}/{entry['path']}", **{k: entry[k] for k in keep if k in entry}}


def _provenance(folder: Path) -> dict:
    try:
        p = json.loads((folder / PROVENANCE_JSON).read_text())
    except (OSError, ValueError):
        return {}
    run = p.get("run") or {}
    return {"generated_by": p.get("generated_by") or [], "status": run.get("status"),
            "start": run.get("start"), "end": run.get("end"), "subjects": (p.get("subjects") or {}).get("n")}


def collect(roots: list[Path]) -> list[tuple[Path, dict, Any]]:
    """Every conforming analysis folder under ``roots``: (folder, analysis.json, report)."""
    out, seen = [], set()
    for root in roots:
        if not Path(root).exists():
            continue
        for rep in check(root):
            folder = Path(rep.folder).resolve()
            if folder in seen:
                continue
            seen.add(folder)
            try:
                analysis = json.loads((folder / ANALYSIS_JSON).read_text())
            except (OSError, ValueError):
                continue
            out.append((folder, analysis, rep))
    return out


def build(study: Path, settings: dict | None = None, out: Path | None = None) -> Path:
    """Build the study's gallery; the path of its ``index.html``.

    ``study`` is the folder the settings' paths are relative to (where
    ``gallery.yaml`` is); ``settings`` its parsed contents (read from the folder's
    ``gallery.yaml`` or ``gallery.json`` when omitted); ``out`` overrides
    ``paths.gallery`` (default ``<study>/gallery``). The output folder is replaced.
    Folders that do not conform are left out and listed on the page.
    """
    study = Path(study).resolve()
    if settings is None:
        found = [study / n for n in ("gallery.yaml", "gallery.yml", "gallery.json") if (study / n).is_file()]
        if not found:
            raise GalleryError(f"no gallery.yaml or gallery.json in {study}")
        settings = load_settings(found[0])
    paths = settings.get("paths") or {}
    roots = [(study / p).resolve() for p in _paths(paths.get("results"))] or [study]
    dest = Path(out).resolve() if out else (study / (paths.get("gallery") or "gallery")).resolve()
    if dest == study or dest in roots:
        raise GalleryError(f"the gallery folder {dest} would replace the study's own files")
    if dest.exists():
        if any(dest.iterdir()) and not (dest / MARKER).is_file():
            raise GalleryError(f"{dest} is not empty and was not built by this shell (no {MARKER}); "
                               "choose another output folder, or move it away first")
        shutil.rmtree(dest)
    (dest / "files").mkdir(parents=True)

    found = collect(roots)
    analyses, failed = [], []
    used: set[str] = set()
    for folder, a, rep in found:
        if not rep.ok:
            failed.append({"folder": str(folder), "id": a.get("id"), "errors": rep.errors[:5]})
            continue
        slug = _slug(f"{a.get('id', folder.name)}__{(a.get('run') or {}).get('id', '')}")
        while slug in used:
            slug += "_"
        used.add(slug)
        rel = f"files/{slug}"
        target = dest / rel
        target.mkdir(parents=True)
        tables = [t for t in (_table(folder, e, target, rel, dest) for e in a.get("tables") or []) if t]
        figures = [f for f in (_figure(folder, e, target, rel) for e in a.get("figures") or []) if f]
        analyses.append({
            "key": slug, "id": a.get("id"), "run": a.get("run") or {}, "title": a.get("title"),
            "description": a.get("description"),
            **{k: a.get(k) for k in ("analysis_type", "modality", "modalities", "domain", "task", "atlas",
                                     "measures", "role", "design", "effect", "decision", "caveats",
                                     "references", "retired", "inference", "contrasts", "variant")},
            "spec_version": a.get("spec_version"), "warnings": rep.warnings,
            "tables": tables, "figures": figures, "maps": [m.get("path") for m in a.get("maps") or []],
            "provenance": _provenance(folder),
        })

    # one entry per analysis id: its newest run, with the others listed as earlier runs
    by_id: dict[str, list[dict]] = {}
    for a in analyses:
        by_id.setdefault(a["id"], []).append(a)
    current = []
    for runs in by_id.values():
        runs.sort(key=lambda a: str(a["run"].get("id", "")), reverse=True)
        head = dict(runs[0])
        head["earlier_runs"] = [r["key"] for r in runs[1:]]
        current.append(head)
    current.sort(key=lambda a: str(a["id"]))

    sections = settings.get("sections") or _default_sections(current)
    placed: dict[str, list[str]] = {s.get("key") or _slug(s.get("label", "section")): [] for s in sections}
    other = []
    for a in current:
        for s in sections:
            if matches(a, s.get("match") or {}):
                placed[s.get("key") or _slug(s.get("label", "section"))].append(a["key"])
                a["section"] = s.get("key") or _slug(s.get("label", "section"))
                break
        else:
            other.append(a["key"])
            a["section"] = "other"
    nav = [{"key": k, "label": s.get("label", k), "group": s.get("group"), "note": s.get("note"),
            "analyses": placed[k]} for k, s in ((s.get("key") or _slug(s.get("label", "section")), s)
                                                for s in sections)]
    if other:
        nav.append({"key": "other", "label": "Other", "group": None, "note": None, "analyses": other})

    links = []
    for link in settings.get("links") or []:
        href = link.get("href") or link.get("path") or ""
        if href and "://" not in href:
            href = Path(os.path.relpath((study / href).resolve(), dest)).as_posix()
        links.append({"label": link.get("label", href), "href": href})

    # what the page orders and explains by, from the vocabularies (never from file names)
    domains = domain_vocabulary()
    used_domains = {a.get("domain") for a in current if a.get("domain")}
    domain_list = [{"name": d, "description": domains[d].get("description")} for d in domains if d in used_domains]
    domain_list += [{"name": d, "description": None} for d in sorted(used_domains - set(domains))]
    vocab = measure_vocabulary()
    measures = {m: vocab[m].get("description") for a in current for m in a.get("measures") or [] if m in vocab}

    built = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "title": settings.get("name") or settings.get("title") or study.name,
        "description": settings.get("description"), "links": links,
        "group_labels": settings.get("groups") or {}, "group_order": settings.get("group_order") or [],
        "sections": nav, "analyses": {a["key"]: a for a in current},
        "domains": domain_list, "measures": measures, "variant_order": settings.get("variants") or {},
        "runs": {a["key"]: a for a in analyses},
        "not_shown": failed, "built": built, "spec_version": SPEC_VERSION,
        "generator": settings.get("generator"),
    }
    shutil.copytree(HERE / "static", dest / "assets")
    data = json.dumps(manifest, default=str).replace("</", "<\\/")
    page = string.Template((HERE / "index.html").read_text()).substitute(
        title=html.escape(manifest["title"]), manifest=data, built=html.escape(built))
    (dest / "index.html").write_text(page, encoding="utf-8")
    (dest / MARKER).write_text(f"built {built}; rebuilt by neurobox.gallery.build, never edited\n")
    return dest / "index.html"

