from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "browser-runner"))
sys.path.insert(0, str(ROOT / "training"))
sys.path.insert(0, str(ROOT / "evaluation"))

from build_live_datasets import build_live_datasets
from check_user_policy_dataset import check_user_policy_rows
from quality_checks import check_dataset, load_jsonl
from run_batch import run_batch
from run_experiment import run_experiment
from train_ranker import train_frequency_ranker
from train_user_policy import train_user_policy
from evaluate_ranker import evaluate_ranker
from evaluate_user_policy import evaluate_user_policy


RUN_MODE_POLICY = {
    "baseline": ("baseline", "baseline-no-coach"),
    "coach": ("coach", "rule-based"),
    "trainable": ("coach", "trainable-ranker"),
}

LEONARDO_JOB_SCRIPTS = {
    "validate": ROOT / "leonardo" / "slurm_validate_live.sh",
    "bulk": ROOT / "leonardo" / "slurm_bulk_live.sh",
    "train": ROOT / "leonardo" / "slurm_train.sh",
    "evaluate": ROOT / "leonardo" / "slurm_evaluation_experiment.sh",
}


@contextmanager
def _temporary_env(**updates: str) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_live_batch(*, execution_mode: str, runner_mode: str, experiment_id: str, sessions: int, output_dir: Path | None) -> dict[str, object]:
    resolved_execution_mode, model_policy = RUN_MODE_POLICY[execution_mode]
    with _temporary_env(RUNNER_EXECUTION_MODE=resolved_execution_mode, MODEL_VERSION_OR_POLICY=model_policy):
        return run_batch(mode=runner_mode, experiment_id=experiment_id, sessions=sessions, output_dir=output_dir)


def cmd_validate_live(args: argparse.Namespace) -> dict[str, object]:
    return _run_live_batch(
        execution_mode=args.execution_mode,
        runner_mode="validation",
        experiment_id=args.experiment_id,
        sessions=args.sessions,
        output_dir=args.output_dir,
    )


def cmd_run_live(args: argparse.Namespace) -> dict[str, object]:
    return _run_live_batch(
        execution_mode=args.execution_mode,
        runner_mode="bulk",
        experiment_id=args.experiment_id,
        sessions=args.sessions,
        output_dir=args.output_dir,
    )


def cmd_build_datasets(args: argparse.Namespace) -> dict[str, object]:
    summary = build_live_datasets(
        traces_path=args.traces,
        user_output=args.user_output,
        coach_output=args.coach_output,
        user_dataset_phase=args.user_dataset_phase,
        coach_dataset_phase=args.coach_dataset_phase,
    )
    summary["user_policy_check"] = check_user_policy_rows(
        [json.loads(line) for line in args.user_output.read_text().splitlines() if line.strip()]
    )
    summary["coach_ranking_check"] = check_dataset(load_jsonl(args.coach_output))
    return summary


def cmd_train_user_policy(args: argparse.Namespace) -> dict[str, object]:
    train_summary = train_user_policy(args.dataset, args.output)
    train_summary["evaluation"] = evaluate_user_policy(args.dataset, args.output)
    return train_summary


def cmd_train_coach_ranker(args: argparse.Namespace) -> dict[str, object]:
    quality = check_dataset(load_jsonl(args.dataset))
    if not quality["valid"]:
        raise SystemExit(json.dumps(quality, indent=2, sort_keys=True))
    train_summary = train_frequency_ranker(args.dataset, args.output)
    train_summary["evaluation"] = evaluate_ranker(args.dataset, args.output)
    return train_summary


def cmd_evaluate(args: argparse.Namespace) -> dict[str, object]:
    modes = tuple(item.strip() for item in args.evaluation_modes.split(",") if item.strip())
    return run_experiment(
        experiment_id=args.experiment_id,
        runner_mode=args.runner_mode,
        sessions_per_mode=args.sessions_per_mode,
        output_root=args.output_root,
        evaluation_modes=modes,
        trainable_model=args.trainable_model,
    )


def cmd_leonardo_submit(args: argparse.Namespace) -> dict[str, object]:
    script = LEONARDO_JOB_SCRIPTS[args.job]
    if not script.exists():
        raise FileNotFoundError(f"Missing Leonardo script: {script}")
    command = ["sbatch", str(script)]
    if args.env_file:
        env = {**os.environ, "LEONARDO_ENV_FILE": str(args.env_file)}
    else:
        env = None
    if args.print_only:
        return {"command": command, "env_file": str(args.env_file) if args.env_file else None, "submitted": False}
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return {"command": command, "submitted": True, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI entrypoint for live UNIQA simulation, dataset building, training, and Leonardo submission")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-live", help="Run a capped live validation batch")
    validate.add_argument("--execution-mode", choices=("baseline", "coach"), default="baseline")
    validate.add_argument("--sessions", type=int, default=12)
    validate.add_argument("--experiment-id", default="validate-live")
    validate.add_argument("--output-dir", type=Path)
    validate.set_defaults(func=cmd_validate_live)

    run_live = subparsers.add_parser("run-live", help="Run the bulk live generation batch")
    run_live.add_argument("--execution-mode", choices=("baseline", "coach"), default="coach")
    run_live.add_argument("--sessions", type=int, default=300)
    run_live.add_argument("--experiment-id", default="run-live")
    run_live.add_argument("--output-dir", type=Path)
    run_live.set_defaults(func=cmd_run_live)

    build = subparsers.add_parser("build-datasets", help="Build user-policy and coach-ranking datasets from traces")
    build.add_argument("--traces", type=Path, required=True)
    build.add_argument("--user-output", type=Path, default=Path("artifacts/datasets/user-policy.jsonl"))
    build.add_argument("--coach-output", type=Path, default=Path("artifacts/datasets/coach-ranking.jsonl"))
    build.add_argument("--user-dataset-phase", default="behavioral_imitation_live")
    build.add_argument("--coach-dataset-phase", default="coach_ranking_live")
    build.set_defaults(func=cmd_build_datasets)

    train_user = subparsers.add_parser("train-user-policy", help="Train the user policy model")
    train_user.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/user-policy.jsonl"))
    train_user.add_argument("--output", type=Path, default=Path("artifacts/training/user-policy.json"))
    train_user.set_defaults(func=cmd_train_user_policy)

    train_coach = subparsers.add_parser("train-coach-ranker", help="Train the coach action ranker")
    train_coach.add_argument("--dataset", type=Path, default=Path("artifacts/datasets/coach-ranking.jsonl"))
    train_coach.add_argument("--output", type=Path, default=Path("artifacts/training/frequency-ranker.json"))
    train_coach.set_defaults(func=cmd_train_coach_ranker)

    evaluate = subparsers.add_parser("evaluate", help="Run baseline/rule-based/trainable evaluation experiments")
    evaluate.add_argument("--experiment-id", default="cli-eval")
    evaluate.add_argument("--runner-mode", choices=("mock", "validation", "bulk"), default="mock")
    evaluate.add_argument("--sessions-per-mode", type=int, default=6)
    evaluate.add_argument("--output-root", type=Path, default=Path("artifacts/evaluation-experiments/latest"))
    evaluate.add_argument("--evaluation-modes", default="baseline,rule_based,trainable")
    evaluate.add_argument("--trainable-model", type=Path, default=Path("artifacts/training/frequency-ranker.json"))
    evaluate.set_defaults(func=cmd_evaluate)

    leonardo = subparsers.add_parser("leonardo-submit", help="Submit a prepared Slurm job on Leonardo")
    leonardo.add_argument("--job", choices=tuple(LEONARDO_JOB_SCRIPTS), required=True)
    leonardo.add_argument("--env-file", type=Path)
    leonardo.add_argument("--print-only", action="store_true")
    leonardo.set_defaults(func=cmd_leonardo_submit)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
