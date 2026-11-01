# NX-Böschung und Abraum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax; no implementation on G02 source.

**Goal:** Native, reopened NX study assemblies with measurable excavation and matched sand piles.
**Architecture:** Pure Python terrain/polyhedron/material core, STEP mesh interchange and separate real NX clone/build/verify journals. Existing G02 delivery reused as immutable source. Generation manifests bind outputs to current inputs.
**Tech Stack:** Python>=3.10 standard library; NX2406 Python via run_journal; Git LFS.
**Spec:** `docs/plans/2026-11-01-nx-boeschung-studie-spec.md`.

## Global Constraints

- G02 bytes and native originals unchanged. Independent saved copies; no cross-state/original component links.
- mm; height transform once. No invented extension foundation/slab elevation.
- 45°/800mm/2000mm are study assumptions; all construction_release=false.
- Loose1.05 and compacted0.89 are illustrative volume ratios; no invented dry density. Model pile1:2; finite positive volume.
- Actual NX creation, fresh and moved reopening, path/unit/volume validation required; only actual evidence is PASS.

## Review Focus

1. Concave house and closed end slopes cross excluded land/buildings: keep conflict visible, no silent crop.
2. DGM bilinear saddle: approximation bound and consistent volume geometry, no hidden flat ground.
3. Mesh T-junctions or negative volumes: closed-manifold checks and analytical flat cases.
4. Material factor direction and repeated excavation: deficit/import and overlaps cannot become fictitious surplus/net excavation.
5. Clone loads original prototypes or filenames collide: exact source/destination inventory and fresh moved reopening.

### Task 1: Geometric/material core and interchange

**Files:** create `renovierung/k02/{__init__,geometry,terrain,materials,mesh_step,planning}.py`, `renovierung/k02/study_config.json`, `renovierung/tests/test_k02_core.py`.
**Interfaces:** `planning.create_plan(repo_root:Path, config:dict)->dict` returns JSON plan with sectors/fields, statuses, closed meshes `{vertices:[[x,y,z]],faces:[[indices]]}`, volumes, stockpile/terrain meshes, provenance and assumptions. Pure functions for clipping/volume and material conversion exposed and tested. No NX imports.

- [ ] Write failing tests: flat 45° end-sloped field analytical volume; slope length/width influence; bilinear saddle refinement bound; mesh closure; property/house conflicts; exclusion/unknown depth; factors1.05/.89; mass-conserving refill deficit; overlap not silently net-summed; pile contact and matched volume on sloping ground.
- [ ] Run tests red, implement core, run green. Use available source terrain reader or equivalent stable parser, preserving imported code bytes. Do not depend on libraries absent in NX Python.
- [ ] Emit minimal FACETED_BREP STEP fixture and mathematical volume. File existence/finite closed mesh checks before handoff.
- [ ] Commit task and report exact tests, plan schema/example and geometric limitations.

### Task 2: Native spike, independent assemblies and verification

**Files:** create `renovierung/k02/{nx_build,nx_verify,runner}.py`, `renovierung/tests/test_k02_runner.py`; modify `tools/nx_project.py`, `tools/run_checks.py`, `.gitignore` only as needed for manifests.
**Interfaces:** consume Task1 plan. `runner.build_study(nx_root:Path,accept:bool)->Path`, `runner.check_study()->list[str]` including current fingerprints. NX journals receive JSON via environment and emit explicit PASS/FAIL report; never load existing user session.

- [ ] Write failing runner tests for stale inputs, failed latest attempt, malformed/missing parts and manifest/master mismatch; actual native checks remain separate.
- [ ] Real minimal NX spike: cube STEP imports as solid with expected m³; three-part clone with unique destinations retains positions, no original references. Save/reopen/move. Iterate only on observed failures.
- [ ] Generate independent basis/field assemblies, visible cut terrain, excavation toggle, slope and pile objects, clear study/status attributes. Excluded/unknown sectors visible without fake quantities. Preserve all source hashes.
- [ ] Real volume check and reopening on generated files; mismatch or missing parts fail closed. Update current pointer only after full success. G02 fingerprint stays its real scope; separate K02 fingerprint includes its inputs/code and base source evidence.
- [ ] Integrate default project check/build to include active study. Unit/runner checks green. Commit and submit task review.

### Task 3: Full delivery, visual review and documentation

**Files:** generated `cad/nx/` study .prt/manifests, `renovierung/planung/` quantity JSON and readable report, docs development evidence/readme/current entry updates.

- [ ] Run actual complete study build. Run all relevant offline tests and `tools/nx_project.py check`.
- [ ] Verify full and moved reopening, original hashes, internal paths, mm, matching NX volumes. Inspect actual NX views for cut visibility, slopes, placement, excluded status.
- [ ] Document per-field bank/loose/compacted/refill quantities and sensitivity; blocked sectors and remaining uncovered areas. No construction or net-volume claims beyond implementation.
- [ ] Fresh whole-branch subagent review; resolve important findings, recheck changed scope. Commit and push authorized deliverables. Keep user-accessible primary checkout coherent with delivered branch; preserve unrelated changes.
