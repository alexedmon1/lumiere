"""What the gallery says about each analysis beyond its own folder.

**The findings that cite it.** A DUET finding names the analysis its numbers came from by the
``id`` in its ``analysis.json`` (DUET #165). The study's record writes those into
``<study>/duet/status.json`` (``records``, each finding with an ``analysis`` list), which this
reads, so each analysis can show its findings and link to them in the record page.

**Whether it ran on the code the study pins.** A study's ``study.toml`` pins each tool
(``[packages] name = "git+URL@ref"``); an analysis's ``provenance.json`` says which version of
its producer made it (``generated_by``, producer first). Compared, an analysis made with an older
version than the pin is flagged: its numbers may not be what the pinned code gives now.

Both are read when the gallery is built, from the study's own files; nothing is fetched, and a
study with neither file builds as before. Standard library only: on Python 3.10, which has no
``tomllib``, the ``[packages]`` table's ``name = "value"`` lines are read directly.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

#: A version as written by a package or ``git describe``: 0.7.0, v0.8.2-12-g0c7052e(-dirty).
_VERSION = re.compile(
    r"^v?(?P<base>\d+(?:\.\d+)*)(?:[-+.]?(?:(?P<ahead>\d+)-)?g(?P<sha>[0-9a-f]{7,40}))?(?P<dirty>-dirty)?$"
)
try:
    import tomllib
except ImportError:  # Python 3.10: read [packages] directly (see _packages_310)
    tomllib = None  # type: ignore[assignment]

_TABLE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*(?:#.*)?$")
_STRING = re.compile(r"""^\s*(?P<key>[A-Za-z0-9_.-]+|"[^"]+")\s*=\s*(?P<q>["'])(?P<value>.*?)(?P=q)\s*(?:#.*)?$""")


def _packages_310(text: str) -> dict[str, str]:
    """``[packages]``'s string values, without a TOML reader: all a pin is."""
    out: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        table = _TABLE.match(line)
        if table:
            inside = table["name"].strip() == "packages"
            continue
        m = _STRING.match(line) if inside else None
        if m:
            out[m["key"].strip('"')] = m["value"]
    return out

_PIN = re.compile(r"^git\+(?P<url>.+?)(?:\.git)?@(?P<ref>[^@#\s]+)$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def _name(text: str) -> str:
    return re.sub(r"[-_.]+", "-", str(text)).casefold()


def findings_by_analysis(study: Path, dest: Path) -> dict[str, list[dict[str, Any]]]:
    """Analysis id to the DUET findings that name it, each ``{id, text, status, href}``."""
    status = study / "duet" / "status.json"
    try:
        doc = json.loads(status.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    base = Path(os.path.relpath(status.parent, dest)).as_posix()
    out: dict[str, list[dict[str, Any]]] = {}
    for record in doc.get("records") or []:
        if not isinstance(record, dict) or record.get("kind") != "finding":
            continue
        for aid in record.get("analysis") or []:
            out.setdefault(str(aid), []).append({
                "id": record.get("id"), "text": record.get("text") or "", "status": record.get("status"),
                "href": f"{base}/{record.get('link') or 'record.html'}",
            })
    return out


def study_pins(study: Path) -> dict[str, str]:
    """Package name (normalised) to the ref ``study.toml`` pins it at."""
    try:
        text = (study / "study.toml").read_text(encoding="utf-8")
        packages = (tomllib.loads(text).get("packages") or {}) if tomllib else _packages_310(text)
    except (OSError, ValueError):
        return {}
    pins = {}
    for name, spec in packages.items():
        m = _PIN.match(str(spec).strip())
        if m:
            pins[_name(name)] = m["ref"]
    return pins


def _parts(version: str) -> tuple[tuple[int, ...], int, str, bool] | None:
    m = _VERSION.match(str(version).strip())
    if not m:
        return None
    base = tuple(int(x) for x in m["base"].split("."))
    return base, int(m["ahead"] or 0), m["sha"] or "", bool(m["dirty"])


def code_state(generated_by: list[dict[str, Any]], pins: dict[str, str]) -> dict[str, Any] | None:
    """How an analysis's producer compares with the study's pin of it, or None when unpinned.

    ``state`` is ``current`` (made by the pinned release or commit), ``older`` (an earlier
    version than the pin), ``newer`` (later than the pin: unreleased work, or the pin is behind),
    ``uncommitted`` (made from a working tree with changes) or ``unknown`` (versions that cannot
    be compared, e.g. a commit pin and a release version).
    """
    if not generated_by or not isinstance(generated_by[0], dict):
        return None
    producer = generated_by[0]
    ref = pins.get(_name(producer.get("Name") or ""))
    if ref is None:
        return None
    ran = str(producer.get("Version") or "")
    out = {"tool": producer.get("Name"), "ran": ran, "pinned": ref}
    parts = _parts(ran)
    if parts and parts[3]:
        return {**out, "state": "uncommitted"}
    commit = str(producer.get("CommitID") or (parts[2] if parts else "")).casefold()
    if _SHA.match(ref.casefold()):
        if commit and (commit.startswith(ref.casefold()) or ref.casefold().startswith(commit)):
            return {**out, "state": "current"}
        return {**out, "state": "unknown"}
    pinned = _parts(ref)
    if parts is None or pinned is None:
        return {**out, "state": "unknown"}
    width = max(len(parts[0]), len(pinned[0]))
    have = (parts[0] + (0,) * (width - len(parts[0])), parts[1])
    want = (pinned[0] + (0,) * (width - len(pinned[0])), pinned[1])
    state = "current" if have == want else "older" if have < want else "newer"
    return {**out, "state": state}
