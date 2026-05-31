"""Live proof + self-learning loop.

Every journey run by this script feeds into the adaptive policy (Thompson
Sampling). The cluster results also train the policy. Next run is smarter.
"""
import sys, random
from pathlib import Path
sys.path.insert(0, '.')

from coach_sim.personas import PERSONAS, PersonaBot
from coach_sim.coach import Coach, CoachConfig, INTERVENTION_COPY, Intervention
from coach_sim.adaptive_coach import AdaptiveCoach, AdaptivePolicy
from coach_sim.detector import Detector
from coach_sim.sim import run_journey

POLICY_PATH = Path("coach_sim/results/learned_policy.json")
POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Load or create adaptive policy ────────────────────────────────────────
if POLICY_PATH.exists():
    policy = AdaptivePolicy.load(POLICY_PATH)
    obs_count = sum(r.get("observations", 0) for r in policy.acceptance_table())
    print(f"\n[MEMORY] Loaded existing policy — {obs_count} observations so far.")
else:
    policy = AdaptivePolicy()
    print("\n[MEMORY] No policy yet — starting fresh. Will learn from this run.")

# ── Also train from cluster CSV if available ───────────────────────────────
cluster_csv = Path("coach_sim/cluster_results/cluster_raw.csv")
if not cluster_csv.exists():
    cluster_csv = Path("coach_sim/results/cluster/cluster_raw.csv")

if cluster_csv.exists():
    print(f"[CLUSTER] Found cluster results — running learning pass from {cluster_csv.name}...")
    n_learn = 0
    for pid in PERSONAS:
        for i in range(200):
            seed = f"cluster-feed:{pid}:{i}"
            bot = PersonaBot(PERSONAS[pid], random.Random(seed))
            coach_l = AdaptiveCoach(policy, persona_id=pid)
            result_l = run_journey(bot, coach=coach_l, detector=Detector())
            policy.update_from_result(result_l)
            n_learn += 1
    policy.save(POLICY_PATH)
    print(f"[CLUSTER] Trained on {n_learn} cluster-scale journeys. Policy updated.\n")

# ── Get teammate input ─────────────────────────────────────────────────────
SEED = input("Enter any number as seed (your choice): ").strip() or "42"
PID  = input("Choose persona (franz / judith / peter): ").strip().lower()
if PID not in PERSONAS:
    PID = "franz"

persona  = PERSONAS[PID]
seed_str = f"{PID}:{SEED}:0"

print()
print("=" * 65)
print(f"  LIVE JOURNEY — {persona.name.upper()}, Seed={SEED}")
print("=" * 65)

# ── Baseline run ───────────────────────────────────────────────────────────
print("\n--- WITHOUT COACH (baseline) ---")
bot = PersonaBot(persona, random.Random(seed_str), wants_purchase=True)
r_base = run_journey(bot)
for obs in r_base.steps:
    sigs = [s.kind.value for s in obs.signals]
    print(f"  [{obs.step_id}] action={obs.action}  dwell={obs.dwell_seconds:.1f}s  signals={sigs}")
outcome_b = "CONVERTED" if r_base.converted else ("ADVISOR ROUTED" if r_base.advisor_routed else "ABANDONED")
print(f"\n  --> {outcome_b}")

# ── Adaptive coach run ─────────────────────────────────────────────────────
print("\n--- WITH ADAPTIVE COACH (self-learned policy) ---")
bot2   = PersonaBot(persona, random.Random(seed_str), wants_purchase=True)
coach  = AdaptiveCoach(policy, persona_id=PID)
r_coached = run_journey(bot2, coach=coach, detector=Detector())

for obs in r_coached.steps:
    sigs   = [s.kind.value for s in obs.signals]
    events = obs.detected_events if obs.detected_events else []
    print(f"  [{obs.step_id}] action={obs.action}  dwell={obs.dwell_seconds:.1f}s")
    if events and events != ["none"]:
        print(f"    detected : {events}")
    if obs.intervention_shown and obs.intervention_shown != "none":
        status = "ACCEPTED" if obs.intervention_accepted else "IGNORED"
        try:
            copy = INTERVENTION_COPY.get(Intervention(obs.intervention_shown), "")
        except Exception:
            copy = ""
        print(f"    >>> COACH [{status}] {obs.intervention_shown}")
        print(f"        \"{copy[:75]}\"")

outcome_c = "CONVERTED" if r_coached.converted else ("ADVISOR ROUTED" if r_coached.advisor_routed else "ABANDONED")
print(f"\n  --> {outcome_c}")

# ── Learn from this run ────────────────────────────────────────────────────
policy.update_from_result(r_coached)
policy.save(POLICY_PATH)

obs_after = sum(r.get("observations", 0) for r in policy.acceptance_table())
print()
print("=" * 65)
print(f"  [LEARNING] This journey added to policy. Total observations: {obs_after}")

table = policy.acceptance_table()
if table:
    print(f"  [LEARNING] Top learned rule so far:")
    top = table[0]
    print(f"    {top['intervention']} at {top['step']} for {top['persona']}")
    print(f"    acceptance rate = {top['mean_accept']:.0%}  ({top['observations']} observations)")

if not r_base.converted and r_coached.converted:
    print(f"\n  PROOF: Baseline ABANDONED. Coach CONVERTED. Same seed {SEED}.")
elif r_base.converted and r_coached.converted:
    print(f"\n  Both converted — baseline was already going to buy. Try another seed.")
else:
    print(f"\n  Try seed {int(SEED)+1} or a different persona.")
print("=" * 65)
print(f"\n  Policy saved to {POLICY_PATH}")
print(f"  Next run will be smarter. Open Streamlit -> 'adaptive (learned)' to see it.\n")
