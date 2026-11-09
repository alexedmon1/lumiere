# Results specification changelog

The specification's identifier is `neurofaune.results`; it moved from neurofaune to
neurobox-dev (a working name) on 2026-11-03.

## 0.4.2 — 2026-11-09

- **Gallery summary:** balanced accuracy (decoding) is shown without a direction arrow, like AUC.
- **Vocabulary:** `net_transfer_entropy` (alias `net_te`), for source-analytics' `roi_directed`.
- **`ElementName`** on an `element` column says what one element is, in the singular (`ROI`,
  `region`, `electrode`, `edge`, `cluster`), as `FacetName` names a facet. Optional; a reader
  that needs a name and finds none says "element".

## Gallery shell — 2026-11-09: the significance summary (Esprit's results plan, 5b.2)

- **Each analysis's Summary tab** now says what was found, not only which contrasts were
  tested: per declared contrast, each test (`measure` and its facets) with a significant
  result, at every level the analysis reports: the overall row (a contract table with no
  `element` column), then each element table, named by its `ElementName` (until then by its
  file). Effect size and direction lead (▲/▼: the first-listed group is higher), the
  corrected p follows; up to 8 elements are named per level and the rest counted. Each
  contrast shows its 5 strongest tests (largest effect at any level) and folds the rest
  under "+N more tests".
- **The lead line** gives the strongest overall effect of a directed contrast (not an
  omnibus, not an equivalence test, and not a single element's peak) and how many
  comparisons have any significant result, with the count at each level.
- **Equivalence contrasts** say in how many tests equivalence was concluded (`equivalent`),
  then list where the difference is still significant.
- **Read only from declared fields:** `contrast`, `measure`, `facet`, `element`, `effect_size`
  (with `EffectMeasure` or `effect_measure`), `p_value` (`PKind`), `significant`, else
  `p_value` below the family's or correction's `alpha` (0.05 when none is stated). Computed
  at build time from whole tables (`gallery/digest.py`), not the 500 rows the page embeds;
  an analysis whose summary cannot be made is still shown, with a warning.

## Gallery shell — 2026-11-04 (no change to the specification)

- **`#/id/<id>`** opens an analysis by its `analysis.json` id, whichever run is current: the
  link a DUET finding uses (DUET #165).
- **Findings that cite it:** the build reads `<study>/duet/status.json`, and each analysis
  lists the findings whose `analysis` names it, each linking to the record page.
- **Older code:** the build compares each analysis's producer (`generated_by`, first entry)
  with the version `<study>/study.toml` pins; an analysis made with an older version is
  flagged on its page and listed on the overview. The manifest's `code` counts each state
  (current, older, newer, uncommitted, unknown) for readers such as Esprit.
- **Dark theme:** the description and provenance boxes and links in text used colours the
  themes did not define, and showed light on dark; they follow the theme now.

## 0.4.1 — 2026-11-04

What source-lightbox's study galleries need that the specification did not say (Esprit's
results plan, step 5b.3), so the shared gallery reads it instead of guessing. All optional:
a 0.4.0 folder conforms unchanged.

- **`contrasts`** in `analysis.json` (§3.6): each contrast the tables test, with its label,
  kind, groups, `tier` (the study's grouping: phenotype, rescue, normalization), its own
  `role` where it differs from the analysis's, and `gate_on`. Where given, every `contrast`
  value in a contract table is one of its ids.
- **`variant`** (§3.7): `{of, axis, value, label}` ties one analysis across reconstructions,
  pipelines or templates; the id is `of` with `value` among its later parts, and one variant
  is one id across the results.
- **`recordings`** table role (§5.7), with the standard terms **`subject`** (required),
  **`group`**, **`session`** and **`qc_flag`** (`Rule`*), and the qualifier **`QCMetric`**
  for the columns quality checks look at.

## Vocabulary — 2026-11-04 (spec 0.4.0)

Two EEG measures that source-analytics' `roi_psd`, `electrode_psd` and `roi_cross_freq` test:
`delta_referenced_power` (alias `delta_ref`), a band's power density referenced to a
low-frequency anchor window in dB, and `ppc_z`, n:m phase-phase coupling z-scored against
surrogates, which is tested beside the raw `ppc` and so needs its own name.

## Gallery shell — 2026-11-03 (spec still 0.4.0)

`neurobox.gallery.build(study, settings, out=None)` and `python -m neurobox gallery <study>`:
one static gallery per study from its conforming analysis folders, the shell every tool's
`gallery build` calls (Esprit's results plan, step 5). Settings are cuprizone's planned
`gallery.yaml` format (`name`, `paths.results` / `paths.gallery`, `links`, `sections` with
`group`, `match` and `note`) plus `groups` / `group_order` for display labels; a tool parses
the YAML and passes a dict, so the package stays standard-library only. Each analysis shows
its description, caveats, decision (with its calibration), design, inference, effect, run,
producer, figures and tables (column descriptions on hover, sortable, filterable, full CSV
linked); the newest run of each id is shown and earlier runs listed; folders that do not
conform are listed, not shown. A table column whose values are relative paths to files beside
the analysis (a recording's report) becomes links. Text from results is set as text, never
HTML. Colours and layout follow source-lightbox's.

## 0.4.0 — 2026-11-03 (draft)

One schema for MRI and EEG, plus what cuprizone's first real run of the spec (the TBSS
read-out, 330 tests; Esprit's results plan, step 2) showed was missing. **Everything is
additive and optional:** a 0.3 folder conforms unchanged; a folder that only changes its
`spec_version` to 0.4 gains warnings at most (cuprizone's two folders: one warning each,
the `PercentOf` below). A folder declaring 0.3 or earlier may not use anything below.

- **EEG identity** (§3.1): modality `eeg`; analysis types `sensor`, `vertex`, `directed`;
  optional `domain` (new vocabulary, `vocab/domains.json`, each domain tagged by
  modality), `task` (a BIDS task label) and `atlas` (`{name, version}` of the parcellation
  `element` values name). EEG measures in the measure vocabulary (`band_power`,
  `aperiodic_exponent`, `dwpli`, `transfer_entropy`, `pac_mi`, `itc`, …, with
  source-analytics' short names as aliases), and graph metrics shared by several
  modalities (a vocabulary entry may give `modalities`).
- **Named facets** (§5.2): several `facet` columns, each with a `FacetName`; a test is
  measure + contrast + every facet.
- **Correction families** (§5.2): `inference.families` in place of one `correction`; a
  `correction_family` column; `PKind: "per_family"`; `correction.method` names the
  procedure (`BH`, `holm`, `tfce`, …); `p_uncorrected` beside the corrected p.
- **Equivalence tests** (§5.3): `test_kind` `equivalence`, terms `margin` and `equivalent`.
- **Per-row effect measures** (§5.4): `EffectMeasure: "per_row"` with `effect_measure`.
- **Bayesian results** (§5.5): `posterior_median`, `hdi_low`/`hdi_high`, `p_direction`,
  `p_rope`, `bf10`; a `bayesian` analysis gives the first four on every row in place of
  the effect, its interval and p.
- **From cuprizone's run:** `PercentOf` on `mde_percent` (warned when missing in 0.4),
  since a percent of the controls' mean change is not a percent of the measure (§5.1);
  the smallest effect of interest, `effect.sesoi` or a `sesoi` column, and a `reading`
  column against it (§5.6); `decision.calibration` (how often the rule holds with no
  effect) and `decision.rests_on`, with a table's `threshold` so the uncorrected clusters a
  rule counts can be listed (§3.4); a map's `space_derivation` for a space derived from a
  template, and `design.sessions` and `design.timepoints` (§3.5).
- **Figures** (§3.3): `facets`, `kind`, `shows`, `headline`, `drawn_by`.
- The schemas' `$id`s point at neurobox-dev. `inference.correction` is no longer
  required by the schema; the checker requires it for folders before 0.4, and one of
  `correction` or `families` from 0.4.

## Moved to neurobox-dev — 2026-11-03 (spec still 0.3.0)

No change to the specification, its schemas, checker or writer: the package
`neurofaune.results` was copied byte-for-byte as `neurobox`, so tools other than
neurofaune can use it without neurofaune's imaging stack. Only wording changed: the
checker's command (`python -m neurobox check`), the vocabulary path in one message, and
the documents, which now name source-lightbox and the planned gallery shell as readers
instead of "neuro-lightbox", and make 1.0.0 depend on one MRI study (cuprizone) and one
EEG study (FORGE) building galleries. neurofaune re-exports the package as
`neurofaune.results`, as an optional extra (`neurofaune[results]`), and every `analysis.json`
keeps `"spec": "neurofaune.results"`.

## 0.1.0 — 2026-10-06 (draft)

First version: analysis folders (`analysis.json`, `provenance.json`, tables with
BIDS-style column dictionaries), the standard column vocabulary, the reporting
contract for `tests` / `clusters` / `elements` tables, JSON Schemas and a
standard-library checker. Written first by neurofaune's TBSS and VBM /
voxelwise-fMRI read-outs (`neurofaune.analysis.stats.readout_results`).

Amended while still a draft (2026-10-06; every addition optional, nothing removed):
a `background` map kind; p maps' `values` (p / one_minus_p); maps' `facet` and `axes`
(declared orientation) and the analysis's `display.plane`; the per-subgroup terms
`subgroup_effect` / `subgroup_n` with the `Subgroup` qualifier; a tests row giving an
effect must give both interval bounds.


## 0.2.0 — 2026-10-06 (draft)

Identity and vocabulary (RESULTS_SPEC.md §3.1), so a reader can group analyses by what
they are without matching on names:

- an analysis is one modality and one method; `modality` is required and one of
  `anat`, `dwi`, `func`, `msme`, `mrs`, `asl`, `multimodal` (with `modalities`);
- `id` is `<modality>/<analysis_type>/<name>` (`spec.analysis_id` builds one);
- `analysis_type` gains `decoding`, `radiomics`, `spectroscopy`;
- measures take their canonical names from the measure vocabulary
  (`vocab/measures.json`); an unknown measure is warned about, a known one under another
  spelling is an error; a contract table's measures are those `analysis.json` lists;
- `references` labels `registration`, `finding` and `doi` have an agreed meaning.

- **runs** (§3.2): a folder is one run of an analysis, `run: {id, label, supersedes}`
  (required; the writer fills in a time-stamped id when none is given). Runs of one id
  share modality and analysis type; a test held by two runs is an error unless the later
  supersedes the earlier (per test); corrections stay with their runs. `check` checks
  runs across a results root (`check_runs`); the writer checks a new run against its
  siblings. Recommended layout `<root>/<id>/<run id>/` (`spec.run_folder`).

The checker reads 0.1 and 0.2, each folder by the rules of the version it declares.
neurofaune's TBSS and randomise writers now write 0.2 ids (`dwi/tbss/<name>`,
`anat/vbm/<name>`, `func/voxelwise/<name>`).


## 0.3.0 — 2026-10-20 (draft)

The minimum detectable effect (RESULTS_SPEC.md §5.1): beside each test, the smallest
difference its design could have detected, so a finding's size -- and a null -- is read
against what the study could see. Asked for by DUET (OPEN.md #151); the same names and
formula are written by neurofaune, source-analytics and neurovrai.

- standard terms `se` (standard error of the estimate, from the fitted model),
  `mde` (`(t(1 - Alpha/2, df) + t(Power, df)) * se`, normal quantiles without a finite
  df; requires the new `Power` qualifier and `Alpha`), `mde_percent` (percent of the
  reference group's mean) and `mde_note` (why an `mde` is not given, starting
  `not computed: `);
- the producers write power 0.80 and two-sided alpha 0.05, nominal (no
  multiple-comparison correction);
- the checker, for folders that declare 0.3: an `mde` is positive and its `Power` /
  `Alpha` lie in (0, 1); a row without an `mde` carries an `mde_note`, and a row with one
  leaves it empty; `mde_percent` is positive and only beside an `mde`; `se` is >= 0; a
  tests table with neither `mde` nor `mde_note` is warned about. A folder declaring an
  earlier version may not use the 0.3 terms.

The checker reads 0.1, 0.2 and 0.3, each folder by the rules of the version it declares.
neurofaune's randomise read-out (TBSS, VBM, voxelwise fMRI) writes 0.3: `whole_se`,
`whole_mde`, `whole_mde_percent`, `whole_mde_note` on tests rows (the test on each
subject's whole-mask mean), `mde_note` "not computed: cluster selected by the test" on
cluster rows, and a caveat that the voxelwise maps' MDE is not computed (randomise
corrects them).
