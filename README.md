# neurobox-dev

*A working name; it will change.*

The shared ground for results from every analysis tool, MRI and EEG:

- **The results specification** (`docs/RESULTS_SPEC.md`): what an analysis writes so anyone can read it without the tool that produced it: `analysis.json`, `provenance.json`, and every table with a column dictionary.
- **Its JSON Schemas and the conformance checker**: `python -m neurobox check <folder or results root> [--json]`.
- **The writer** producers call (`write_analysis`, `write_columns`, `provenance`).
- **The study gallery shell** (`neurobox.gallery`): each tool's `gallery build` writes its figures and `analysis.json` files, then calls `neurobox.gallery.build(study, settings)` once. It finds the analysis folders that conform under the paths `gallery.yaml` names, places each in the first section it matches, and writes one static folder (`index.html`, the listed tables and figures, no server needed). The settings format is in the module's docstring; `python -m neurobox gallery <study>` builds from `gallery.yaml` (with PyYAML) or `gallery.json`.

Standard library only, so any producer or reader can install it without another tool's stack.

```bash
pip install "neurobox-dev @ git+https://github.com/alexedmon1/neurobox-dev@<commit>"
python -m neurobox check path/to/results
python -m neurobox gallery path/to/study        # reads path/to/study/gallery.yaml or gallery.json
```

**Where it came from:** neurofaune's `neurofaune.results` (spec 0.3.0), moved here unchanged on 2026-11-03 so EEG tools can use it without installing neurofaune. It is **optional everywhere**: tools run without it, and use it when installed. neurofaune takes it as an extra (`neurofaune[results]`) and re-exports it as `neurofaune.results`, and the identifier written in each `analysis.json` stays `"neurofaune.results"` until the final name is chosen. **0.4.0** (2026-11-03, draft) extends it to EEG and adds what cuprizone's first real run found missing; every addition is optional, so 0.3 folders still conform (`CHANGELOG.md`). **0.4.1** (2026-11-04) adds declared contrasts, variants of one analysis and a recordings table, for the study galleries.

Producers: neurofaune (TBSS, VBM, voxelwise fMRI); planned: source-analytics, source-localization, neurovrai.
