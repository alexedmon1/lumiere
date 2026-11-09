# Results specification — `neurofaune.results` 0.4.0

What an analysis writes so that **anyone can read its results without the package
that produced them**: a plain pandas script, a manuscript table, a study gallery.
Producers are neurofaune, neurovrai, source-analytics, source-localization and any
study's own orchestration scripts; `RESULTS_PRODUCERS.md` says how each one meets this.
The specification, its JSON Schemas (`src/neurobox/schemas/`) and the conformance
checker (`python -m neurobox check`) live in **neurobox-dev** (a working name). They
moved there from neurofaune, unchanged, on 2026-11-03. It is optional for every tool:
neurofaune takes it as an extra (`neurofaune[results]`) and re-exports it as
`neurofaune.results`; without it, neurofaune still writes its tables but not their
descriptions, and `neurofaune results check` says how to install it.

**Readers.** A study's gallery reads it. Today that is source-lightbox for EEG studies;
its page shell is moving into neurobox-dev, so that each tool's `gallery build`
(neurofaune for MRI, source-analytics for EEG) builds its studies' galleries from these
files. The identifier in every file stays `"neurofaune.results"` until the final name.

**Status: 0.4.2, draft.** It becomes 1.0.0 when one MRI study (cuprizone) and one EEG
study (FORGE) both build their galleries from it end to end. Until then a minor version may change a field;
from 1.0.0 on, versions follow semver and a reader written for 1.x reads every 1.y.
0.2 adds identity and vocabulary (§3.1): what one analysis is, how it is named, and
the words a reader groups analyses by; and runs (§3.2): the tests of one analysis run
at different times, each run in a folder of its own. 0.3 adds the minimum detectable
effect (§5.1): beside each test, the smallest difference its design could have detected.
0.4 makes one schema cover EEG as well as MRI (the `eeg` modality, `domain`, `task` and
`atlas`; §3.1), lets a table carry what EEG and Bayesian analyses report (named facets and
correction families, equivalence tests, per-row effect measures, posteriors; §5.2-§5.5),
and adds what cuprizone's first real run of the spec found missing (step 2 of the results
plan, 2026-11-03): what an MDE percent is a percent of (§5.1), the smallest effect of
interest and readings against it (§5.6), how often a decision rule holds with no effect
and which rows it rests on (§3.4), a space derived from a template, and sessions and
timepoints in the design (§3.5). Figures say what they are and what they show (§3.3).
Every 0.4 addition is optional: a 0.3 folder conforms as it is, and one that only changes
its `spec_version` to 0.4 gains warnings at most.

## 1. Principles

- **Open formats only.** Tables are CSV or TSV, metadata is JSON, maps are NIfTI.
  No pickles, no `.npz` as the only copy, nothing that needs one package to read.
- **Self-describing.** Every table has a column dictionary beside it (BIDS-style
  sidecar). Nothing is to be inferred from a column name, a filename or a folder.
- **Complete.** Every test that was run has its row, significant or not, with its
  effect and uncertainty. Tables are never truncated.
- **Explicit.** The correction and what it is over, the effect measure, the
  direction a test asks, units and each table's role are written down.
- **Provenance included.** Which package, version and commit; when; on what; and
  whether the run finished.
- **Workflow-neutral.** No field belongs to a workflow tool. Anything a study wants
  attached (a pre-registration id, a finding id) goes in the opaque `references`.
- **The reporting contract is part of the format** (§6): a result is not reported
  until its magnitude, direction, extent and location are stated, and a test that
  found nothing is still a result. The checker enforces it.

## 2. The analysis folder

An **analysis** is one family of tests run together under one inference scheme —
a TBSS battery over several measures, one VBM model, one covariance-network
comparison — on **one modality, by one method** (0.2). Measures share an analysis
only when they share its design and inference *and* a reader would look for them
together: the 11 diffusion measures of one TBSS battery are one analysis; ReHo and
fALFF, each a voxelwise battery of its own, are two. An analysis on several
modalities at once (a decoder over diffusion and functional features) is
`multimodal` and says which. Each analysis is one folder:

```
<analysis>/
  analysis.json          what the analysis is (§3)
  provenance.json        what produced it (§4)
  <table>.csv|.tsv       results; each with <table>.json, its column dictionary (§5)
  ...                    maps (NIfTI) and figures, each listed in analysis.json
```

- Every file the analysis reports is **listed in `analysis.json`** with a path
  relative to the folder. Paths stay inside the folder (no absolute paths, no `..`).
- The layout inside the folder is free. `tables/`, `maps/`, `figures/` is
  recommended for new producers; existing output trees adopt the spec in place by
  adding `analysis.json`, `provenance.json` and the column dictionaries.
- A results root holds any number of analysis folders at any depth. A reader finds
  them by looking for `analysis.json` files whose `spec` is `"neurofaune.results"`.
  Analysis folders do not nest.
- **From 0.2 a folder is one run of an analysis** (§3.2): the analysis is its `id`, and
  its runs — the tests run at one time — are folders that share it. The recommended
  layout is `<root>/<id>/<run id>/`, e.g. `results/dwi/tbss/h1h/2026-10-05/`
  (`neurofaune.results.spec.run_folder`).

## 3. `analysis.json`

Fields marked * are required.

| field | content |
|---|---|
| `spec`* | `"neurofaune.results"` |
| `spec_version`* | `"0.4.0"` |
| `id`* | the analysis, stable across re-runs; from 0.2 `<modality>/<analysis_type>/<name>`, e.g. `"dwi/tbss/dose_p60"` (§3.1), shared by its runs (§3.2); a 0.1 id is unique under the results root |
| `run`* (0.2) | this folder's run of the analysis: `{id*, label, supersedes}` (§3.2) |
| `title`*, `description`* | a heading, and what the analysis asks in a sentence or two |
| `analysis_type`* | `tbss`, `vbm`, `tbm`, `voxelwise`, `roi`, `covariance_network`, `nbs`, `graph`, `connectome`, `fixel`, `decoding`, `radiomics`, `spectroscopy`, `other`; from 0.4 also `sensor` (electrode-level tests), `vertex` (whole-brain source-space tests) and `directed` (directed connectivity edges) |
| `modality`* (0.2) | `anat`, `dwi`, `func`, `msme`, `mrs`, `asl`, from 0.4 `eeg`, or `multimodal` (§3.1) |
| `domain` (0.4) | what the analysis is about, from the domain vocabulary: `spectral`, `aperiodic`, `connectivity`, `microstructure`, … (§3.1) |
| `task` (0.4) | the paradigm the data come from, by its BIDS task label: `rest`, `chirp`, `assr40` |
| `atlas` (0.4) | `{name*, version}`: the parcellation that `element` values name (§3.5) |
| `variant` (0.4.1) | `{of*, axis*, value*, label}`: this analysis is one variant of `of`, differing in `axis` (§3.7) |
| `modalities` | a `multimodal` analysis's modalities, e.g. `["dwi", "func"]`; only then |
| `measures` | the measured quantities, in display order, e.g. `["FA", "MD", "RD"]`; from 0.2 by their names in the measure vocabulary (§3.1) |
| `role`* | `confirmatory`, `exploratory`, `descriptive` or `diagnostic` |
| `design`* | `{n*, groups: {name: n}, test_kinds: [...], records: [paths to design.json], sessions, timepoints}`; `sessions` (0.4) the number of scans or recordings, `timepoints` (0.4) their labels in order (§3.5) |
| `contrasts` (0.4.1) | `[{id*, label, kind, group_a, group_b, tier, role, gate_on}]`: the contrasts the tables test, declared (§3.6) |
| `inference`* | `{method*, correction*, n_permutations, notes}`; `correction` = `{p_kind*, family*, statement*, alpha, method}` (below); from 0.4 `families` in place of `correction` (§5.2) |
| `effect`* | `{measure*, definition*, ci_level, scope, sesoi}`, or `{measure: null, reason*}` where no effect size applies; `measure` is `per_row` (0.4) where it varies by row (§5.4); `sesoi` (0.4) is the smallest effect of interest (§5.6) |
| `tables`* | `[{path*, role*, rows*, description*, headline, n_rows, threshold}]` (below); `threshold` (0.4) is what selected the rows (§3.4) |
| `maps` | `[{path*, kind*, description*, space, measure, contrast, facet, values, axes, space_derivation}]`; `space_derivation` (0.4): §3.5 |
| `figures` | `[{path*, caption*, measure, contrast, facet}]`; from 0.4 also `facets`, `kind`, `shows`, `headline`, `drawn_by` (§3.3) |
| `display` | `{plane}`: `axial`, `coronal` or `sagittal`, the plane maps are best shown in (coronal for rodents) |
| `decision` | where the analysis defines a decision rule: `{rule*, outcome*, criteria: [{name, description, passed}], calibration, rests_on}`; `outcome` is `holds`, `does_not_hold` or `not_assessed`; `calibration` and `rests_on` (0.4): §3.4 |
| `retired` | `{reason*, superseded_by}` — kept on disk, not to be read as current |
| `caveats` | `[sentence, …]` that a reader must see beside the results |
| `references` | `[{label, value}]`; the labels `registration` (a pre-registered hypothesis this analysis tests), `finding` (a recorded finding it reports) and `doi` have that meaning; any other label is opaque to the spec |

**`inference.correction`.** `p_kind` is `fwe`, `fdr`, `perm` (permutation p of a
single test statistic), `uncorrected` or `none`. `family` says what the correction
is over ("voxels in the skeleton mask, per contrast"; "the 11 measures"). `statement`
is the sentence a methods section would carry ("TFCE, FWE p < 0.05 by 5,000
permutations, per contrast over the skeleton"). A table column may carry its own
`PKind` (§5) where it differs — a cluster table's uncorrected minimum p, say. From 0.4
`method` names the procedure (`BH`, `BY`, `holm`, `hochberg`, `bonferroni`, `tfce`,
`cluster`, `maxT`, `nbs`, `none`, `other`), because `p_kind` says what is controlled but
not how: Holm and BH are both "a correction", and only one of them is FDR.

**`tables[].role`** — what one row is, so no reader guesses from a filename:

| role | one row is | contract (§6) |
|---|---|---|
| `tests` | one test that was run (a contrast on a measure) | checked |
| `clusters` | one spatial cluster of one test | checked |
| `elements` | one ROI / edge / component of one test | checked |
| `descriptives` | a group summary (means, SDs, n) | not checked |
| `recordings` (0.4.1) | one recording (a scan, an EEG session) with its quality checks (§5.7) | its own rules (§5.7) |
| `other` | anything else, described in `rows` | not checked |

`rows` says what one row is in words; `headline: true` marks the table a reader
should show first (at most one per analysis).

**`maps[].kind`**: `stat`, `p_corrected`, `p_uncorrected`, `effect`, `mask`,
`background`, `input`, `other`. A `background` map is the **intensity template of
the atlas the maps are in** -- the atlas the study registered to -- on the same grid as
the maps, which readers draw on voxel for voxel. It is not a study-derived image
(a mean FA, a group template): every analysis in one space is shown on the same
reference. A reader draws on the `mask` when there is no background.
A map's `axes` states the anatomical direction each voxel axis runs toward -- three
letters, one from each of R/L, A/P, S/I (S dorsal, I ventral), e.g. `LIA`. A reader
orients by it and not by the image header: rodent headers often follow the scanner
rather than the animal. Without `axes` a reader uses the header and says so.
A `p_corrected` / `p_uncorrected` map states what its voxels hold: `values` is `p`
or `one_minus_p` (randomise's convention). A reader does not threshold a p map that
does not say. A map that belongs to one test names its `measure`,
`contrast` and (where the tests table has one) `facet`, matching that test's row. `space` names the template (e.g. `SIGMA`,
`MNI152NLin2009cAsym`).

### 3.1 Identity and vocabulary (0.2)

What a reader groups analyses by — a gallery's sections by modality, a manuscript's
tables by method — is written by the producer, in words every producer uses:

- **`modality`** is required and is one of `anat` (structural T1w/T2w: volumes,
  morphometry, VBM / TBM), `dwi`, `func`, `msme` (multi-echo relaxometry: T2, MWF),
  `mrs`, `asl`, `eeg` (0.4; sensor or source space), or `multimodal` with `modalities`
  listing at least two of the others.
- **`id`** is `<modality>/<analysis_type>/<name>`: the folder's own modality and
  analysis type, then a name whose parts are lowercase letters, digits, `_`, `.` or
  `-` (`neurofaune.results.spec.analysis_id(modality, type, name...)` builds one). A
  reader can sort by the id alone; the id never contradicts the fields.
- **`measures`** are written by their canonical names in the measure vocabulary,
  `src/neurobox/vocab/measures.json` (canonical name → modality, or `modalities` for a
  measure several use, such as graph metrics; description; aliases: `FICVF` not `NDI`,
  `CSWF` not `CSFF`, `Cr+PCr` not `tCr`, and from 0.4 `aperiodic_exponent` not
  `exponent`, `transfer_entropy` not `te`). A measure the vocabulary does not have is
  allowed and warned about; it is added to the vocabulary, in neurobox-dev, with a
  CHANGELOG line, rather than spelled anew by each producer.
- **`domain`** (0.4, optional) is what the analysis is about — the signal or tissue
  property — from the domain vocabulary, `src/neurobox/vocab/domains.json`, each domain
  tagged with the modalities that use it: `spectral`, `aperiodic`, `evoked`,
  `connectivity`, `cross_frequency`, `directed`, `decoding`, `localization` for EEG;
  `microstructure`, `morphometry`, `relaxometry`, `function`, `metabolites`, `perfusion`
  for MRI. A gallery groups by it. An EEG example: `id` `eeg/roi/aperiodic_rest`,
  `domain` `aperiodic`, `task` `rest`.
- **`task`** (0.4, optional) is the paradigm, by its BIDS task label (letters and digits).
- **Tables name only listed measures**: a contract table's `measure` column holds
  names from `analysis.json`'s `measures`.

The checker enforces these for folders that declare 0.2 (errors: a missing or unknown
modality, an id that does not follow the pattern or contradicts the fields, a known
measure under another spelling, a table measure not listed; warnings: a measure not in
the vocabulary, a measure of another modality than the analysis's), and from 0.4 the
`domain` and `task` (an error: a task that is not a BIDS label; warnings: a domain not in
the vocabulary, or of another modality). A 0.1 folder is read by 0.1's rules.

### 3.2 Runs: tests of one analysis run at different times (0.2)

An analysis is rarely run once. A battery is registered and run; a contrast is added
after its results are read; one measure is re-run with a corrected mask. Each of those
is a **run**: the tests run together at one time, with their own provenance, role,
correction and references — a registered run and a later exploratory one keep their
own labels, side by side. Each run is a folder of its own, written once and not edited
afterwards; its `analysis.json` carries

```json
"run": {"id": "2026-10-08", "label": "covariate-adjusted follow-up", "supersedes": ["2026-10-05"]}
```

- `id`* — unique among the analysis's runs; lowercase letters, digits, `_`, `.`, `-`
  (a date, or a date and time, reads well). The writer fills in the current UTC time
  when a producer gives none.
- `label` — the run in a few words, for a reader's list of runs.
- `supersedes` — earlier runs of the same analysis whose tests this run repeats and
  replaces. Supersession is per test: an earlier run's test (measure × contrast × facet)
  is superseded when a run that lists it holds the same test; the earlier run's other
  tests stay current. Superseded runs stay on disk.

**The rules** (checked across a results root; the writer checks a new run against its
sibling runs in the same parent folder): runs of one `id` share `modality` and
`analysis_type`; run ids are unique within an analysis; `supersedes` names runs of the
same analysis, never the run itself, and two runs do not supersede each other; **a test
held by two runs, neither superseding the other, is an error** — the same test is never
reported twice as current. A run that supersedes another but repeats none of its tests
is warned about.

**Corrections stay with their runs.** Each run's `inference.correction` covers that
run's tests; a reader shows every test with its own run's correction and never pools p
values across runs. To correct a set of tests jointly after adding to it, run them all
again as one new run that supersedes the old ones.

Fields that describe the analysis rather than the run (`title`, `description`,
`measures`) may differ between runs as the analysis grows; a reader takes them from the
latest current run and lists the union of the measures.

### 3.3 Figures (0.4)

A gallery lays figures out and filters them by fields, never by file names, so a figure
may say:

| field | content |
|---|---|
| `facets` | `{name: value}` for the test it belongs to, by the tables' facet names (§5.2), e.g. `{"band": "gamma", "tier": "region"}` |
| `kind` | `brain` (a map or parcel rendering), `matrix` (connectivity), `spectrum`, `distribution` (box or violin), `trajectory`, `summary` (a heatmap over tests), `diagnostic`, `other` |
| `shows` | the table it was drawn from, one of `tables[].path` |
| `headline` | true on the one figure to show first |
| `drawn_by` | `analysis` (written with the results) or `gallery` (drawn by the tool when it built the gallery, so it can be redrawn) |

A figure that names a test (`measure`, `contrast`, `facet` or `facets`) matches a row of
the tests table; one that does not is warned about. From 0.4.2 a figure that names a
`contrast` (and `measure`) but no facet shows that contrast across its facets (a heatmap
over bands, say): it matches when the tests table tests that contrast (on that measure).

### 3.4 Decisions and their reliability (0.4)

A decision rule that also holds on data with no effect does not separate an effect from
none, and a reader of `outcome` alone cannot know. So a decision may state:

- **`calibration`** `{null_rate*, method*, datasets}`: the share of datasets with no
  effect (label reshuffles, simulations: `method`, `datasets` of them) in which the rule
  also holds. cuprizone's H008 holds in 66% of reshuffled datasets: `{"null_rate": 0.66,
  "method": "label reshuffles", "datasets": 200}`. A reader shows it beside `outcome`.
- **`rests_on`**: the tables (by `path`) whose rows the rule counts. A rule that counts
  clusters at an uncorrected threshold rests on a cluster table at that threshold, which
  the analysis then lists, with the table's own **`threshold`** `{p_kind*, statement*,
  alpha, method}` saying what selected its rows (`"TFCE p < 0.05, uncorrected"`) beside
  the corrected one.

### 3.5 Spaces, atlases and designs (0.4)

- A map in a space **derived from a template** — flipped, transposed, resampled — keeps
  the name it is known by in `space` and says how it relates in **`space_derivation`**
  `{from*, how*}`: `{"from": "SIGMA", "how": "the study-space SIGMA: a transpose and two
  flips of the distributed template"}`. A reader who overlays on the named template
  itself sees that it must not.
- **`atlas`** `{name*, version}` names the parcellation that an `elements` table's
  `element` values come from, as `space` does for maps. An analysis with an `elements`
  table and a figure of `kind` `brain` states it.
- **`design.sessions`** is the number of scans or recordings when it is not `n` (longitudinal
  designs), and **`design.timepoints`** their labels in order (`["p60", "p90", "p120"]`).

### 3.6 Declared contrasts (0.4.1)

A table's `contrast` column names each test's contrast by an identifier. **`contrasts`**
says what each one is, once for the analysis, so a reader need not take it from a column or
from the study's own config:

```json
"contrasts": [
  {"id": "disease_effect", "label": "Disease effect (KO vs WT)", "kind": "contrast",
   "group_a": "KO_VEH", "group_b": "WT_VEH", "tier": "phenotype"},
  {"id": "hd_icv_rescue", "label": "HD-ICV rescue (vs KO veh)", "kind": "contrast",
   "group_a": "KO_HD_ICV", "group_b": "KO_VEH", "tier": "rescue", "gate_on": ["disease_effect"]},
  {"id": "hd_icv_normalization", "label": "HD-ICV normalization to WT", "kind": "equivalence",
   "group_a": "KO_HD_ICV", "group_b": "WT_VEH", "tier": "normalization", "role": "confirmatory"}
]
```

- **`id`*** is the value in the tables' `contrast` column. Where `contrasts` is given, every
  `contrast` value in a `tests`, `clusters` or `elements` table is one of its ids.
- **`kind`** is `omnibus`, `contrast`, `equivalence`, `regression` or `other`; **`group_a`**
  and **`group_b`** are the positively and negatively weighted groups of a two-group contrast,
  as `design.groups` names them.
- **`tier`** groups contrasts as the study does (phenotype, rescue, normalization); a reader
  shows tiers in the order they first appear.
- **`role`** is the contrast's own role where it differs from the analysis's: an exploratory
  analysis may test some contrasts it declared in advance, which are `confirmatory`.
- **`gate_on`** names contrasts (of this list) that must hold before this one is read.

### 3.7 Variants of one analysis (0.4.1)

The same analysis is often run several ways that a reader compares side by side: on each
source reconstruction of an EEG study, through two pipelines, in two templates. Each way is
its own analysis, with its own id and runs; **`variant`** ties them together:

```json
"id": "eeg/roi/psd/cartesian_mc",
"variant": {"of": "eeg/roi/psd", "axis": "reconstruction", "value": "cartesian_mc", "label": "MC Cartesian"}
```

- Analyses with the same **`of`** and **`axis`** are variants of one analysis; **`value`**
  tells them apart and **`label`** names it for display. A study's gallery settings give the
  order of an axis's values.
- The id is `of` followed by its parts, the variant's `value` among them, so the two cannot
  drift apart; and one variant (`of`, `axis`, `value`) is one analysis id across the results.

## 4. `provenance.json`

| field | content |
|---|---|
| `spec`*, `spec_version`* | as in `analysis.json` |
| `generated_by`* | BIDS `GeneratedBy`: `[{Name*, Version*, CommitID, RequestedRevision, Description}]`, the producing package first, then the tools it ran (FSL, ANTs) |
| `run`* | `{status*, start*, end, id}`; `status` is `completed`, `partial`, `failed` or `running` |
| `inputs` | `[{path*, role, sha256}]` |
| `subjects` | `{n, groups: {name: n}}` |
| `settings` | the parameters the analysis ran with |
| `environment` | `{python, platform}` |

A reader shows a run whose status is not `completed` as such, never silently.

## 5. Tables and column dictionaries

- **CSV or TSV**, chosen by the extension (`.csv` comma, `.tsv` tab); UTF-8; one
  header row; one row per what `rows` says. An empty cell is a missing value.
  Booleans are `true` / `false` (`True` / `False` accepted). Lists inside a cell
  are separated by `"; "`.
- **Column dictionary**: `<table stem>.json` beside the table, BIDS-style — one key
  per column, every column present, no entries for absent columns:

```json
{
  "whole_d": {
    "Description": "Cohen's d of the contrast on each subject's mean over the mask (unselected)",
    "Standard": "effect_size",
    "EffectMeasure": "d",
    "EffectScope": "whole mask"
  },
  "min_p_fwe": {
    "Description": "smallest FWE-corrected voxel p in the map",
    "Standard": "p_value",
    "PKind": "fwe",
    "PScope": "minimum over the mask"
  }
}
```

  `Description` is required; `Units` and `Levels` (`{value: meaning}`) are BIDS's;
  `Standard` maps the column to the vocabulary below, so a reader finds "the
  effect size" without knowing the producer's column names. A standard term is
  claimed by at most one column per table -- except `subgroup_effect` and `subgroup_n`,
  claimed once per subgroup, and from 0.4 `facet`, claimed once per named facet (§5.2).

**Standard terms** (qualifiers in brackets; * = required with the term):

| term | meaning |
|---|---|
| `measure` | the measured quantity of the row (FA, ReHo, …) |
| `contrast` | test identifier within the analysis; `measure` + `contrast` (+ `facet`, or from 0.4 every named facet) identify a test |
| `contrast_label` | the contrast in words |
| `facet` | any further split of the tests (window, timepoint, family); from 0.4 [`FacetName`] when a table has several (§5.2) |
| `element` | per-element rows: the cluster id, ROI name, edge `"A -- B"`, component id; from 0.4.2 [`ElementName`: what one element is, in the singular: `ROI`, `region`, `electrode`, `edge`, `cluster`, `component`, `vertex`] |
| `test_kind` | `two_group`, `one_sample`, `regression`, `interaction`, `custom`; from 0.4 `equivalence` (§5.3) |
| `tested_direction` | what a positive statistic means, in words: `"cuprizone > control"`, `"mean > 0"` |
| `observed_direction` | the direction the effect actually went, in the same words |
| `group_a`, `group_b` | two-group tests: `group_a` is higher when the statistic is positive |
| `n`, `n_a`, `n_b`, `df` | sample sizes and error degrees of freedom |
| `effect_size` | [`EffectMeasure`*: `d`, `g`, `r`, `beta`, `eta2`, …, or from 0.4 `per_row` (§5.4); `EffectScope`] |
| `effect_ci_low`, `effect_ci_high` | [`CILevel`] bounds on `effect_size` |
| `effect_selected` | true where the effect was computed on elements chosen for significance (inflated) |
| `estimate` | the contrast in raw units [`Units`] |
| `mean_a`, `mean_b`, `mean` | group means / the one-sample mean [`Units`] |
| `stat` | [`StatName`*: `t`, `F`, `z`, …; `StatScope`: `peak`, `element`] |
| `p_value` | [`PKind`*, from 0.4 also `per_family` (§5.2); `PScope`] |
| `significant` | [`Alpha`] |
| `n_significant` | elements (voxels, edges) significant under the correction [`Units`, `PKind`, `Alpha`] |
| `frac_significant` | the same as a fraction of the mask / network |
| `n_voxels`, `volume_mm3` | a cluster's extent |
| `peak_xyz_mm` | [`Space`*] peak coordinate, `"x y z"` |
| `peak_region` | atlas region at the peak |
| `regions` | every region covered, `"name:count; name:count"` |
| `crosses_midline` | the cluster has voxels in both hemispheres |
| `subgroup_effect` | [`EffectMeasure`*, `Subgroup`*] the test's effect within one subgroup (a cohort, a batch, a site); one column per subgroup, each naming it |
| `subgroup_n` | [`Subgroup`*] that subgroup's size |
| `se` (0.3) | standard error of `estimate` from the fitted model (covariates included), in its units |
| `mde` (0.3) | [`Power`*, `Alpha`*] minimum detectable effect, in `estimate`'s units (§5.1) |
| `mde_percent` (0.3) | `mde` as a percent of the reference group's mean (§5.1); from 0.4 [`PercentOf`] says of what |
| `mde_note` (0.3) | empty when `mde` is given; otherwise why not, starting `not computed: ` |
| `correction_family` (0.4) | the row's correction family, one of `inference.families[].id` (§5.2) |
| `p_uncorrected` (0.4) | the raw p, beside the corrected `p_value` |
| `effect_measure` (0.4) | the row's effect measure, where `effect_size` says `per_row` (§5.4) |
| `margin` (0.4) | [`Units`*] the equivalence bound of the row (§5.3) |
| `equivalent` (0.4) | true where an equivalence test concludes equivalence |
| `posterior_median` (0.4) | the posterior median of the effect [`Units`] (§5.5) |
| `hdi_low`, `hdi_high` (0.4) | [`CILevel`*] the highest-density interval |
| `p_direction` (0.4) | the posterior probability of the effect's direction |
| `p_rope` (0.4) | [`Rope`*: the region of practical equivalence] the posterior share inside it |
| `bf10` (0.4) | [`Scale`*: `log10` or `linear`] the Bayes factor for an effect over none |
| `sesoi` (0.4) | [`Basis`*] the row's smallest effect of interest, in `estimate`'s units (§5.6) |
| `reading` (0.4) | [`Levels`*] what the row shows, one of its `Levels` (§5.6) |
| `subject` (0.4.1) | the subject a recording is of (§5.7) |
| `group` (0.4.1) | the subject's group, as `design.groups` names it (§5.7) |
| `session` (0.4.1) | the session or timepoint of a recording (§5.7) |
| `qc_flag` (0.4.1) | [`Rule`*: the rule in words] true where the recording is flagged by its quality checks (§5.7) |

Columns with no standard term are welcome; their dictionary entry describes them.

### 5.1 The minimum detectable effect (0.3)

A test that found nothing is a result only together with what it could have found, and
a finding's size means more beside the size its design could see. So a tests row gives
its **minimum detectable effect**: the difference the design detects with power `Power`
at two-sided `Alpha`,

    mde = (t(1 - Alpha/2, df) + t(Power, df)) * se

with `se` the standard error of the estimate from the fitted model (covariates
included) and `df` the test's degrees of freedom; with no finite `df`, the normal
quantiles. It is a positive number in the estimate's units. The `mde` column states
`Power` and `Alpha` in its dictionary entry, so the number never travels without them.
neurofaune, source-analytics and neurovrai write it at **power 0.80 and alpha 0.05,
nominal**: no multiple-comparison correction (the decision behind DUET's OPEN.md #151,
which reads every finding against it). Reference values every producer reproduces:
se 1, df 10 → 3.107197; se 1, df 26 → 2.911195; se 2.09, df 24 → 6.104376; se 1, df ∞
→ 2.801585; se 0.5, df 4 → 1.858705.

`mde_percent` is `100 * mde / |reference mean|`, the reference being the reference
group's mean (the control, the baseline) on the estimate's scale. It is empty where
there is no reference group (a regression slope, a one-sample mean) or the mean is near
zero; the column's description says which group is the reference. From 0.4 the column's
**`PercentOf`** says what the percent is of, in words, because the estimate's scale is not
always the measure's: in a test of a difference in change, the reference mean is the
controls' mean *change*, and a percent of it (cuprizone: a median 65%) reads very
differently from a percent of the measure's mean. `PercentOf: "the controls' mean change
from p60 to p90"` makes that plain; a 0.4 `mde_percent` without it is warned about. MDE
terms may be given on `elements` rows as well as `tests` rows.

**Never blank without a reason.** A row whose `mde` is empty says why in `mde_note`,
starting `not computed: ` — `not computed: voxelwise map, corrected by randomise`,
`not computed: cluster selected by the test`, `not computed: permutation test with no
standard error`. A voxelwise map has no closed-form detectable effect (its permutation
correction depends on the effect's spatial extent); a cluster's effect is measured on
the voxels the test chose. A row that gives an `mde` leaves the note empty.

### 5.2 Named facets and correction families (0.4)

**Facets.** A table whose tests split several ways — EEG's band and spatial tier, say —
gives each split a `facet` column naming itself with **`FacetName`**: `band`, `tier`,
`window`, `freq_pair`, `metric`, `timepoint`. A test is then `measure` + `contrast` + every
facet; facet names are unique within a table. A single `facet` column needs no name, and
keeps its 0.3 meaning.

**Correction families.** One analysis — one EEG module on one paradigm — often corrects
its tests in several families (per band, per hypothesis). In place of the one
`inference.correction`, it then gives

```json
"families": [
  {"id": "alpha_bh", "p_kind": "fdr", "method": "BH", "scope": "band", "members": "roi[26]",
   "members_hash": "…", "statement": "BH-FDR q < 0.05 over the 26 ROIs within the band"},
  {"id": "posthoc", "p_kind": "fwe", "method": "holm", "statement": "Holm over ROIs"}
]
```

and each row names its family in a **`correction_family`** column (required when there are
several). The `p_value` column's `PKind` is the families' shared kind, or `per_family`
where they differ. Corrections are still never pooled: each test is corrected within its
own family. An analysis gives `correction` or `families`, not both. A table may carry the raw
p beside the corrected one as **`p_uncorrected`**.

### 5.3 Equivalence tests (0.4)

A row whose `test_kind` is `equivalence` (two one-sided tests) states its bound in a
**`margin`** column (or a `sesoi` column, §5.6), with its `Units`, and may say in
**`equivalent`** whether the test concludes equivalence. A table of equivalence tests alone
may give `equivalent` and `margin` in place of `p_value`.

### 5.4 Effect measures that vary by row (0.4)

A table that mixes omnibus, contrast and regression rows gives `effect_size` the
`EffectMeasure` `per_row` and names each row's measure in an **`effect_measure`** column
(`g`, `omega2_partial`, `std_beta`); `effect.measure` in `analysis.json` may say `per_row`
too. A reader filters by measure before comparing effects.

### 5.5 Bayesian results (0.4)

An analysis whose `inference.method` is `bayesian` reports, on every `tests` and
`elements` row, **`posterior_median`** with **`hdi_low`** and **`hdi_high`** (its `CILevel`)
as the magnitude and **`p_direction`** as the evidence, in place of `effect_size` with its
interval and `p_value`; **`p_rope`** (with its `Rope`) and **`bf10`** (with its `Scale`) are
optional. The checker requires the four on every row, and the median within its interval.
Its `correction` is `{"p_kind": "none", …}`, saying so in its statement.

### 5.6 The smallest effect of interest (0.4)

The MDE (§5.1) is what a design could detect; the **smallest effect of interest** is the
effect agreed, before reading the results, to count as real — cuprizone's within-rat scatter
across repeat scans, an equivalence margin. An analysis gives one value in
`effect.sesoi` `{value*, basis*, units}`, or per row in a **`sesoi`** column with its
`Basis`. A study's readings against it ("an effect", "below the scatter", "no effect as large
as the scatter", "undetermined") go in a **`reading`** column, whose `Levels` define every
value it uses.

### 5.7 Recordings and their quality checks (0.4.1)

A table of role **`recordings`** has one row per recording: a scan, an EEG session, a
localization of one session. It names the subject in a column marked **`subject`** (required,
on every row), and where it has them the subject's group (**`group`**, values from
`design.groups`) and the session (**`session`**). A column marked **`qc_flag`** is true where
the recording's quality checks flag it, and states the rule that flags it in words (`Rule`,
e.g. "|z| > 2 against the study on any QCMetric column"); the producer applies the rule, and a
reader shows its result. The columns the checks look at say so with **`QCMetric: true`**, so
a reader can show them as the recording's metrics. Other columns, such as a recording's report
or figures, are described like any others.

## 6. The reporting contract

`neurofaune results check` enforces this on tables whose role is `tests`,
`clusters` or `elements`. A missing item is an error.

**`tests`** — one row per test that was run, significant or not:
- identity: `contrast` (and `measure` where the analysis has several);
- direction: `tested_direction`, or `test_kind` with `group_a` / `group_b` for
  two-group tests;
- magnitude: `effect_size` with its `EffectMeasure` and `effect_ci_low` /
  `effect_ci_high` — or, where no effect applies, `analysis.json`
  `effect = {measure: null, reason}`;
- sample: `n`, or `n_a` and `n_b`;
- significance: `p_value` with its `PKind`; the family it is corrected over is in
  `analysis.json` (from 0.4, with several families, each row names its own: §5.2);
- extent, for voxelwise tests: `n_significant` or `frac_significant`;
- what the design could detect (0.3): `mde` with its `Power` and `Alpha`, or an
  `mde_note` on each row saying why not (§5.1). A tests table with neither is warned
  about, not refused;
- from 0.4: an `equivalence` row gives its `margin` (§5.3); a `per_row` effect names each
  row's measure (§5.4); a Bayesian analysis gives `posterior_median`, `hdi_low`,
  `hdi_high` and `p_direction` on every row in place of the effect, its interval and
  `p_value` (§5.5).

**`clusters`** — every cluster under a stated definition:
- which test: `contrast` (and `measure`), matching a `tests` row;
- extent: `n_voxels` or `volume_mm3`;
- location: `peak_xyz_mm` with its `Space`, and `peak_region`;
- magnitude: `stat` with its `StatName` (the peak), or `effect_size` — and
  `effect_selected` wherever an effect is given, since cluster effects are selected;
- significance: `p_value` with its `PKind`.

**`elements`** — one row per ROI / edge / component tested:
- which test: `contrast` (and `measure`); the element: `element`;
- magnitude: `effect_size` with its `EffectMeasure` (signed), or `stat` with `StatName`;
- significance: `p_value` with its `PKind`.

The checker cannot see a test that was run and left out. A producer that knows how
many tests it ran states `"n_rows"` on the table's entry in `analysis.json`, and
the checker counts.

## 7. Conformance

```
neurofaune results check <analysis folder or results root> [--json]
```

checks every analysis folder it finds: the JSON files against the schemas, every
listed file present and inside the folder, every table against its dictionary, the
standard terms and their qualifiers, the contract (§6), for folders that declare
0.2 or later identity and vocabulary (§3.1) and, across the folders it finds, the runs of
each analysis against each other (§3.2), and for folders that declare 0.3 the minimum
detectable effect (§5.1): an `mde` is positive, with `Power` and `Alpha` between 0 and 1;
a row without one carries an `mde_note` starting `not computed: `; an `mde_percent` is
positive and only beside an `mde`; an `se` is a number >= 0. A folder that declares an
earlier version may not use the 0.3 terms. For folders that declare 0.4 it also checks the 0.4
additions where they are used: each `correction_family` names a declared family, and each
row names one when there are several; a `p_value`'s `PKind` agrees with its rows' families;
several facets are each named, once; a figure's `shows` is one of the tables and its
`facets` are names the tables use; one headline figure; an `atlas` beside a brain figure of
an `elements` table; the equivalence, per-row and Bayesian rules above; `margin` and `sesoi`
above 0, a linear `bf10` above 0, a `reading` within its `Levels`, a `calibration.null_rate`
within [0, 1], and `rests_on` naming listed tables. A folder that declares an earlier
version may not use any 0.4 field, term, qualifier or value. Each folder is checked by the
rules of the version it declares. Exit status 0 when every
folder conforms. The schemas in `src/neurobox/schemas/` are plain JSON Schema
(draft 2020-12) and work with any validator; the checker itself needs only the
standard library, so it can run where no producer's dependencies are installed.

## 8. Versioning

`spec_version` is semver. A reader accepts any version with the major version it
was written for — while the major is 0, every minor up to its own (a 0.4 reader reads
0.1 to 0.4) — and reports, never guesses, a field it does not know. Producers write
the version they were built against. Changes are listed in neurobox-dev's
`CHANGELOG.md`. A patch version (0.4.1) adds only optional fields; the checker reads a
folder's version by its major and minor, so it checks 0.4.1's fields wherever a 0.4 folder
uses them, and refuses them in older folders.
