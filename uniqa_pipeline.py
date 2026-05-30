from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib import error, request

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
    "validate-vllm": ROOT / "leonardo" / "slurm_validate_live_vllm.sh",
    "bulk": ROOT / "leonardo" / "slurm_bulk_live.sh",
    "bulk-vllm": ROOT / "leonardo" / "slurm_bulk_live_vllm.sh",
    "build-datasets": ROOT / "leonardo" / "slurm_build_datasets.sh",
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


def _healthcheck(url: str, *, timeout_s: float = 5.0) -> bool:
    try:
        with request.urlopen(url, timeout=timeout_s) as response:
            return 200 <= getattr(response, "status", 500) < 300
    except (error.URLError, TimeoutError, OSError, ValueError):
        return False


def _total_failures(summary: dict[str, object]) -> int:
    failures = summary.get("failures", {})
    if not isinstance(failures, dict):
        return 0
    return sum(int(value) for value in failures.values())


def _ensure_local_live_prereqs() -> None:
    if not os.getenv("FEATHERLESS_API_KEY"):
        raise RuntimeError("FEATHERLESS_API_KEY must be set for local live runs that use Featherless")


def _ensure_local_coach_prereqs() -> None:
    _ensure_local_live_prereqs()
    extension_dist = os.getenv("EXTENSION_DIST")
    if extension_dist and not Path(extension_dist).expanduser().exists():
        raise RuntimeError(f"EXTENSION_DIST does not exist: {extension_dist}")
    if not (ROOT / "extension" / "dist").exists() and not extension_dist:
        raise RuntimeError("Build the extension first with `npm run build:extension`, or set EXTENSION_DIST to an existing build")
    coach_api_url = os.getenv("COACH_API_URL", "http://127.0.0.1:8787").rstrip("/")
    if not _healthcheck(f"{coach_api_url}/healthz"):
        raise RuntimeError(f"Coach API health check failed at {coach_api_url}/healthz")


def _assert_validation_gate(name: str, summary: dict[str, object], expected_sessions: int) -> None:
    traces = summary.get("traces", [])
    completed = len(traces) if isinstance(traces, list) else 0
    total_failures = _total_failures(summary)
    if summary.get("circuit_breaker") or total_failures or completed < expected_sessions:
        raise RuntimeError(
            json.dumps(
                {
                    "gate": name,
                    "expected_sessions": expected_sessions,
                    "completed_sessions": completed,
                    "failures": summary.get("failures", {}),
                    "failure_log": summary.get("failure_log", []),
                    "circuit_breaker": summary.get("circuit_breaker"),
                },
                indent=2,
                sort_keys=True,
            )
        )


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


def cmd_local_full_loop(args: argparse.Namespace) -> dict[str, object]:
    _ensure_local_live_prereqs()
    artifacts_root = args.artifacts_root
    traces_dir = args.output_dir or artifacts_root / "browser-runs" / args.experiment_prefix
    datasets_dir = artifacts_root / "datasets" / args.experiment_prefix
    training_dir = artifacts_root / "training" / args.experiment_prefix
    evaluation_dir = artifacts_root / "evaluation-experiments" / args.experiment_prefix
    user_dataset = datasets_dir / "user-policy.jsonl"
    coach_dataset = datasets_dir / "coach-ranking.jsonl"
    user_model = training_dir / "user-policy.json"
    coach_model = training_dir / "frequency-ranker.json"

    baseline_validation = _run_live_batch(
        execution_mode="baseline",
        runner_mode="validation",
        experiment_id=f"{args.experiment_prefix}-validate-baseline",
        sessions=args.validate_sessions,
        output_dir=traces_dir,
    )
    _assert_validation_gate("baseline_validation", baseline_validation, args.validate_sessions)

    _ensure_local_coach_prereqs()
    coach_validation = _run_live_batch(
        execution_mode="coach",
        runner_mode="validation",
        experiment_id=f"{args.experiment_prefix}-validate-coach",
        sessions=args.validate_sessions,
        output_dir=traces_dir,
    )
    _assert_validation_gate("coach_validation", coach_validation, args.validate_sessions)

    baseline_bulk = _run_live_batch(
        execution_mode="baseline",
        runner_mode="bulk",
        experiment_id=f"{args.experiment_prefix}-baseline",
        sessions=args.bulk_sessions,
        output_dir=traces_dir,
    )
    coach_bulk = _run_live_batch(
        execution_mode="coach",
        runner_mode="bulk",
        experiment_id=f"{args.experiment_prefix}-coach",
        sessions=args.bulk_sessions,
        output_dir=traces_dir,
    )

    datasets_summary = build_live_datasets(
        traces_path=traces_dir,
        user_output=user_dataset,
        coach_output=coach_dataset,
        user_dataset_phase=args.user_dataset_phase,
        coach_dataset_phase=args.coach_dataset_phase,
    )
    user_dataset_rows = [json.loads(line) for line in user_dataset.read_text().splitlines() if line.strip()]
    datasets_summary["user_policy_check"] = check_user_policy_rows(user_dataset_rows)
    datasets_summary["coach_ranking_check"] = check_dataset(load_jsonl(coach_dataset))

    user_training = train_user_policy(user_dataset, user_model)
    user_training["evaluation"] = evaluate_user_policy(user_dataset, user_model)
    coach_training = train_frequency_ranker(coach_dataset, coach_model)
    coach_training["evaluation"] = evaluate_ranker(coach_dataset, coach_model)

    evaluation_summary = None
    if not args.skip_evaluate:
        evaluation_summary = run_experiment(
            experiment_id=f"{args.experiment_prefix}-eval",
            runner_mode=args.evaluation_runner_mode,
            sessions_per_mode=args.evaluation_sessions_per_mode,
            output_root=evaluation_dir,
            evaluation_modes=("baseline", "rule_based", "trainable"),
            trainable_model=coach_model,
        )

    return {
        "experiment_prefix": args.experiment_prefix,
        "paths": {
            "artifacts_root": str(artifacts_root),
            "traces": str(traces_dir),
            "user_dataset": str(user_dataset),
            "coach_dataset": str(coach_dataset),
            "user_model": str(user_model),
            "coach_model": str(coach_model),
            "evaluation_root": str(evaluation_dir),
        },
        "validation": {
            "baseline": baseline_validation,
            "coach": coach_validation,
        },
        "bulk": {
            "baseline": baseline_bulk,
            "coach": coach_bulk,
        },
        "datasets": datasets_summary,
        "training": {
            "user_policy": user_training,
            "coach_ranker": coach_training,
        },
        "evaluation": evaluation_summary,
    }


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
    parser = argparse.ArgumentParser(description="CLI entrypoint for local UNIQA simulation, dataset building, training, evaluation, and optional Leonardo submission")
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

    local_loop = subparsers.add_parser("local-full-loop", help="Run the end-to-end local browser, dataset, training, and evaluation loop")
    local_loop.add_argument("--validate-sessions", type=int, default=12)
    local_loop.add_argument("--bulk-sessions", type=int, default=300)
    local_loop.add_argument("--experiment-prefix", default="local-full-loop")
    local_loop.add_argument("--artifacts-root", type=Path, default=Path("artifacts"))
    local_loop.add_argument("--output-dir", type=Path)
    local_loop.add_argument("--user-dataset-phase", default="behavioral_imitation_live")
    local_loop.add_argument("--coach-dataset-phase", default="coach_ranking_live")
    local_loop.add_argument("--evaluation-runner-mode", choices=("mock", "validation", "bulk"), default="validation")
    local_loop.add_argument("--evaluation-sessions-per-mode", type=int, default=6)
    local_loop.add_argument("--skip-evaluate", action="store_true")
    local_loop.set_defaults(func=cmd_local_full_loop)

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
