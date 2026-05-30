from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "browser-runner"))

from run_batch import run_batch
from reports import write_report

EVALUATION_MODES = ("baseline", "rule_based", "trainable")
MODE_POLICY = {
    "baseline": "baseline-no-coach",
    "rule_based": "rule-based",
    "trainable": "trainable-ranker",
}


@dataclass(frozen=True)
class ExperimentModeResult:
    evaluation_mode: str
    output_dir: Path
    batch_summary: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {
            "evaluation_mode": self.evaluation_mode,
            "output_dir": str(self.output_dir),
            "batch_summary": self.batch_summary,
        }


def _run_mode(*, evaluation_mode: str, runner_mode: str, experiment_id: str, sessions: int, output_root: Path) -> ExperimentModeResult:
    if evaluation_mode not in EVALUATION_MODES:
        raise ValueError(f"Unsupported evaluation mode: {evaluation_mode}")
    mode_dir = output_root / evaluation_mode
    previous_policy = os.environ.get("MODEL_VERSION_OR_POLICY")
    os.environ["MODEL_VERSION_OR_POLICY"] = MODE_POLICY[evaluation_mode]
    try:
        summary = run_batch(
            mode=runner_mode,
            experiment_id=f"{experiment_id}-{evaluation_mode}",
            sessions=sessions,
            output_dir=mode_dir,
        )
    finally:
        if previous_policy is None:
            os.environ.pop("MODEL_VERSION_OR_POLICY", None)
        else:
            os.environ["MODEL_VERSION_OR_POLICY"] = previous_policy
    return ExperimentModeResult(evaluation_mode=evaluation_mode, output_dir=mode_dir, batch_summary=summary)


def _validate_trainable_mode(evaluation_modes: tuple[str, ...], trainable_model: Path | None) -> None:
    if "trainable" not in evaluation_modes:
        return
    model_path = trainable_model or Path(os.getenv("TRAINABLE_RANKER_MODEL", "artifacts/training/frequency-ranker.json"))
    if not model_path.exists():
        raise FileNotFoundError(f"Trainable evaluation requires a ranker model. Set TRAINABLE_RANKER_MODEL or pass --trainable-model: {model_path}")


def run_experiment(
    *,
    experiment_id: str,
    runner_mode: str,
    sessions_per_mode: int,
    output_root: Path,
    evaluation_modes: tuple[str, ...] = EVALUATION_MODES,
    trainable_model: Path | None = None,
) -> dict[str, Any]:
    _validate_trainable_mode(evaluation_modes, trainable_model)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_trainable_model = os.environ.get("TRAINABLE_RANKER_MODEL")
    if trainable_model is not None:
        os.environ["TRAINABLE_RANKER_MODEL"] = str(trainable_model)
    try:
        results = [
            _run_mode(
                evaluation_mode=evaluation_mode,
                runner_mode=runner_mode,
                experiment_id=experiment_id,
                sessions=sessions_per_mode,
                output_root=output_root,
            )
            for evaluation_mode in evaluation_modes
        ]
    finally:
        if trainable_model is not None:
            if previous_trainable_model is None:
                os.environ.pop("TRAINABLE_RANKER_MODEL", None)
            else:
                os.environ["TRAINABLE_RANKER_MODEL"] = previous_trainable_model
    manifest = {
        "experiment_id": experiment_id,
        "runner_mode": runner_mode,
        "sessions_per_mode": sessions_per_mode,
        "trainable_model": str(trainable_model or os.getenv("TRAINABLE_RANKER_MODEL", "artifacts/training/frequency-ranker.json")) if "trainable" in evaluation_modes else None,
        "evaluation_modes": [result.to_json() for result in results],
    }
    manifest_path = output_root / "experiment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

    reports = {}
    mode_dirs = {result.evaluation_mode: result.output_dir for result in results}
    if "baseline" in mode_dirs and "rule_based" in mode_dirs:
        report_path = output_root / "baseline_vs_rule_based.md"
        reports["baseline_vs_rule_based"] = write_report(baseline_path=mode_dirs["baseline"], treatment_path=mode_dirs["rule_based"], output=report_path)
    if "baseline" in mode_dirs and "trainable" in mode_dirs:
        report_path = output_root / "baseline_vs_trainable.md"
        reports["baseline_vs_trainable"] = write_report(baseline_path=mode_dirs["baseline"], treatment_path=mode_dirs["trainable"], output=report_path)
    manifest["manifest_path"] = str(manifest_path)
    manifest["reports"] = reports
    manifest["report"] = reports.get("baseline_vs_rule_based")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _parse_modes(value: str) -> tuple[str, ...]:
    modes = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = sorted(set(modes) - set(EVALUATION_MODES))
    if unknown:
        raise argparse.ArgumentTypeError(f"Unknown evaluation modes: {', '.join(unknown)}")
    return modes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run baseline/rule-based/trainable evaluation batches and write a comparison report")
    parser.add_argument("--experiment-id", default=f"exp_{int(time.time())}")
    parser.add_argument("--runner-mode", choices=["mock", "validation", "bulk"], default="mock")
    parser.add_argument("--sessions-per-mode", type=int, default=6)
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/evaluation-experiments/latest"))
    parser.add_argument("--evaluation-modes", type=_parse_modes, default=EVALUATION_MODES, help="Comma-separated modes: baseline,rule_based,trainable")
    parser.add_argument("--trainable-model", type=Path, help="Frequency ranker JSON used when trainable mode is included")
    args = parser.parse_args()
    print(json.dumps(run_experiment(
        experiment_id=args.experiment_id,
        runner_mode=args.runner_mode,
        sessions_per_mode=args.sessions_per_mode,
        output_root=args.output_root,
        evaluation_modes=args.evaluation_modes,
        trainable_model=args.trainable_model,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
