# Security

## Supported versions

The project is pre-1.0. Security fixes are applied to the latest commit on `main`; older tags are not maintained.

## Reporting a vulnerability

Use a private GitHub Security Advisory on this repository. Do not open a public issue for a vulnerability.

Include the affected command or module, a minimal reproduction, and the impact. This is a solo project, so response is best effort, normally within 30 days.

## Scope

In scope:

- the dataset download and checksum path,
- schema and input validation,
- the CLI exit-code and error path,
- HTML/Markdown report generation,
- dependency and build configuration.

Out of scope:

- a local user intentionally running untrusted code or modifying the repository,
- denial of service through deliberately huge `--replications` or `--bootstrap` values,
- the security of the upstream dataset hosts.

## Controls

- Downloads use HTTPS, a hard-coded registry, a timeout, a size cap, and a SHA-256 check before the file is used.
- Raw data is never committed, and reports contain aggregate numbers.
- No pickle, joblib, or `numpy.load(allow_pickle=True)` on untrusted files.
- No secrets are required. `.env` files are ignored.
- Dependencies are locked in `uv.lock`; CI uses `uv sync --locked`.
