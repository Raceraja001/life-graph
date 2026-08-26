# Releasing Life Graph to PyPI

> **A human runs the upload.** Every command in the *Publish* section below is
> outward-facing and irreversible — a version number, once uploaded to PyPI, can
> never be reused, even after `yank` or delete. Agents prepare and verify the
> artifact; the developer runs `twine upload`. Do not delegate that step.

The package name is **`life-graph`** (importable as `life_graph`). It was
confirmed unclaimed on PyPI on 2026-08-26.

---

## 0. Prerequisites (once)

1. A PyPI account with 2FA enabled, and a TestPyPI account (separate registration).
2. A **project-scoped API token** from each. Until the first upload exists there is
   no project to scope to, so the first token must be account-scoped — regenerate a
   project-scoped one immediately after the first successful release and delete the
   account-scoped one.
3. Store the tokens. Either of these works; pick one, don't mix them:

   **`~/.pypirc`** (chmod 600 — it holds live credentials):

   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-AgEIcHlwaS5vcmc...      # the full token, including the pypi- prefix

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-AgENdGVzdC5weXBp...
   ```

   ```bash
   chmod 600 ~/.pypirc
   ```

   **Or environment variables** (nothing on disk; preferred for CI):

   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD='pypi-AgEIcHlwaS5vcmc...'
   ```

4. Build tooling in the venv:

   ```bash
   python -m pip install --upgrade build twine
   ```

---

## 1. Bump the version

Two files carry a version number. Set both to the same value:

| File | Field |
|------|-------|
| `pyproject.toml` | `[project] version` |
| `CHANGELOG.md` | a new `## [X.Y.Z] — YYYY-MM-DD` heading |

`life_graph.__version__` is **not** bumped by hand — it reads the installed
distribution's metadata, so it follows `pyproject.toml` automatically. It used
to be a third literal and drifted to `0.1.0` while the other two said `1.1.0`.
In a source tree that was never `pip install`ed it reports `0.0.0+unknown`.

```bash
grep -n 'version' pyproject.toml | head -3
head -12 CHANGELOG.md
```

Semantics: PyPI orders releases by [PEP 440](https://peps.python.org/pep-0440/).
Breaking API change → major; new endpoints/tables → minor; fixes only → patch.
Pre-releases use a suffix PyPI understands and `pip` skips by default:
`1.2.0rc1`, `1.2.0a1`.

Do **not** write changelog entries for releases that did not happen.

---

## 2. Build

Always build from a clean `dist/` — `twine upload dist/*` will otherwise try to
re-upload stale artifacts from a previous version and fail the whole command.

```bash
rm -rf dist/ build/ *.egg-info
python -m build
ls -l dist/
```

This produces two files: `life_graph-X.Y.Z-py3-none-any.whl` and
`life_graph-X.Y.Z.tar.gz`.

> The build backend is **hatchling**, configured in `pyproject.toml` under
> `[tool.hatch.build.targets.*]`. There is no `MANIFEST.in`; adding one would have
> no effect. The sdist uses an **allow-list**, so a new file at the repo root is
> excluded until it is named explicitly — that is deliberate, and it is what keeps
> `.env`, `.comms/`, `logs/` and `.run/` out of the tarball.

---

## 3. Verify before uploading

### 3a. Metadata check

```bash
python -m twine check dist/*
```

Must print `PASSED` for both files. A `FAILED` here means PyPI would reject the
long-description render.

### 3b. Eyeball the contents

```bash
python -m zipfile -l dist/*.whl
tar tzf dist/*.tar.gz | head -50
```

Confirm the wheel contains every `life_graph/` subpackage (including newer ones
such as `life_graph/integrations/`) and `life_graph/_alembic/versions/`.

### 3c. Secrets audit

```bash
tar tzf dist/*.tar.gz | grep -E '(^|/)\.env$|\.pem$|\.key$|credential|secret|\.pypirc' || echo "clean"
python -m zipfile -l dist/*.whl | grep -E '(^|/)\.env$|\.pem$|\.key$|credential' || echo "clean"
```

`.env.example` is expected and is fine — it contains only empty placeholders.
A bare `.env` is not.

### 3d. Clean-venv smoke test

Never test against the repo checkout — `import life_graph` would resolve to the
source tree and prove nothing.

```bash
python -m venv /tmp/lg-verify
/tmp/lg-verify/bin/pip install --quiet dist/life_graph-*.whl
cd /tmp && /tmp/lg-verify/bin/python -c "import life_graph; print(life_graph.__version__)"
/tmp/lg-verify/bin/life-graph --help
rm -rf /tmp/lg-verify
```

---

## 4. TestPyPI dry run

TestPyPI is a separate index with separate accounts and separate version history.
Burning a version number there costs nothing.

```bash
python -m twine upload --repository testpypi dist/*
```

Then install from it. `--extra-index-url` is required because TestPyPI does not
mirror the real dependency tree:

```bash
python -m venv /tmp/lg-testpypi
/tmp/lg-testpypi/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  life-graph
/tmp/lg-testpypi/bin/life-graph --help
rm -rf /tmp/lg-testpypi
```

---

## 5. Publish — **the developer runs this**

```bash
python -m twine upload dist/*
```

With `~/.pypirc` in place this needs no further arguments. With environment
variables, make sure `TWINE_USERNAME=__token__` is exported first.

Irreversible. `pip install life-graph` is live worldwide the moment it returns.

---

## 6. Post-release verification

```bash
python -m venv /tmp/lg-pypi
/tmp/lg-pypi/bin/pip install life-graph
/tmp/lg-pypi/bin/python -c "import life_graph; print(life_graph.__version__)"
/tmp/lg-pypi/bin/life-graph --help
rm -rf /tmp/lg-pypi
```

Then:

```bash
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z
```

and check <https://pypi.org/project/life-graph/> renders the README correctly.

---

## Known gaps to close before or shortly after the first release

- **No `LICENSE` file.** `pyproject.toml` and `README.md` both declare MIT, but no
  licence text exists in the repo, so none ships in the artifacts. Metadata that
  claims a licence the package does not carry is a real problem for anyone
  evaluating adoption. Add `LICENSE` at the repo root, add `"/LICENSE"` to
  `[tool.hatch.build.targets.sdist] include`, then rebuild.
- **Migrations ship but are not wired.** `alembic/` is force-included into the
  wheel at `life_graph/_alembic/`, so the revisions are present after
  `pip install life-graph`. Nothing reads them yet: `alembic.ini` still has
  `script_location = alembic`, a repo-relative path. A `life-graph migrate`
  subcommand in `life_graph/cli.py` that points alembic at the packaged directory
  would make a pip-only install able to create its own schema.
- **`sentence-transformers` and `spacy` are hard runtime dependencies.** Together
  they pull roughly **4 GB** (torch ≈ 1.1 GB, the bundled NVIDIA CUDA libraries
  ≈ 2.7 GB, transformers, scipy) into every `pip install life-graph`. Both are
  imported lazily behind `ImportError` guards, so moving them to an extra would
  not break anything at import time — but it would silently downgrade embeddings
  to empty vectors and NLP extraction to the regex tier for anyone who installs
  the default. That trade-off is a product decision, not a packaging one.
