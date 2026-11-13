<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/lumiere-banner-dark.svg">
    <img src="docs/brand/lumiere-banner-light.svg" alt="Lumière" width="430">
  </picture>
</p>

<p align="center"><b>A study's results, in one light page.</b><br>
Every analysis of a study, MRI or EEG, as a gallery you open from the file system: figures, tables, what each
test found, the code that made it, and the Duet findings that cite it.</p>

---

Lumière is one of three tools for AI-assisted computational neuroscience, each kept separate:

| | |
|---|---|
| **Esprit** | the hub: every project, its decisions, jobs and files, so nothing is lost |
| **Duet** | the scientific record: hypotheses, findings and claims, read critically |
| **Lumière** | the results: what every analysis of a study found, shown the same way whichever tool made it |

It holds two things. **The gallery** turns a study's analysis folders into one page. **The results
specification** says what an analysis folder contains, so the gallery, or anyone, can read it without the tool
that made it; a checker and a small writer come with it.

## What you need

- **Python 3.10 or later.** Lumière uses only the standard library, so any analysis tool can install it
  without pulling in another tool's stack.
- **PyYAML**, only if your gallery settings are in `gallery.yaml` (otherwise use `gallery.json`). Analysis
  tools that build galleries for you already have it.
- **A browser.** The gallery is plain HTML, CSS and JavaScript with everything inside its folder: no server, no
  internet connection, nothing fetched.
- **Analysis folders that meet the results specification.** Today these come from
  [source-analytics](https://github.com/alexedmon1/source-analytics) (EEG) and
  [neurofaune](https://github.com/alexedmon1/neurofaune) (MRI); any script can write them (see
  [For tool authors](#for-tool-authors)).

## Install

```bash
pip install "lumiere @ git+https://github.com/alexedmon1/lumiere@<commit>"
```

Pin a commit: the specification is still a draft. This gives you the `lumiere` command (also
`python -m lumiere`) and the `lumiere` package.

## Build a study's gallery

A study is a folder with a `study.toml` (the tools it pins) and a `gallery.yaml` (what goes in its gallery).
The gallery is written to `<study>/gallery/`, beside them, so Esprit and Duet find it without being told.

**From an analysis tool**, the usual way: the tool draws its figures and writes its analysis folders, then
calls Lumière. For EEG with source-analytics:

```bash
source-analytics gallery build --study study.yaml
```

neurofaune does the same for MRI studies.

**From Lumière directly**, when the analysis folders are already written:

```bash
lumiere gallery path/to/study                 # reads gallery.yaml or gallery.json there
lumiere gallery path/to/study --out /tmp/try  # elsewhere, say to compare with an older gallery
```

Then open `path/to/study/gallery/index.html`. To look at it from another computer, serve the folder and
tunnel the port:

```bash
python -m http.server 8799 --bind 127.0.0.1 --directory path/to/study/gallery
ssh -L 8799:127.0.0.1:8799 <you>@<that computer>      # then open http://localhost:8799
```

Esprit also links each study's gallery from its project page.

### `gallery.yaml`

```yaml
name: FORGE treatment                     # the gallery's title
description: Mouse FXS, AAV treatment      # optional
paths:
  results: [analyses/results, preprocessing/derivatives/rest_shell_mc/qc]   # where the analysis folders are
  gallery: ./gallery                      # where to write it (the standard place)
links: [{label: Preprocessing QC, path: ../preprocessing/qc/index.html}]
groups: {WT_VEH: WT vehicle, KO_VEH: KO vehicle}   # labels for the design's groups
group_order: [WT_VEH, KO_VEH]
variants: {reconstruction: [roi_based, cartesian_mc]}   # the order of each variant's values
sections:                                 # optional; by default by modality, then domain
  - key: dwi_tbss
    label: TBSS (randomise)
    group: Diffusion
    match: {analysis_type: tbss, modality: dwi}   # a value, or a list of values
    note: shown at the top of the section
```

An analysis goes under the first section it matches, on `analysis_type`, `modality`, `domain`, `role`,
`task`, `measures` or `id` (a shell-style pattern); one that matches none goes under "Other". Paths are
relative to the settings file. A folder that does not meet the specification is left out, and the gallery says
which and why.

## What the page shows

- **A top bar and the sections down the left**, laid out as Esprit and Duet are: the study's name, a search
  (`/` to start typing), and a light or dark button that follows your computer until you press it.
- **An overview**: how many analyses, figures and tables, by modality and level.
- **Each analysis**, under its section:
  - *About this analysis*: its method and how to read it, with the caveats its tool states.
  - *Summary*: what was found, not only what was tested: for each declared contrast, the tests with a
    significant result at every level the analysis reports, the strongest effect, and equivalence results
    counted apart.
  - *Figures*, grouped by what they show (measure, contrast, band), each opening full size.
  - *Tables*, sortable, every column described, nothing truncated.
  - *What produced this*: the tool, its version and the run, flagged when the study pins a different version.
  - *The Duet findings that cite it*, each opening its place in the study's Duet record.
- **A permanent address for each analysis**: `index.html#/id/<analysis id>` opens whichever run is current.

The gallery is rebuilt, never edited: a rebuild replaces it whole, and never touches a folder Lumière did not
make.

## Check analysis folders

```bash
lumiere check path/to/results          # every analysis folder at or under the path
lumiere check path/to/results --json   # one JSON report per folder
```

Each folder gets `OK` or `FAIL` with its errors and warnings; the exit code is 0 only when every folder
passes.

## For tool authors

An analysis folder holds `analysis.json` (what was analysed and how, and the tables and figures it lists),
`provenance.json` (the code and inputs that produced it) and its tables, each with a column dictionary that
maps its columns to standard terms: estimate, p value, effect size, minimum detectable effect and the rest.
The specification is [`docs/RESULTS_SPEC.md`](docs/RESULTS_SPEC.md);
[`docs/RESULTS_PRODUCERS.md`](docs/RESULTS_PRODUCERS.md) is the recipe for producing it from any tool or
script. The writer does the bookkeeping:

```python
from lumiere import write_analysis, write_columns, provenance
```

`write_columns` writes a table's dictionary, `provenance` builds the provenance record, and
`write_analysis` writes both JSON files and checks the folder. A figure can say what it shows (`measure`,
`contrast`, `facets`, `kind`, `shows`), so the gallery groups and filters figures by those rather than by
file names.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
ruff check src tests
```

The page is `src/lumiere/gallery/index.html` and `static/` (`gallery.css`, `gallery.js`, and the vendored
GLightbox and Tablesort, with their notices in `static/vendor/NOTICE.md`). `CHANGELOG.md` lists every change
to the specification and the gallery.

## Where it came from

The specification began in neurofaune as `neurofaune.results` (0.3.0) and moved here on 2026-11-03, so EEG
tools could use it without installing neurofaune, which re-exports it. The repository was called
`neurobox-dev`, a working name, until 2026-11-10, when the gallery was named Lumière (light, in French, beside
Esprit and Duet) and the repository, package and command with it; GitHub sends the old address here.
Galleries built before the rename carry `.neurobox-gallery` and are rebuilt as Lumière's. The old name
`neurobox` forwarded to `lumiere` until 2026-11-13, when the last tool had moved. The identifier written in
each `analysis.json` is still `"neurofaune.results"`, so folders written before the rename stay valid.

## Licence

MIT. GLightbox and Tablesort are MIT too (`src/lumiere/gallery/static/vendor/NOTICE.md`).
