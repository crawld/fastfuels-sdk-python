# FastFuels SDK: v1 → v2 Transition Plan (Versioned Subpackages)

## Context

The FastFuels API is upgrading from v1 (`https://api.fastfuels.silvxlabs.com`) to v2
(`https://api-v2-prod-782971006568.us-west1.run.app`). These are **separate live
services**: users hold existing v1 resources and will need to access them while
adopting v2.

The SDK will follow the **versioned-subpackage** strategy (the pattern used by
Google Cloud client libraries): `fastfuels_sdk.v1` and `fastfuels_sdk.v2` coexist in
one package on one branch, and the top-level `fastfuels_sdk` namespace re-exports the
"default" version.

```python
from fastfuels_sdk.v1 import Domain      # explicit v1
from fastfuels_sdk.v2 import Domain      # explicit v2
from fastfuels_sdk import Domain         # default (v1 until 2.0.0, v2 after)
```

### Why subpackages instead of a `v1.x` maintenance branch

- **One release train.** A v1 bugfix is a normal commit on `main` that ships in the
  next release — no cherry-picks, no second branch, no separate docs deploy.
- **One docs site.** v1 and v2 are nav sections in the existing mkdocs site (matching
  the v1/v2 tabs in the FastFuels-Web documentation service). No Mike, no gh-pages
  history manipulation, no tag-prefix routing.
- **Users can run both APIs in one environment** during migration — impossible with
  the branch strategy.
- **v2 ships as an installable preview** during development. Users can try
  `fastfuels_sdk.v2` from a normal 0.x release before 2.0.0 locks in the default.
- **v1 is frozen code, not parallel development.** The v1 API gets no new features,
  so the subpackage is write-once, bugfix-only. Carrying it costs a few hundred KB in
  the wheel. When the v1 API sunsets, deleting `fastfuels_sdk/v1/` in a 3.0.0 release
  is the whole cleanup.
- **The migration story is one line.** At 2.0.0, unpinned users whose code breaks fix
  it with `from fastfuels_sdk.v1 import ...` instead of rewriting or pinning.

### Target layout

```
fastfuels_sdk/
├── __init__.py            # re-exports the default version (v1 now, v2 at 2.0.0)
├── v1/
│   ├── __init__.py        # current top-level __init__.py contents
│   ├── api.py, domains.py, inventories.py, features.py, exports.py,
│   │   pointclouds.py, convenience.py, exceptions.py, utils.py, grids/
│   └── client_library/    # current v1 generated client (openapi-generator, pydantic)
└── v2/
    ├── __init__.py
    ├── api.py             # v2 auth + client construction
    ├── client_library/    # v2 generated client (openapi-python-client, attrs/httpx)
    └── domains.py, ...    # new wrapper modules, built incrementally
```

---

## Phase 0: Modernize packaging to pyproject.toml + uv — release **0.20.0** ✅ implemented

> Status: implemented in the working tree (2026-06-05). Latest published release at
> implementation time was **0.19.1** (the plan originally assumed 0.18.2 — stale).
> Remaining: commit, PR, and cut the 0.20.0 release.

Goal: replace `setup.py` + `requirements/` with a single `pyproject.toml` managed by
uv, shipped as a packaging-only release **before** any code moves, so packaging
fallout is never conflated with the restructure.

1. **Rewrite the root `pyproject.toml`** (the current untracked one is uv scratch
   with the wrong name/version — `fastfuels-sdk-python` / `0.1.0` — and dev tools in
   runtime deps):

   ```toml
   [build-system]
   requires = ["hatchling", "hatch-vcs"]
   build-backend = "hatchling.build"

   [project]
   name = "fastfuels-sdk"
   description = "3D Fuels for Next Generation Fire Models"
   readme = "README.md"
   license = "MIT"
   requires-python = ">=3.11"
   dynamic = ["version"]
   dependencies = [
       "geopandas",
       "numpy",
       "pandas",
       "pydantic>=2",
       "requests",
       "scipy",
       "urllib3>=2.1.0",
       "zarr",
   ]

   [project.urls]
   Homepage = "https://github.com/silvxlabs/fastfuels-sdk-python"
   "Bug Tracker" = "https://github.com/silvxlabs/fastfuels-sdk-python/issues"

   [dependency-groups]
   dev = ["pytest", "pre-commit", "ipykernel"]
   docs = ["mkdocs", "mkdocs-material", "mkdocstrings", "mkdocstrings-python"]

   [tool.hatch.version]
   source = "vcs"

   [tool.hatch.build]
   exclude = [
       "fastfuels_sdk/client_library_v2",            # scratch v2 client (Phase 2)
       "fastfuels_sdk/client_library/*.sh",          # regeneration scaffolding
       "fastfuels_sdk/client_library/README.md",
       "fastfuels_sdk/client_library/api_spec.json",
       "fastfuels_sdk/client_library/openapi-generator-config.yaml",
   ]

   [tool.hatch.build.targets.wheel]
   packages = ["fastfuels_sdk"]
   ```

   Notes:
   - **Versioning:** `hatch-vcs` derives the version from the checked-out git tag —
     the modern replacement for `setup.py`'s build-time GitHub API call, preserving
     the existing "version comes from the release tag" workflow with no network
     dependency and reproducible rebuilds of old versions. (Alternative: a static
     `version = "..."` bumped per release — simpler mechanics, but adds a manual
     bump step the project has never had.) Existing `vX.Y.Z` tags parse as-is.
   - **`requires-python = ">=3.11"`:** the current scientific stack forces this —
     latest numpy/scipy require ≥3.11 (zarr 3.2 even requires ≥3.12), so a lower
     floor would make uv's universal lock hold the whole stack at old versions while
     real 3.12+ users get new ones. Drops 3.9 (EOL Oct 2025) and 3.10 (EOL Oct
     2026); those users stay on ≤0.19.1. Still satisfies the v2 generated client's
     `^3.10` floor (Phase 2).
   - **Build excludes:** the wheel-content diff against the published 0.19.1 wheel
     surfaced two things hatchling would otherwise ship that `setup.py` didn't: the
     scratch `client_library_v2/` tree and the client regeneration scaffolding in
     `client_library/` (`*.sh`, `api_spec.json`, generator config, README). Both are
     excluded via `[tool.hatch.build].exclude`; the `client_library_v2` exclude is
     removed in Phase 2 when the client is promoted.
   - The `requirements-txt-fixer` pre-commit hook was removed along with
     `requirements/`.
   - The `package_data` templates entry in `setup.py` is dead config — no
     `templates/` directory exists. Hatchling includes package subdirectories and
     non-Python files automatically.

2. **Delete `setup.py` and `requirements/`** (`requirements.txt` →
   `[project.dependencies]`, `test_requirements.txt` → `dev` group,
   `docs.txt` + the ad-hoc pip installs in `docs.yml` → `docs` group).

3. **Regenerate and commit `uv.lock`** (`uv lock`). The lock pins dev/CI
   environments only — it does not constrain consumers of the library.

4. **Update workflows to uv:**

   `tests_main.yml` / `tests_cron.yml`:

   ```yaml
   steps:
     - uses: actions/checkout@v4
     - uses: astral-sh/setup-uv@v6
       with:
         python-version: ${{ matrix.python-version }}
         enable-cache: true
     - run: uv sync
     - run: uv run pytest tests/
   ```

   `publish_to_pypi.yml`:

   ```yaml
   steps:
     - uses: actions/checkout@v4
       with:
         fetch-depth: 0  # hatch-vcs needs tag history to derive the version
     - uses: astral-sh/setup-uv@v6
     - run: uv build
     - run: uv publish
       env:
         UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
   ```

   (Optional later upgrade: PyPI trusted publishing instead of the token.)

   `docs.yml`:

   ```yaml
   steps:
     - uses: actions/checkout@v4
     - uses: astral-sh/setup-uv@v6
     - run: uv sync --group docs
     - run: uv run mkdocs gh-deploy --force
   ```

   `pre-commit.yml` is fine as-is.

5. **Clean up stale local branches** once any useful content is salvaged:
   `v1`, `v1.x`, `v2-dev`, `upgrade-to-v2`. None are needed under this plan.

6. Delete `.run/` from the repo root or gitignore it.

7. Release **0.20.0** (packaging-only, no code changes; minor bump for the
   `requires-python` floor change) and verify it publishes and installs cleanly
   before starting Phase 1.

---

## Phase 1: Move v1 into `fastfuels_sdk/v1/` — release **0.21.0**

Goal: restructure with **zero change to the documented public surface**.
`from fastfuels_sdk import Domain` keeps working.

1. **Move the code** (preserve history with `git mv`):

   ```bash
   mkdir fastfuels_sdk/v1
   git mv fastfuels_sdk/{api.py,convenience.py,domains.py,exceptions.py,exports.py,\
   features.py,inventories.py,pointclouds.py,utils.py,grids,client_library} fastfuels_sdk/v1/
   git mv fastfuels_sdk/__init__.py fastfuels_sdk/v1/__init__.py
   ```

2. **Rewrite internal imports.** 18 wrapper files use absolute
   `from fastfuels_sdk.X import ...` imports (~130 occurrences). Sed
   `from fastfuels_sdk.` → `from fastfuels_sdk.v1.` across `fastfuels_sdk/v1/`.
   (Or convert to relative imports, which makes the package relocatable and avoids
   a repeat of this step.) The generated `client_library/` also self-references
   `fastfuels_sdk.client_library` — include it in the sweep, and update the
   regeneration config so future regens emit the `v1` path.

3. **New top-level `fastfuels_sdk/__init__.py`** — re-export the v1 surface
   unchanged:

   ```python
   from fastfuels_sdk.v1 import *          # noqa: F401,F403
   from fastfuels_sdk.v1 import __all__    # noqa: F401
   ```

   `fastfuels_sdk/v1/__init__.py` keeps the existing explicit imports and `__all__`.

4. **Known break (document in changelog):** deep imports like
   `from fastfuels_sdk.client_library.models import X` become
   `from fastfuels_sdk.v1.client_library.models import X`. No `sys.modules` shims —
   the documented surface is the top-level names, and a shim is the kind of
   cleverness this plan is trying to avoid.

5. **Move tests:** `git mv` existing test modules into `tests/v1/`, keep shared
   fixtures in `tests/conftest.py`. Update the `pytest` invocation in CI if needed
   (currently `cd tests/ && pytest` — still works).

6. **Docs:** move `docs/guides/`, `docs/tutorials/`, `docs/reference.md` under
   `docs/v1/`. Update mkdocstrings identifiers in `reference.md`
   (`::: fastfuels_sdk.domains` → `::: fastfuels_sdk.v1.domains`) and the
   `mkdocs.yml` nav:

   ```yaml
   nav:
     - Home: index.md
     - v1 (current):
       - How-To Guides: ...
       - Tutorials: ...
       - Reference: v1/reference.md
   ```

7. **Verify** (see Verification below), then release **0.21.0**. The workflows
   modernized in Phase 0 need no further changes.

---

## Phase 2: Build v2 under `fastfuels_sdk/v2/` — 0.x preview releases

1. **Promote the generated v2 client.** It currently sits at
   `fastfuels_sdk/client_library_v2/fast-fuels-api-client/fast_fuels_api_client/` —
   a full openapi-python-client *project* (own `pyproject.toml`, hyphenated dir,
   `.ruff_cache`) that is not importable where it is and must not ship as-is. Move
   the inner package:

   ```bash
   git mv fastfuels_sdk/client_library_v2/fast-fuels-api-client/fast_fuels_api_client \
          fastfuels_sdk/v2/client_library
   rm -rf fastfuels_sdk/client_library_v2
   ```

   The generated code uses relative imports throughout (`from ...models import`),
   so **no import rewriting is needed** — it works at any location.

2. **Record the regeneration recipe** in `fastfuels_sdk/v2/client_library/README.md`
   so regens are reproducible, e.g.:

   ```bash
   openapi-python-client generate \
     --url https://api-v2-prod-782971006568.us-west1.run.app/openapi.json \
     --meta none --output-path fastfuels_sdk/v2/client_library --overwrite
   ```

   (`--meta none` emits just the package, no poetry scaffolding.)

3. **Add v2 dependencies:**
   `uv add "httpx>=0.23.0,<0.29.0" "attrs>=22.2.0" python-dateutil`.
   The v1 stack (`pydantic>=2`, `urllib3`, `requests`) stays until v1 is removed.
   No version conflicts between the two stacks.

4. **Write `fastfuels_sdk/v2/api.py`** — auth and client construction:
   - Read `FASTFUELS_API_KEY` (same variable as v1) by default. **Open decision:**
     if v1/v2 keys are not interchangeable across the two deployments, add
     `FASTFUELS_API_V2_KEY` as an override and document precedence.
   - **Open decision:** the Cloud Run URL is an implementation detail; put a stable
     custom domain (e.g. `api-v2.fastfuels.silvxlabs.com`) behind it before GA so
     the SDK default doesn't churn.

5. **Write v2 wrapper modules incrementally** (`domains.py`, `grids.py`,
   `inventories.py`, `exports.py`, ...), mirroring v1's resource-object ergonomics
   where the v2 API allows. Note the v2 client is attrs-based, not pydantic — the
   `model_fields` copy pattern from `api-response-initialization-pattern.md` is
   obsolete for v2 code; use the generated `to_dict()`/`from_dict()` and plain
   attribute access instead.

6. **Tests** in `tests/v2/`. Split CI into two named jobs so failures are
   attributable (`tests_main.yml`):

   ```yaml
   jobs:
     test-v1:
       # checkout / setup-uv / uv sync as in Phase 0, then:
       # uv run pytest tests/v1
     test-v2:
       # same, then:
       # uv run pytest tests/v2
   ```

   Once v2 stabilizes, drop `tests/v1` from `tests_cron.yml` (keep it on PRs) to
   stop burning weekly live-API resources on frozen code.

7. **Docs:** add a `v2 (preview)` nav section with its own guides and
   `docs/v2/reference.md` as wrappers land.

8. Ship continuously as **0.22.0, 0.23.0, …** with v2 documented as preview. Each
   release publishes through the existing unmodified workflows.

---

## Phase 3: Flip the default — release **2.0.0**

Cut this release when the v2 wrapper covers the core workflow (domain → grids →
export) and has been exercised in preview.

1. (Optional, one release ahead) emit a `FutureWarning` from the top-level
   `__init__.py`: "fastfuels_sdk will default to the v2 API in 2.0.0; pin
   `fastfuels-sdk<2` or import from `fastfuels_sdk.v1` explicitly."
2. Change the top-level `__init__.py` to re-export from `.v2`.
3. Write a short migration guide in the docs: stay on v1 by changing imports to
   `fastfuels_sdk.v1` (one line) or pinning `fastfuels-sdk<2`; or migrate to v2.
4. Reorder docs nav: `v2 (current)` first, `v1 (legacy)` second.
5. Tag `v2.0.0`. The existing PyPI and docs workflows handle it unchanged.

**Rule: the default never flips silently mid-0.x.** Top level stays v1 until exactly
2.0.0.

---

## Phase 4 (eventual): Remove v1 — release **3.0.0**

When the v1 API is decommissioned:

1. Delete `fastfuels_sdk/v1/`, `tests/v1/`, and the v1 docs section.
2. `uv remove pydantic urllib3 requests` if nothing outside `v1/` uses them.
3. Release 3.0.0. Users needing v1 archaeology pin `fastfuels-sdk<3`.

---

## What this plan deliberately does NOT include

| Old-plan item | Status |
|---|---|
| `v1.x` maintenance branch | Not needed — v1 fixes ship from `main`. Old releases on PyPI serve pinners. |
| Mike versioned docs | Not needed — one site, v1/v2 nav sections. (Mike remains an option later for SDK 2.x vs 3.x docs, a different axis than API v1/v2.) |
| Docs tag-routing in `docs.yml` | Not needed — workflow unchanged. |
| CI triggers for a second branch | Not needed — one branch. |

---

## Files modified (by phase)

| Phase | File | Change |
|---|---|---|
| 0 | `pyproject.toml` | rewrite: real metadata, hatchling + hatch-vcs, dependency groups |
| 0 | `setup.py`, `requirements/` | delete (folded into `pyproject.toml`) |
| 0 | `uv.lock` | regenerate and commit |
| 0 | all four workflows | switch to `setup-uv` + `uv sync` / `uv build` / `uv publish` |
| 0 | `.run/` | remove or gitignore |
| 1 | `fastfuels_sdk/*` | move into `fastfuels_sdk/v1/`, rewrite imports |
| 1 | `fastfuels_sdk/__init__.py` | new: re-export from `.v1` |
| 1 | `tests/*` | move into `tests/v1/` |
| 1 | `docs/*`, `mkdocs.yml` | move under `docs/v1/`, nav sections, mkdocstrings ids |
| 2 | `fastfuels_sdk/v2/` | promoted client + new wrappers |
| 2 | `pyproject.toml` | `uv add httpx attrs python-dateutil` |
| 2 | `.github/workflows/tests_main.yml`, `tests_cron.yml` | split v1/v2 jobs; later drop v1 from cron |
| 3 | `fastfuels_sdk/__init__.py` | re-export from `.v2` |

After Phase 0, packaging and workflows need **no further changes** in Phases 1 and 3:
hatchling's `packages = ["fastfuels_sdk"]` includes the new `v1`/`v2` subpackages
automatically, and releases flow through the same tag → build → publish pipeline.

---

## Verification

**Phase 0:**
1. `uv sync && uv run pytest tests/` — suite passes in the uv-managed environment.
2. `uv build`, then compare wheel contents against the published 0.19.1 wheel
   (`unzip -Z1`) — same modules, correct `fastfuels-sdk` name, and a version
   derived from the current tag (visible in the built filename).
   *Result: exact 186-file parity after adding the build excludes.*
3. Clean-venv install of the built wheel:
   `from fastfuels_sdk import Domain, list_domains, export_roi`.
4. Release **0.20.0** and confirm the tag → `uv publish` → PyPI → `docs.yml` chain
   end-to-end.

**Phase 1 (the risky one):**
1. `pytest tests/v1` against the live v1 API — full pass.
2. Build the wheel locally (`uv build`) and inspect: `fastfuels_sdk/v1/`
   and `fastfuels_sdk/v1/client_library/` present, no `client_library_v2`, no stray
   root metadata.
3. In a clean venv, install the wheel and run the smoke test that matters:
   `from fastfuels_sdk import Domain, list_domains, export_roi` plus one round-trip
   `export_roi` call.
4. `mkdocs serve` — v1 nav section renders, mkdocstrings reference resolves.

**Phase 2:**
1. `from fastfuels_sdk.v2.client_library.api.domains import create_domain` imports
   cleanly in the built wheel.
2. `pytest tests/v2` against the live v2 API.

**Phase 3:**
1. Clean-venv install of the 2.0.0 wheel: `from fastfuels_sdk import Domain` is the
   v2 class; `from fastfuels_sdk.v1 import Domain` still round-trips against the v1
   API.
