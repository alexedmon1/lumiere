# neurobox-dev

*A working name; it will change.*

The shared ground for results from every analysis tool, MRI and EEG:

- **The results specification** (`docs/RESULTS_SPEC.md`): what an analysis writes so anyone can read it without the tool that produced it: `analysis.json`, `provenance.json`, and every table with a column dictionary.
- **Its JSON Schemas and the conformance checker**: `python -m neurobox check <folder or results root> [--json]`.
- **The writer** producers call (`write_analysis`, `write_columns`, `provenance`).
- **The study gallery shell** (planned): each tool's `gallery build` writes its figures and `analysis.json` files, then calls the shell once for the study.

Standard library only, so any producer or reader can install it without another tool's stack.

```bash
pip install "neurobox-dev @ git+https://github.com/alexedmon1/neurobox-dev@<commit>"
python -m neurobox check path/to/results
```

**Where it came from:** neurofaune's `neurofaune.results` (spec 0.3.0), moved here unchanged on 2026-11-03 so EEG tools can use it without installing neurofaune. neurofaune re-exports it as `neurofaune.results`, and the identifier written in each `analysis.json` stays `"neurofaune.results"` until the final name is chosen. The plan for 0.4 (EEG) is in Esprit's `docs/RESULTS_SCHEMA_DRAFT.md`.

Producers: neurofaune (TBSS, VBM, voxelwise fMRI); planned: source-analytics, source-localization, neurovrai.
