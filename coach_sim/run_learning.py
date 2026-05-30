"""Self-improving Coach training loop — persistent across sessions.

Loads an existing learned policy from disk if one exists, then continues
training from where it left off. Saves after every iteration so progress
is never lost even if interrupted.

Usage:
    python -m coach_sim.run_learning                        # continue/start
    python -m coach_sim.run_learning --reset                # discard & restart
    python -m coach_sim.run_learning --iterations 20 --runs 200
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from .adaptive_coach import AdaptiveCoach, AdaptivePolicy
from .detector import Detector
from .metrics import aggregate, per_persona, weighted_from_personas
from .personas import PERSONAS, PersonaBot
from .sim import run_journey

POLICY_FILE = Path("coach_sim/results/learned_policy.json")
CURVE_FILE  = Path("coach_sim/results/learning_curve.csv")


def _load_curve(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _save_curve(curve: list[dict], path: Path) -> None:
    if not curve:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=curve[0].keys())
        writer.writeheader()
        writer.writerows(curve)


def _run_batch(policy: AdaptivePolicy, n_runs: int,
               base_seed: int, global_iter: int) -> list:
    results = []
    for pid in PERSONAS:
        for i in range(n_runs):
            seed = f"{pid}:{base_seed}:{global_iter}:{i}"
            bot = PersonaBot(PERSONAS[pid], random.Random(seed))
            coach = AdaptiveCoach(policy, persona_id=pid)
            result = run_journey(bot, coach=coach, detector=Detector())
            policy.update_from_result(result)
            results.append(result)
    return results


def main(args: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Adaptive Coach learning loop")
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--runs", type=int, default=150,
                        help="Journeys per persona per iteration")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="coach_sim/results")
    parser.add_argument("--reset", action="store_true",
                        help="Discard existing policy and start fresh")
    parsed = parser.parse_args(args)

    out = Path(parsed.out)
    out.mkdir(parents=True, exist_ok=True)
    policy_path = out / "learned_policy.json"
    curve_path  = out / "learning_curve.csv"

    # Load or create policy.
    if parsed.reset and policy_path.exists():
        policy_path.unlink()
        curve_path.unlink(missing_ok=True)
        print("Existing policy discarded — starting fresh.\n")

    if policy_path.exists():
        policy = AdaptivePolicy.load(policy_path)
        prior_curve = _load_curve(curve_path)
        global_iter_start = len(prior_curve)
        total_obs = sum(
            r.get("observations", 0) for r in policy.acceptance_table()
        )
        print(f"Resuming from saved policy "
              f"({global_iter_start} prior iterations, {total_obs} observations).\n")
    else:
        policy = AdaptivePolicy()
        prior_curve = []
        global_iter_start = 0
        print("No existing policy found — starting fresh.\n")

    print(f"{'Iter':>5}  {'Conv (weighted)':>16}  {'Trigger prec':>13}  "
          f"{'Annoyance':>10}  {'Top learned rule'}")
    print("-" * 90)

    new_curve: list[dict] = []
    for local_it in range(parsed.iterations):
        global_it = global_iter_start + local_it
        results = _run_batch(policy, parsed.runs, parsed.seed, global_it)
        agg = weighted_from_personas(per_persona(results))
        raw = aggregate(results)

        table = policy.acceptance_table()
        top = table[0] if table else {}
        top_str = (
            f"{top.get('intervention','')} @ {top.get('step','')} "
            f"[{top.get('persona','')}] "
            f"acc={top.get('mean_accept', 0):.2f} n={top.get('observations', 0)}"
            if top else "-"
        )

        conv_pct = agg.conversion_rate * 100
        prec_pct = (raw.trigger_precision or 0) * 100
        ann_pct  = (raw.annoyance_rate or 0) * 100
        total_obs = sum(r.get("observations", 0) for r in table)

        print(f"{global_it + 1:>5}  {conv_pct:>15.1f}%  "
              f"{prec_pct:>12.1f}%  {ann_pct:>9.1f}%  {top_str}")

        new_curve.append({
            "iteration": global_it + 1,
            "conversion_weighted": round(conv_pct, 2),
            "trigger_precision": round(prec_pct, 2),
            "annoyance_rate": round(ann_pct, 2),
            "observations": total_obs,
        })

        # Save after every iteration — progress survives interruptions.
        policy.save(policy_path)
        _save_curve(prior_curve + new_curve, curve_path)

    print()
    print(f"Policy saved  -> {policy_path}")
    print(f"Curve saved   -> {curve_path}")
    print()
    print("Top learned intervention rules:")
    print(f"  {'Step':<22} {'Persona':<8} {'Intervention':<25} "
          f"{'Mean accept':>12} {'N obs':>6}")
    print("  " + "-" * 77)
    for row in policy.acceptance_table()[:10]:
        print(f"  {row['step']:<22} {row['persona']:<8} "
              f"{row['intervention']:<25} "
              f"{row['mean_accept']:>12.3f} {row['observations']:>6}")


if __name__ == "__main__":
    main()
