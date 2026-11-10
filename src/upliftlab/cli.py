"""Command-line interface. Parsing and formatting only; statistics live in the library."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from upliftlab import __version__
from upliftlab.config import AnalysisConfig, load_analysis_config
from upliftlab.datasets import (
    available_datasets,
    ensure_dataset,
    fetch_dataset,
    get_spec,
    load_dataset,
)
from upliftlab.errors import (
    AnalysisError,
    ConfigError,
    DataError,
    ReportError,
    SchemaError,
    UpliftError,
)
from upliftlab.experiment import analyze_experiment
from upliftlab.report import render_readout
from upliftlab.results import write_json, write_text
from upliftlab.simulation import SCENARIOS, get_scenario, render_simulation, run_simulation
from upliftlab.uplift import UpliftConfig, render_uplift, run_uplift

_EXIT_CODES: dict[type[UpliftError], int] = {
    ConfigError: 2,
    SchemaError: 3,
    DataError: 4,
    ReportError: 5,
    AnalysisError: 6,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upliftlab",
        description="Experiment readout and budget-constrained uplift targeting.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="download a dataset and verify its checksum")
    fetch.add_argument("dataset", choices=available_datasets())
    fetch.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    fetch.add_argument("--force", action="store_true", help="re-download even if cached")

    analyze = subparsers.add_parser("analyze", help="run an experiment readout")
    analyze.add_argument("dataset", choices=available_datasets())
    analyze.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    analyze.add_argument("--config", type=Path, default=None, help="TOML with a [readout] table")
    analyze.add_argument("--out", type=Path, default=None, help="write Markdown here")
    analyze.add_argument("--json", type=Path, default=None, help="write canonical JSON here")
    analyze.add_argument("--force", action="store_true", help="overwrite existing outputs")

    simulate = subparsers.add_parser("simulate", help="run the synthetic calibration benchmark")
    simulate.add_argument(
        "--scenario",
        choices=["all", *(scenario.name for scenario in SCENARIOS)],
        default="all",
    )
    simulate.add_argument("--replications", type=int, default=5000)
    simulate.add_argument("--seed", type=int, default=42)
    simulate.add_argument("--out", type=Path, default=None, help="write JSON here")
    simulate.add_argument("--markdown", type=Path, default=None, help="write Markdown here")
    simulate.add_argument("--force", action="store_true", help="overwrite existing outputs")

    uplift = subparsers.add_parser("uplift", help="fit an uplift model and price a budget policy")
    uplift.add_argument("dataset", choices=available_datasets())
    uplift.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    uplift.add_argument("--outcome", default="visit")
    uplift.add_argument("--seed", type=int, default=42)
    uplift.add_argument("--budget", type=float, default=0.2, help="target fraction, 0 to 1")
    uplift.add_argument("--value", type=float, default=2.0, help="value per conversion")
    uplift.add_argument("--cost", type=float, default=0.05, help="cost per contact")
    uplift.add_argument("--bootstrap", type=int, default=200, help="policy bootstrap draws")
    uplift.add_argument("--out", type=Path, default=None, help="write JSON here")
    uplift.add_argument("--markdown", type=Path, default=None, help="write Markdown here")
    uplift.add_argument("--force", action="store_true", help="overwrite existing outputs")

    return parser


def _preflight_output(path: Path | None, force: bool) -> None:
    if path is not None and path.exists() and not force:
        raise ReportError(f"{path} exists; pass --force to overwrite")


def _run_fetch(args: argparse.Namespace) -> int:
    dataset = str(args.dataset)
    path = fetch_dataset(dataset, Path(args.data_dir), force=bool(args.force))
    print(f"{dataset}: verified {path}")
    print(f"license: {get_spec(dataset).license_note}")
    return 0


def _run_analyze(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else None
    json_path = Path(args.json) if args.json else None
    if out is not None and json_path is not None and out.resolve() == json_path.resolve():
        raise ReportError("--out and --json must be different paths")
    _preflight_output(out, bool(args.force))
    _preflight_output(json_path, bool(args.force))

    config = load_analysis_config(Path(args.config)) if args.config else AnalysisConfig()
    dataset = load_dataset(str(args.dataset), Path(args.data_dir))
    result = analyze_experiment(dataset, config)
    markdown = render_readout(result)

    if json_path is not None:
        write_json(result.to_dict(), json_path, overwrite=bool(args.force))
        print(f"wrote {json_path}")
    if out is not None:
        write_text(markdown, out, overwrite=bool(args.force))
        print(f"wrote {out}")
    else:
        print(markdown)
    return 0


def _run_simulate(args: argparse.Namespace) -> int:
    replications = int(args.replications)
    seed = int(args.seed)
    if replications < 100:
        raise AnalysisError("--replications must be at least 100")
    if seed < 0:
        raise AnalysisError("--seed must be non-negative")

    out = Path(args.out) if args.out else None
    markdown_path = Path(args.markdown) if args.markdown else None
    if out is not None and markdown_path is not None and out.resolve() == markdown_path.resolve():
        raise ReportError("--out and --markdown must be different paths")
    _preflight_output(out, bool(args.force))
    _preflight_output(markdown_path, bool(args.force))

    selected = SCENARIOS if args.scenario == "all" else (get_scenario(str(args.scenario)),)
    report = run_simulation(replications=replications, seed=seed, scenarios=selected)
    markdown = render_simulation(report)

    if out is not None:
        write_json(report.to_dict(), out, overwrite=bool(args.force))
        print(f"wrote {out}")
    if markdown_path is not None:
        write_text(markdown, markdown_path, overwrite=bool(args.force))
        print(f"wrote {markdown_path}")
    if out is None and markdown_path is None:
        print(markdown)
    return 0


def _run_uplift(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else None
    markdown_path = Path(args.markdown) if args.markdown else None
    if out is not None and markdown_path is not None and out.resolve() == markdown_path.resolve():
        raise ReportError("--out and --markdown must be different paths")
    _preflight_output(out, bool(args.force))
    _preflight_output(markdown_path, bool(args.force))

    dataset = ensure_dataset(str(args.dataset), Path(args.data_dir))
    config = UpliftConfig(
        outcome=str(args.outcome),
        seed=int(args.seed),
        budget_fraction=float(args.budget),
        value_per_conversion=float(args.value),
        cost_per_contact=float(args.cost),
        policy_bootstrap=int(args.bootstrap),
    )
    report = run_uplift(dataset, config)
    markdown = render_uplift(report)

    if out is not None:
        write_json(report.to_dict(), out, overwrite=bool(args.force))
        print(f"wrote {out}")
    if markdown_path is not None:
        write_text(markdown, markdown_path, overwrite=bool(args.force))
        print(f"wrote {markdown_path}")
    if out is None and markdown_path is None:
        print(markdown)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "fetch":
            return _run_fetch(args)
        if args.command == "analyze":
            return _run_analyze(args)
        if args.command == "simulate":
            return _run_simulate(args)
        if args.command == "uplift":
            return _run_uplift(args)
        raise AssertionError(f"unhandled command: {args.command}")
    except UpliftError as exc:
        code = next((code for cls, code in _EXIT_CODES.items() if isinstance(exc, cls)), 1)
        print(f"error: {exc}", file=sys.stderr)
        return code


if __name__ == "__main__":
    raise SystemExit(main())
