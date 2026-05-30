"""Cluster-scale parallel simulation runner.

Designed for the Leonardo HPC cluster (SLURM), but falls back to local
multiprocessing automatically when running on a laptop. The simulation is
embarrassingly parallel — every journey is independent, so linear speedup
with worker count is expected.

Usage (local multiprocessing):
    python -m coach_sim.run_cluster --runs 5000 --workers 8

Usage (generate SLURM job script for Leonardo):
    python -m coach_sim.run_cluster --generate-slurm --runs 50000 --workers 32

Usage (inside a SLURM job, called by the generated script):
    python -m coach_sim.run_cluster --runs 50000 --workers $SLURM_NTASKS --slurm-task $SLURM_ARRAY_TASK_ID
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

# Worker functions must be importable at the top level for multiprocessing.
from .coach import Coach, CoachConfig
from .detector import Detector
from .metrics import aggregate, per_persona, weighted_from_personas
from .personas import FUNNEL_WEIGHTS, PERSONAS, PersonaBot
from .sim import run_journey


# -
# Worker — runs in a subprocess
# -

def _run_chunk(args: tuple) -> list[dict]:
    """Run a chunk of journeys for one persona and one policy.

    Returns serialisable dicts (not JourneyResult objects) so they cross
    process boundaries safely via pickle.
    """
    persona_id, policy, seed_base, chunk_start, chunk_size = args
    results = []
    for i in range(chunk_start, chunk_start + chunk_size):
        seed = f"{persona_id}:{seed_base}:{i}"
        bot = PersonaBot(PERSONAS[persona_id], random.Random(seed))
        if policy:
            coach = Coach(
                CoachConfig(policy=policy),  # type: ignore[arg-type]
                persona_id=persona_id,
            )
        else:
            coach = None
        r = run_journey(bot, coach=coach, detector=Detector())
        results.append({
            "persona_id":           r.persona_id,
            "policy":               policy or "baseline",
            "converted":            r.converted,
            "advisor_routed":       r.advisor_routed,
            "abandoned":            r.abandoned,
            "terminal_step":        r.terminal_step.value,
            "interventions_shown":  r.interventions_shown,
            "interventions_accepted": r.interventions_accepted,
            "initial_price_eur":    r.initial_price_eur,
            "final_price_eur":      r.final_price_eur,
            "price_delta_eur":      r.price_delta_eur,
        })
    return results


# -
# Parallel runner
# -

def run_parallel(
    n_runs: int,
    n_workers: int,
    policies: list[str],
    seed: int,
    out: Path,
    verbose: bool = True,
    use_threads: bool = False,
) -> dict[str, list[dict]]:
    """Run baseline + all policies in parallel. Returns results by policy key.

    use_threads=True  — ThreadPoolExecutor (safe inside Streamlit / Windows spawn)
    use_threads=False — ProcessPoolExecutor (default for CLI; true parallelism on cluster)
    """
    chunk_size = max(1, n_runs // max(n_workers, 1))
    tasks: list[tuple] = []

    all_policies = [None] + policies  # None = baseline
    for persona_id in PERSONAS:
        for policy in all_policies:
            start = 0
            while start < n_runs:
                size = min(chunk_size, n_runs - start)
                tasks.append((persona_id, policy, seed, start, size))
                start += size

    total_journeys = len(PERSONAS) * len(all_policies) * n_runs
    if verbose:
        executor_name = "threads" if use_threads else "processes"
        print(f"Workers: {n_workers} ({executor_name})  |  Tasks: {len(tasks)}  |  "
              f"Total journeys: {total_journeys:,}")
        print()

    t0 = time.time()
    all_rows: list[dict] = []

    Executor = ThreadPoolExecutor if use_threads else ProcessPoolExecutor
    with Executor(max_workers=n_workers) as ex:
        futures = {ex.submit(_run_chunk, t): t for t in tasks}
        done = 0
        for fut in as_completed(futures):
            all_rows.extend(fut.result())
            done += 1
            if verbose and done % max(1, len(tasks) // 20) == 0:
                pct = done / len(tasks) * 100
                elapsed = time.time() - t0
                print(f"  {pct:5.1f}%  {done}/{len(tasks)} chunks  "
                      f"elapsed {elapsed:.1f}s")

    elapsed = time.time() - t0
    if verbose:
        print(f"\nDone in {elapsed:.1f}s  ({total_journeys / elapsed:,.0f} journeys/s)")

    # Write raw CSV.
    out.mkdir(parents=True, exist_ok=True)
    raw_path = out / "cluster_raw.csv"
    with raw_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    # Split by policy key.
    by_policy: dict[str, list[dict]] = {}
    for row in all_rows:
        key = row["policy"]
        by_policy.setdefault(key, []).append(row)

    return by_policy


# -
# Metrics from raw dicts (no JourneyResult objects needed)
# -

def _agg_rows(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {}
    conv = sum(1 for r in rows if r["converted"]) / n
    adv  = sum(1 for r in rows if r["advisor_routed"]) / n
    abn  = sum(1 for r in rows if r["abandoned"]) / n
    shown = sum(r["interventions_shown"] for r in rows)
    acc   = sum(r["interventions_accepted"] for r in rows)
    prec  = (acc / shown) if shown else 0.0
    ann   = 1 - prec if shown else 0.0
    return {
        "n": n,
        "conversion": round(conv * 100, 2),
        "advisor":    round(adv * 100, 2),
        "abandoned":  round(abn * 100, 2),
        "trigger_precision": round(prec * 100, 2),
        "annoyance":  round(ann * 100, 2),
    }


def _weighted_conv(rows: list[dict]) -> float:
    """Weighted conversion using FUNNEL_WEIGHTS."""
    by_persona: dict[str, list[dict]] = {}
    for r in rows:
        by_persona.setdefault(r["persona_id"], []).append(r)
    total = 0.0
    for pid, weight in FUNNEL_WEIGHTS.items():
        pr = by_persona.get(pid, [])
        if pr:
            total += weight * sum(1 for r in pr if r["converted"]) / len(pr)
    return round(total * 100, 2)


# -
# SLURM script generator
# -

def generate_slurm(
    n_runs: int,
    n_workers: int,
    out_dir: str,
    account: str = "YOUR_ACCOUNT",
    username: str = "YOUR_USERNAME",
    email: str = "YOUR_EMAIL@example.com",
    partition: str = "g100_usr_prod",
    time_limit: str = "02:00:00",
) -> str:
    """Return a SLURM job script string for the Leonardo cluster."""
    lines = [
        "#!/bin/bash",
        "#",
        f"# Leonardo HPC cluster — UNIQA Conversion Coach simulation",
        f"# User:    {username}",
        f"# Account: {account}",
        "#",
        f"# How to use:",
        f"#   1. SSH into Leonardo:  ssh {username}@login.leonardo.cineca.it",
        f"#   2. Upload project:     scp -r . {username}@login.leonardo.cineca.it:~/4Thrives-Track-2/",
        f"#   3. Submit job:         sbatch cluster_job.sh",
        f"#   4. Monitor:            squeue -u {username}",
        f"#   5. Results:            ls {out_dir}/",
        "#",
        f"#SBATCH --job-name=uniqa-coach-sim",
        f"#SBATCH --account={account}",
        f"#SBATCH --partition={partition}",
        f"#SBATCH --nodes=1",
        f"#SBATCH --ntasks-per-node={n_workers}",
        f"#SBATCH --cpus-per-task=1",
        f"#SBATCH --time={time_limit}",
        f"#SBATCH --output=logs/cluster_%j.out",
        f"#SBATCH --error=logs/cluster_%j.err",
        f"#SBATCH --mail-type=BEGIN,END,FAIL",
        f"#SBATCH --mail-user={email}",
        "",
        "# Environment setup",
        "module load python/3.11",
        "source venv/bin/activate   # or: conda activate your_env",
        "",
        "cd $SLURM_SUBMIT_DIR",
        f"mkdir -p logs {out_dir}",
        "",
        'echo "=============================="',
        f'echo "Job $SLURM_JOB_ID | User: {username}"',
        'echo "Node: $(hostname) | Cores: $SLURM_NTASKS"',
        f'echo "Runs per persona: {n_runs} | Workers: {n_workers}"',
        'echo "=============================="',
        "",
        "# Run simulation",
        "python -m coach_sim.run_cluster \\",
        f"    --runs {n_runs} \\",
        f"    --workers {n_workers} \\",
        f"    --out {out_dir} \\",
        "    --seed 42",
        "",
        'echo "Job $SLURM_JOB_ID finished — results in ' + out_dir + '"',
    ]
    return "\n".join(lines) + "\n"


# -
# CLI entry point
# -

def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Cluster-scale parallel simulation (local or Leonardo/SLURM)"
    )
    parser.add_argument("--runs", type=int, default=5000,
                        help="Journeys per persona (default 5000)")
    parser.add_argument("--workers", type=int,
                        default=min(8, multiprocessing.cpu_count()),
                        help="Parallel workers (default: CPU count, max 8)")
    parser.add_argument("--policies", default="balanced,minimal,aggressive",
                        help="Comma-separated policies to test")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="coach_sim/results/cluster",
                        help="Output directory")
    parser.add_argument("--generate-slurm", action="store_true",
                        help="Print a SLURM job script and exit")
    parser.add_argument("--slurm-account",   default="YOUR_ACCOUNT")
    parser.add_argument("--slurm-username",  default="YOUR_USERNAME")
    parser.add_argument("--slurm-email",     default="YOUR_EMAIL@example.com")
    parser.add_argument("--slurm-partition", default="g100_usr_prod")
    parser.add_argument("--slurm-time",      default="02:00:00")
    parsed = parser.parse_args(args)

    out = Path(parsed.out)
    policies = [p.strip() for p in parsed.policies.split(",") if p.strip()]

    # - Generate SLURM script -
    if parsed.generate_slurm:
        script = generate_slurm(
            n_runs=parsed.runs,
            n_workers=parsed.workers,
            out_dir=parsed.out,
            account=parsed.slurm_account,
            username=parsed.slurm_username,
            email=parsed.slurm_email,
            partition=parsed.slurm_partition,
            time_limit=parsed.slurm_time,
        )
        slurm_path = Path("cluster_job.sh")
        slurm_path.write_text(script, encoding="utf-8")
        print(script)
        print(f"\nSLURM script written to: {slurm_path}")
        print("Submit with:  sbatch cluster_job.sh")
        return

    # - Run parallel simulation -
    print("=" * 70)
    print("UNIQA Conversion Coach — Cluster-scale Simulation")
    print("=" * 70)
    print(f"Runs per persona : {parsed.runs:,}")
    print(f"Personas         : {', '.join(PERSONAS)}")
    print(f"Policies         : baseline + {', '.join(policies)}")
    print(f"Workers          : {parsed.workers}")
    print(f"Total journeys   : {len(PERSONAS) * (1 + len(policies)) * parsed.runs:,}")
    print(f"Output           : {out}")
    print()

    by_policy = run_parallel(
        n_runs=parsed.runs,
        n_workers=parsed.workers,
        policies=policies,
        seed=parsed.seed,
        out=out,
    )

    # - Aggregate & report -
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\n{'Policy':<18} {'Conv (weighted)':>16} {'Conv (raw)':>11} "
          f"{'Advisor':>8} {'Trigger prec':>13} {'Annoyance':>10}")
    print("-" * 80)

    summary_rows = []
    for key in ["baseline"] + policies:
        rows = by_policy.get(key, [])
        if not rows:
            continue
        agg = _agg_rows(rows)
        wconv = _weighted_conv(rows)
        print(f"{key:<18} {wconv:>15.2f}%  {agg['conversion']:>10.2f}%  "
              f"{agg['advisor']:>7.2f}%  {agg['trigger_precision']:>12.2f}%  "
              f"{agg['annoyance']:>9.2f}%")
        summary_rows.append({"policy": key, "conversion_weighted": wconv, **agg})

    # Per-persona breakdown for the balanced policy.
    balanced_rows = by_policy.get("balanced", [])
    if balanced_rows:
        print()
        print("Per-persona conversion (balanced policy):")
        by_pid: dict[str, list[dict]] = {}
        for r in balanced_rows:
            by_pid.setdefault(r["persona_id"], []).append(r)
        base_by_pid: dict[str, list[dict]] = {}
        for r in by_policy.get("baseline", []):
            base_by_pid.setdefault(r["persona_id"], []).append(r)
        print(f"  {'Persona':<10} {'Share':>6} {'Baseline':>10} {'Coached':>9} {'Uplift':>8}")
        print("  " + "-" * 48)
        for pid in PERSONAS:
            w = FUNNEL_WEIGHTS[pid]
            b_conv = (sum(1 for r in base_by_pid.get(pid, []) if r["converted"])
                      / max(1, len(base_by_pid.get(pid, [])))) * 100
            c_conv = (sum(1 for r in by_pid.get(pid, []) if r["converted"])
                      / max(1, len(by_pid.get(pid, [])))) * 100
            print(f"  {pid:<10} {w*100:>5.0f}%  {b_conv:>9.2f}%  "
                  f"{c_conv:>8.2f}%  {c_conv-b_conv:>+7.2f} pp")

    # Save summary JSON.
    summary_path = out / "cluster_summary.json"
    summary_path.write_text(json.dumps(summary_rows, indent=2))
    print(f"\nRaw CSV    -> {out / 'cluster_raw.csv'}")
    print(f"Summary    -> {summary_path}")


if __name__ == "__main__":
    # Required on Windows to avoid spawning subprocesses recursively.
    multiprocessing.freeze_support()
    main()
