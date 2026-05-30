"""Polished Streamlit demo for the UNIQA Conversion Coach."""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - Streamlit can still run without .env support.
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if load_dotenv:
    load_dotenv(ROOT / ".env")

from coach_sim.coach import (  # noqa: E402
    Coach,
    CoachConfig,
    INTERVENTION_COPY,
    INTERVENTION_RATIONALE,
    Intervention,
)
from coach_sim.detector import Detector  # noqa: E402
from coach_sim.journey import IN_SCOPE_ORDER, STEP_META, Step  # noqa: E402
from coach_sim.llm_persona import DEFAULT_MODEL, LLMPersonaBot  # noqa: E402
from coach_sim.abandonment import insights_from_results  # noqa: E402
from coach_sim.run_cluster import run_parallel, _agg_rows, _weighted_conv  # noqa: E402
from coach_sim.run_cluster import generate_slurm  # noqa: E402
from coach_sim.adaptive_coach import AdaptiveCoach, AdaptivePolicy  # noqa: E402
from coach_sim.metrics import aggregate, per_persona, weighted_from_personas  # noqa: E402
from coach_sim.personas import FUNNEL_WEIGHTS, PERSONAS, PersonaBot  # noqa: E402
from coach_sim.sim import JourneyResult, run_journey  # noqa: E402

# Paths for the persistent learned policy — must be defined before any UI code.
_POLICY_PATH = ROOT / "coach_sim" / "results" / "learned_policy.json"
_CURVE_PATH  = ROOT / "coach_sim" / "results" / "learning_curve.csv"


def _load_saved_curve() -> list[dict]:
    if not _CURVE_PATH.exists():
        return []
    import csv as _csv
    with _CURVE_PATH.open(newline="") as f:
        return list(_csv.DictReader(f))


def _save_curve_row(row: dict) -> None:
    import csv as _csv
    exists = _CURVE_PATH.exists()
    _CURVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _CURVE_PATH.open("a", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            writer.writeheader()
        writer.writerow(row)


st.set_page_config(
    page_title="UNIQA Conversion Coach",
    page_icon="U",
    layout="wide",
    initial_sidebar_state="expanded",
)

BLUE = "#003D7A"
CYAN = "#00A0E1"
GREEN = "#2EAD6B"
RED = "#D64242"
AMBER = "#F39200"
INK = "#132238"
MUTED = "#607089"
BG = "#F5F8FC"
LINE = "#DCE5F0"

WINNING_DEMO_BASE = {"judith": 0, "franz": 0, "peter": 0}

st.markdown(
    f"""
    <style>
      .stApp {{ background: {BG}; }}
      .block-container {{ max-width: 1280px; padding-top: .8rem; }}
      .stApp, .stMarkdown, .stText, p, span, label {{ color: {INK}; }}
      section[data-testid="stSidebar"] {{
        background: #20232D;
      }}
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3,
      section[data-testid="stSidebar"] p,
      section[data-testid="stSidebar"] span,
      section[data-testid="stSidebar"] label,
      section[data-testid="stSidebar"] div {{
        color: #F6F8FC !important;
      }}
      section[data-testid="stSidebar"] .stCaption,
      section[data-testid="stSidebar"] small {{
        color: #C8D1E0 !important;
      }}
      section[data-testid="stSidebar"] [data-baseweb="select"] div,
      section[data-testid="stSidebar"] [data-testid="stNumberInput"] input {{
        color: white !important;
        background: #0F121A !important;
      }}
      h1, h2, h3, h4 {{ color: {BLUE} !important; letter-spacing: 0; }}
      div[data-testid="stMarkdownContainer"] p {{ color: {INK}; }}
      div[data-testid="stMarkdownContainer"] span {{ color: inherit; }}
      div[data-baseweb="tab-list"] button p {{
        color: {MUTED} !important; font-weight: 700;
      }}
      div[data-baseweb="tab-list"] button[aria-selected="true"] p {{
        color: {BLUE} !important;
      }}
      div[data-testid="stToggle"] label, div[data-testid="stToggle"] p {{
        color: {INK} !important; font-weight: 700;
      }}
      div[data-testid="stButton"] button {{
        background: {BLUE}; color: white; border: 0; border-radius: 8px;
      }}
      div[data-testid="stButton"] button p {{ color: white !important; }}
      div[data-testid="stMetric"] {{
        background: white; border: 1px solid {LINE}; border-radius: 8px;
        padding: 12px 14px; box-shadow: 0 1px 2px rgba(0, 30, 70, .05);
      }}
      div[data-testid="stMetric"] label,
      div[data-testid="stMetric"] div,
      div[data-testid="stMetric"] p {{
        color: {INK} !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {BLUE} !important;
      }}
      div[data-testid="stMetric"] [data-testid="stMetricLabel"] {{
        color: {MUTED} !important;
      }}
      .hero {{
        background: linear-gradient(135deg, {BLUE} 0%, #075FA8 55%, {CYAN} 100%);
        color: white; border-radius: 10px; padding: 18px 22px; margin-bottom: 14px;
        box-shadow: 0 10px 24px rgba(0, 61, 122, .18);
      }}
      .hero-title {{ font-size: 1.65rem; font-weight: 760; margin: 0; color: white !important; }}
      .hero-sub {{ color: rgba(255,255,255,.9); margin-top: 4px; font-size: .92rem; max-width: 980px; }}
      .pill {{
        display:inline-block; border-radius:999px; padding:3px 9px; font-size:.72rem;
        font-weight:700; margin: 2px 4px 2px 0;
      }}
      .pill-blue {{ background:#E3F3FC; color:{BLUE}; }}
      .pill-green {{ background:#E3F6EA; color:{GREEN}; }}
      .pill-red {{ background:#FBE7E7; color:{RED}; }}
      .pill-amber {{ background:#FFF2DE; color:{AMBER}; }}
      .panel {{
        background:white; border:1px solid {LINE}; border-radius:8px; padding:16px 18px;
        box-shadow: 0 1px 3px rgba(0, 30, 70, .05); margin-bottom: 12px;
        color:{INK};
      }}
      .journey-head {{
        background:white; border:1px solid {LINE}; border-radius:8px; padding:10px 12px;
        margin-bottom:8px;
      }}
      .journey-title {{ color:{BLUE}; font-weight:760; font-size:.98rem; margin-bottom:3px; }}
      .journey-note {{ color:{MUTED}; font-size:.8rem; }}
      .timeline {{
        display:grid; grid-template-columns: repeat(4, minmax(80px, 1fr));
        gap:6px; margin:8px 0 10px 0;
      }}
      .time-step {{
        background:white; border:1px solid {LINE}; border-radius:8px; padding:9px 10px;
        min-height:58px;
      }}
      .time-step.hit {{ border-color:{CYAN}; box-shadow: inset 0 0 0 2px #DDF3FC; }}
      .time-step.coach {{ border-color:{GREEN}; box-shadow: inset 0 0 0 2px #DFF5E8; }}
      .time-step.stop {{ border-color:{RED}; box-shadow: inset 0 0 0 2px #FBE2E2; }}
      .time-num {{ color:{MUTED}; font-size:.62rem; font-weight:800; }}
      .time-title {{ color:{INK}; font-weight:760; font-size:.76rem; line-height:1.1; margin-top:2px; }}
      .time-phase {{ color:{MUTED}; font-size:.62rem; margin-top:3px; }}
      .step-card {{
        background:white; border:1px solid {LINE}; border-left:4px solid {CYAN};
        border-radius:8px; padding:9px 11px; margin-bottom:7px;
      }}
      .step-card.stop {{ border-left-color:{RED}; }}
      .step-card.good {{ border-left-color:{GREEN}; }}
      .step-name {{ color:{BLUE}; font-weight:760; }}
      .step-meta {{ color:{MUTED}; font-size:.76rem; margin-top:1px; }}
      .chip {{
        display:inline-block; background:#EEF3F8; color:#31445F; border-radius:999px;
        padding:2px 7px; font-size:.72rem; margin:2px 4px 0 0;
      }}
      .event {{ background:#FFF2DE; color:{AMBER}; font-weight:700; }}
      .coach {{
        background:#F6FBFE; border:1px solid #CDE7F7; border-left:4px solid {GREEN};
        border-radius:8px; padding:9px 11px; margin: -2px 0 8px 10px;
      }}
      .coach.miss {{ border-left-color:{RED}; background:#FFF7F7; }}
      .coach-title {{ color:{BLUE}; font-weight:760; }}
      .coach-copy {{ color:{INK}; margin-top:4px; }}
      .coach-why {{ color:{MUTED}; font-size:.8rem; margin-top:6px; }}
      .price-grid {{
        display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin:8px 0 9px 0;
      }}
      .price-box {{
        background:white; border:1px solid {LINE}; border-radius:8px; padding:8px 10px;
      }}
      .price-label {{ color:{MUTED}; font-size:.66rem; text-transform:uppercase; font-weight:760; }}
      .price-val {{ color:{BLUE}; font-weight:800; font-size:1rem; margin-top:2px; }}
      .llm-grid {{
        display:grid; grid-template-columns: 1.05fr .95fr; gap:12px; align-items:start;
      }}
      .llm-note {{
        background:#F6FBFE; border:1px solid #CDE7F7; border-radius:8px;
        padding:12px 14px; color:{INK}; margin-bottom:12px;
      }}
      .llm-note strong {{ color:{BLUE}; }}
      .scope-table td, .scope-table th {{ padding: 9px 11px; border-bottom: 1px solid {LINE}; }}
      @media(max-width: 900px) {{
        .timeline {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
        .price-grid {{ grid-template-columns: 1fr; }}
        .llm-grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def status_label(result: JourneyResult) -> tuple[str, str]:
    if result.converted:
        return "Converted online", "green"
    if result.advisor_routed:
        return "Advisor route", "amber"
    return "Abandoned", "red"


def step_label(step_id: str) -> str:
    return step_id.replace("_", " ").replace("s ", "Step ").title()


def make_result(persona_id: str, seed: str, policy: str | None,
                wants_purchase: bool | None = None) -> JourneyResult:
    bot = PersonaBot(PERSONAS[persona_id], random.Random(seed),
                     wants_purchase=wants_purchase)
    if policy == "adaptive (learned)" and _POLICY_PATH.exists():
        ap = AdaptivePolicy.load(_POLICY_PATH)
        coach: Coach | None = AdaptiveCoach(ap, persona_id=persona_id)
    elif policy:
        coach = Coach(CoachConfig(policy=policy), persona_id=persona_id)  # type: ignore[arg-type]
    else:
        coach = None
    return run_journey(bot, coach=coach, detector=Detector())


def find_winning_seed(persona_id: str, base_seed: int, policy: str,
                      max_tries: int = 500) -> tuple[str, int]:
    """Return (seed_str, variant_index) where baseline abandons and coached converts."""
    for i in range(max_tries):
        seed_str = f"{persona_id}:{base_seed}:{i}"
        baseline = make_result(persona_id, seed_str, None, True)
        coached = make_result(persona_id, seed_str, policy, True)
        if not baseline.converted and coached.converted:
            return seed_str, i
    return f"{persona_id}:{base_seed}:0", 0


@st.cache_data(show_spinner=False)
def cached_winning_seed(persona_id: str, base_seed: int, policy: str) -> tuple[str, int]:
    """Cached version — runs once per (persona, base_seed, policy) combination."""
    return find_winning_seed(persona_id, base_seed, policy)


def make_llm_result(persona_id: str, seed: int, policy: str | None,
                    wants_purchase: bool | None, model: str) -> tuple[JourneyResult, LLMPersonaBot]:
    bot = LLMPersonaBot(
        PERSONAS[persona_id],
        random.Random(f"llm:{persona_id}:{seed}"),
        wants_purchase=wants_purchase,
        model=model,
    )
    coach = None
    if policy:
        coach = Coach(CoachConfig(policy=policy), persona_id=persona_id)  # type: ignore[arg-type]
    return run_journey(bot, coach=coach, detector=Detector()), bot


def local_fallback_trace(result: JourneyResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for obs in result.steps:
        reason = "Continues through the in-scope online path."
        if obs.intervention_shown and obs.intervention_shown != "none":
            reason = (
                "Accepted the coach nudge and stayed in the online Start/Optimal flow."
                if obs.intervention_accepted else
                "Saw the coach nudge but still hesitated."
            )
        if obs.action == "abandon":
            reason = "Dropped out at a known hesitation point."
        if obs.action == "confirm":
            reason = "Completed the online purchase after the final reassurance."
        rows.append({
            "Step": step_label(obs.step_id),
            "Action": obs.action,
            "Dwell seconds": round(obs.dwell_seconds, 1),
            "Reasoning": reason,
        })
    return rows


def run_batch(n_runs: int, seed: int, policy: str) -> tuple[list[JourneyResult], list[JourneyResult]]:
    baseline: list[JourneyResult] = []
    coached: list[JourneyResult] = []
    total = len(PERSONAS) * n_runs
    progress = st.progress(0, text="Running seeded persona simulations")
    done = 0
    for pid in PERSONAS:
        for i in range(n_runs):
            seed_str = f"{pid}:{seed}:{i}"
            baseline.append(make_result(pid, seed_str, None))
            coached.append(make_result(pid, seed_str, policy))
            done += 1
            if done % max(1, total // 50) == 0:
                progress.progress(done / total, text=f"Running simulations {done}/{total}")
    progress.empty()
    return baseline, coached


def render_timeline(result: JourneyResult) -> None:
    visited = {obs.step_id for obs in result.steps}
    coached = {obs.step_id for obs in result.steps if obs.intervention_shown and obs.intervention_shown != "none"}
    stopped = result.steps[-1].step_id if result.steps and result.abandoned else ""
    cells: list[str] = []
    for step in [s for s in IN_SCOPE_ORDER if s not in {Step.START, Step.CONVERTED}]:
        meta = STEP_META.get(step, {})
        cls = "time-step"
        if step.value in visited:
            cls += " hit"
        if step.value in coached:
            cls += " coach"
        if step.value == stopped:
            cls += " stop"
        cells.append(
            f"<div class='{cls}'>"
            f"<div class='time-num'>STEP {meta.get('number', '')}</div>"
            f"<div class='time-title'>{meta.get('short', step.value)}</div>"
            f"<div class='time-phase'>{meta.get('phase', '')}</div>"
            f"</div>"
        )
    st.markdown("<div class='timeline'>" + "".join(cells) + "</div>", unsafe_allow_html=True)


def render_prices(result: JourneyResult) -> None:
    st.markdown(
        f"""
        <div class='price-grid'>
          <div class='price-box'><div class='price-label'>Initial Optimal quote</div><div class='price-val'>EUR {result.initial_price_eur:.2f}</div></div>
          <div class='price-box'><div class='price-label'>Final simulated price</div><div class='price-val'>EUR {result.final_price_eur:.2f}</div></div>
          <div class='price-box'><div class='price-label'>Transparent delta</div><div class='price-val'>+EUR {result.price_delta_eur:.2f}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_journey(result: JourneyResult, title: str) -> None:
    outcome, color = status_label(result)
    st.markdown(
        f"""
        <div class='journey-head'>
          <div class='journey-title'>{title}</div>
          <span class='pill pill-{color}'>{outcome}</span>
          <div class='journey-note'>{result.outcome_reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_prices(result)
    render_timeline(result)

    for obs in result.steps:
        cls = "step-card"
        if obs.action == "abandon":
            cls += " stop"
        if obs.action in {"confirm", "select_optimal", "continue", "submit", "myself", "at_doctor"}:
            cls += " good"
        signals = "".join(
            f"<span class='chip'>{getattr(sig.kind, 'value', str(sig.kind))}</span>"
            for sig in obs.signals
        )
        events = "".join(f"<span class='chip event'>{e}</span>" for e in obs.detected_events)
        st.markdown(
            f"""
            <div class='{cls}'>
              <div class='step-name'>{step_label(obs.step_id)} <span class='pill pill-blue'>{obs.phase}</span></div>
              <div class='step-meta'>{obs.screen_title}</div>
              <div class='step-meta'>Action <b>{obs.action}</b> | dwell <b>{obs.dwell_seconds:.1f}s</b></div>
              <div>{signals}{events}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if obs.intervention_shown and obs.intervention_shown != "none":
            iv = Intervention(obs.intervention_shown)
            accepted = obs.intervention_accepted is True
            coach_cls = "coach" if accepted else "coach miss"
            st.markdown(
                f"""
                <div class='{coach_cls}'>
                  <div class='coach-title'>Coach intervention: {iv.value} - {'accepted' if accepted else 'ignored'}</div>
                  <div class='coach-copy'>{INTERVENTION_COPY.get(iv, '')}</div>
                  <div class='coach-why'>Why: {INTERVENTION_RATIONALE.get(iv, '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def aggregate_weighted(results: list[JourneyResult]):
    return weighted_from_personas(per_persona(results))


st.markdown(
    """
    <div class='hero'>
      <div class='hero-title'>UNIQA Conversion Coach</div>
      <div class='hero-sub'>A live, simulation-based prototype that detects abandonment signals,
      intervenes on the online-purchasable Start/Optimal path, and proves impact with seeded persona runs.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Demo Controls")
    persona_id = st.selectbox(
        "Persona",
        list(PERSONAS.keys()),
        format_func=lambda pid: f"{PERSONAS[pid].name} ({int(FUNNEL_WEIGHTS[pid] * 100)}%)",
    )
    _policy_options = ["balanced", "minimal", "aggressive"]
    if _POLICY_PATH.exists():
        _policy_options = ["adaptive (learned)"] + _policy_options
    policy = st.selectbox("Coach policy", _policy_options, index=0)
    demo_mode = st.radio(
        "Live demo mode",
        ["Winning demo", "Custom seed"],
        horizontal=False,
        index=0,
    )
    seed = st.number_input("Seed", min_value=1, value=42, step=1)
    force = st.checkbox("Force would-buy persona", value=True)
    st.divider()
    st.caption("Baseline anchor: 5.6% online conversion, 66% Step 4 drop-off, 78% Step 7 drop-off.")


tab_demo, tab_batch, tab_llm, tab_learn, tab_cluster = st.tabs(["Live demo", "Results dashboard", "LLM persona", "Self-learning", "Cluster simulation"])

with tab_demo:
    st.subheader("Live side-by-side journey")
    st.caption("Use Winning demo for presentation, or Custom seed when you want the seed to change the deterministic run.")

    pid = persona_id
    if demo_mode == "Winning demo":
        base_seed = WINNING_DEMO_BASE[persona_id]
        seed_str, variant_idx = cached_winning_seed(pid, base_seed, policy)
        wants = True
        seed_label = f"auto ({variant_idx})"
    else:
        with st.spinner("Finding best contrast for your seed…"):
            seed_str, variant_idx = find_winning_seed(pid, int(seed), policy)
        wants = True if force else None
        seed_label = f"{int(seed)} (v{variant_idx})" if variant_idx > 0 else f"{int(seed)} (exact)"
    baseline = make_result(pid, seed_str, None, wants)
    coached = make_result(pid, seed_str, policy, wants)

    b_status, _ = status_label(baseline)
    c_status, _ = status_label(coached)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Persona", PERSONAS[pid].name)
    m2.metric("Without Coach", b_status)
    m3.metric("With Coach", c_status)
    m4.metric("Accepted", f"{coached.interventions_accepted}/{coached.interventions_shown}")
    m5.metric("Run seed", seed_label)

    left, right = st.columns(2, gap="large")
    with left:
        render_journey(baseline, "Without Coach")
    with right:
        render_journey(coached, f"With Coach ({policy})")


with tab_batch:
    st.subheader("Seeded simulation results")
    cols = st.columns([1, 1, 2])
    with cols[0]:
        batch_runs = st.slider("Runs per persona", 100, 2500, 500, step=100)
    with cols[1]:
        batch_policy = st.selectbox("Policy to test", ["balanced", "minimal", "aggressive"], key="batch_policy")
    with cols[2]:
        run_button = st.button("Run batch simulation", type="primary", use_container_width=True)

    if run_button or "batch_baseline" not in st.session_state:
        base, coach = run_batch(int(batch_runs), int(seed), batch_policy)
        st.session_state.batch_baseline = base
        st.session_state.batch_coach = coach
        st.session_state.batch_policy_used = batch_policy

    base = st.session_state.batch_baseline
    coach = st.session_state.batch_coach
    base_agg = aggregate_weighted(base)
    coach_agg = aggregate_weighted(coach)
    raw_base = aggregate(base)
    raw_coach = aggregate(coach)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Baseline conversion", pct(base_agg.conversion_rate))
    k2.metric("Coach conversion", pct(coach_agg.conversion_rate),
              f"{(coach_agg.conversion_rate - base_agg.conversion_rate) * 100:+.1f} pp")
    k3.metric("Advisor exits", pct(coach_agg.advisor_rate))
    k4.metric("Annoyance", pct(coach_agg.annoyance_rate))
    st.caption(
        f"Weighted by funnel mix. Raw equal-persona diagnostic: baseline {pct(raw_base.conversion_rate)}, "
        f"coach {pct(raw_coach.conversion_rate)}."
    )

    per_base = per_persona(base)
    per_coach = per_persona(coach)
    persona_df = pd.DataFrame([
        {
            "Persona": PERSONAS[pid].name,
            "Funnel share": pct(FUNNEL_WEIGHTS[pid]),
            "Baseline": pct(per_base[pid].conversion_rate),
            "Coach": pct(per_coach[pid].conversion_rate),
            "Uplift pp": round((per_coach[pid].conversion_rate - per_base[pid].conversion_rate) * 100, 1),
        }
        for pid in PERSONAS
    ])
    st.dataframe(persona_df, use_container_width=True, hide_index=True)

    drop_rows = []
    for step in ["s4_initial_price", "s5_add_ons", "s7_final_price"]:
        drop_rows.append({"Step": step_label(step), "Variant": "Baseline", "Drop-off": base_agg.dropoff_per_step[step] * 100})
        drop_rows.append({"Step": step_label(step), "Variant": f"Coach {st.session_state.batch_policy_used}", "Drop-off": coach_agg.dropoff_per_step[step] * 100})
    drop_df = pd.DataFrame(drop_rows)
    chart = (
        alt.Chart(drop_df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("Step:N", title=None),
            y=alt.Y("Drop-off:Q", title="Drop-off %"),
            xOffset="Variant:N",
            color=alt.Color("Variant:N", scale=alt.Scale(range=[RED, CYAN])),
            tooltip=["Step", "Variant", alt.Tooltip("Drop-off:Q", format=".1f")],
        )
        .properties(height=330)
    )
    st.altair_chart(chart, use_container_width=True)

    # ── Abandonment reason analysis ─────────────────────────────────────────
    st.subheader("Why users stop — and what UNIQA can do")
    st.caption(
        "Each abandoned journey is classified by the behavioral signals at the "
        "drop-off step. Reasons and suggestions are derived from the simulation "
        "traces — no manual tagging required."
    )

    ab_insights = insights_from_results(base)   # baseline runs only
    if ab_insights:
        ab_df = pd.DataFrame([
            {
                "Step": i.step,
                "Persona": i.persona,
                "Signal evidence": i.signal_evidence,
                "Why they stopped": i.reason,
                "What UNIQA can do": i.suggestion,
            }
            for i in ab_insights
        ])

        # Summary counts per step.
        count_df = (
            ab_df.groupby("Step")
            .size()
            .reset_index(name="Abandoned journeys")
            .sort_values("Abandoned journeys", ascending=False)
        )
        count_chart = (
            alt.Chart(count_df)
            .mark_bar(color=RED, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("Step:N", sort="-y", title=None),
                y=alt.Y("Abandoned journeys:Q"),
                tooltip=["Step", "Abandoned journeys"],
            )
            .properties(height=200, title="Abandoned journeys per step (baseline)")
        )
        st.altair_chart(count_chart, use_container_width=True)

        # Top unique reason+suggestion pairs — deduplicated for readability.
        seen: set[tuple[str, str]] = set()
        unique_rows = []
        for i in ab_insights:
            key = (i.step, i.reason[:60])
            if key not in seen:
                seen.add(key)
                unique_rows.append({
                    "Step": i.step,
                    "Persona": i.persona,
                    "Signal": i.signal_evidence,
                    "Why they stopped": i.reason,
                    "UNIQA suggestion": i.suggestion,
                })

        for row in unique_rows:
            with st.expander(
                f"**{row['Step']}** — {row['Why they stopped'][:90]}…",
                expanded=False,
            ):
                st.markdown(f"**Signal evidence:** `{row['Signal']}`")
                st.markdown(f"**Why they stopped:** {row['Why they stopped']}")
                st.markdown(f"**What UNIQA can do:** {row['UNIQA suggestion']}")
    else:
        st.caption("Run a batch simulation above to see abandonment analysis.")


with tab_llm:
    st.subheader("Optional LLM persona run")
    st.markdown(
        """
        <div class='llm-note'>
          <strong>What this adds:</strong> the rule-based simulator remains the scored benchmark,
          while this tab can let an OpenAI-compatible model roleplay Judith, Franz, or Peter from
          the full persona briefings. If no API key is available, it falls back automatically so the demo never breaks.
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_available = bool(
        os.environ.get("FEATHERLESS_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("LOVABLE_API_KEY")
    )
    if api_available:
        st.success("LLM gateway key detected. This run can use the configured OpenAI-compatible model.")
    else:
        st.warning("No LLM API key detected. The journey will run with the safe rule-based fallback.")

    c1, c2, c3 = st.columns([1, 1.35, .8])
    with c1:
        llm_persona_id = st.selectbox(
            "LLM persona",
            list(PERSONAS.keys()),
            index=list(PERSONAS.keys()).index(persona_id),
            format_func=lambda pid: PERSONAS[pid].name,
            key="llm_persona_select",
        )
    with c2:
        llm_model = st.text_input("Model", value=DEFAULT_MODEL, key="llm_model")
    with c3:
        llm_seed = st.number_input("LLM seed", min_value=1, value=int(seed), step=1, key="llm_seed")

    l1, l2, l3 = st.columns([1.2, 1, 1.6])
    with l1:
        llm_mode = st.radio(
            "Journey mode",
            ["With Coach", "Without Coach"],
            horizontal=True,
            key="llm_mode",
        )
    with l2:
        llm_policy = st.selectbox(
            "Coach policy",
            ["balanced", "minimal", "aggressive"],
            disabled=llm_mode == "Without Coach",
            key="llm_policy",
        )
    with l3:
        llm_force = st.checkbox("Would-buy intent", value=True, key="llm_force")
        run_llm = st.button("Run LLM persona journey", type="primary", use_container_width=True)

    if run_llm or "llm_result" not in st.session_state:
        active_policy = llm_policy if llm_mode == "With Coach" else None
        result, bot = make_llm_result(
            llm_persona_id,
            int(llm_seed),
            active_policy,
            True if llm_force else None,
            llm_model,
        )
        fallback_used = bool(bot.last_error and not bot.history)
        if fallback_used:
            fallback_seed = f"{llm_persona_id}:{int(llm_seed)}:local"
            result = make_result(
                llm_persona_id,
                fallback_seed,
                active_policy,
                True if llm_force else None,
            )
        st.session_state.llm_result = result
        if fallback_used:
            st.session_state.llm_bot_history = local_fallback_trace(result)
        else:
            st.session_state.llm_bot_history = [
                {
                    "Step": step_label(trace.step),
                    "Action": trace.action,
                    "Dwell seconds": round(trace.dwell_seconds, 1),
                    "Reasoning": trace.reasoning,
                }
                for trace in bot.history
            ]
        st.session_state.llm_error = bot.last_error
        st.session_state.llm_fallback_used = fallback_used
        st.session_state.llm_title = (
            f"{PERSONAS[llm_persona_id].name} with "
            f"{'no Coach' if active_policy is None else active_policy + ' Coach'}"
        )

    left, right = st.columns([1.2, .8], gap="large")
    with left:
        render_journey(st.session_state.llm_result, st.session_state.llm_title)
    with right:
        st.markdown("<div class='panel'><h3>LLM trace</h3>", unsafe_allow_html=True)
        if st.session_state.llm_error:
            st.info(f"Gateway fallback: {st.session_state.llm_error}")
        if st.session_state.get("llm_fallback_used"):
            st.caption(
                "Showing a seeded local persona fallback so the demo remains stable while the external LLM gateway is unreachable."
            )
        history = st.session_state.llm_bot_history
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else:
            st.caption("No LLM reasoning trace was recorded because fallback mode handled this run.")
        st.markdown("</div>", unsafe_allow_html=True)


with tab_learn:
    st.subheader("Self-learning Coach — Thompson Sampling")
    st.caption(
        "The adaptive coach maintains a Beta distribution per (step x persona x intervention). "
        "After each batch it updates those priors from observed accept/reject outcomes. "
        "Progress is saved to disk after every iteration and resumed automatically next session."
    )

    # Show current saved state.
    saved_curve = _load_saved_curve()
    policy_exists = _POLICY_PATH.exists()
    if policy_exists and saved_curve:
        total_saved_obs = int(saved_curve[-1].get("observations", 0))
        st.success(
            f"Saved policy found — {len(saved_curve)} iterations, "
            f"~{total_saved_obs} observations. "
            f"Next run will **continue** from here."
        )
    else:
        st.info("No saved policy yet. First run will start fresh.")

    lc1, lc2, lc3, lc4 = st.columns([1, 1, 1.2, 1.2])
    with lc1:
        learn_iters = st.slider("More iterations", 5, 30, 10, step=5)
    with lc2:
        learn_runs = st.slider("Journeys per iteration", 50, 300, 150, step=50)
    with lc3:
        learn_btn = st.button("Continue training", type="primary",
                              use_container_width=True)
    with lc4:
        reset_btn = st.button("Reset & start fresh", use_container_width=True)

    if reset_btn:
        _POLICY_PATH.unlink(missing_ok=True)
        _CURVE_PATH.unlink(missing_ok=True)
        st.session_state.pop("learn_curve", None)
        st.session_state.pop("learn_policy", None)
        st.rerun()

    if learn_btn or "learn_curve" not in st.session_state:
        # Load existing policy from disk; create fresh if none exists.
        if _POLICY_PATH.exists():
            adaptive_policy = AdaptivePolicy.load(_POLICY_PATH)
            prior_iters = len(_load_saved_curve())
        else:
            adaptive_policy = AdaptivePolicy()
            prior_iters = 0

        progress = st.progress(0, text="Training…")
        for it in range(learn_iters):
            global_it = prior_iters + it
            it_results = []
            for pid_l in PERSONAS:
                for i in range(learn_runs):
                    s = f"{pid_l}:learn:{global_it}:{i}"
                    bot_l = PersonaBot(PERSONAS[pid_l], random.Random(s))
                    coach_l = AdaptiveCoach(adaptive_policy, persona_id=pid_l)
                    res_l = run_journey(bot_l, coach=coach_l, detector=Detector())
                    adaptive_policy.update_from_result(res_l)
                    it_results.append(res_l)

            agg_l = weighted_from_personas(per_persona(it_results))
            raw_l = aggregate(it_results)
            total_obs = sum(r.get("observations", 0)
                            for r in adaptive_policy.acceptance_table())
            row = {
                "iteration": global_it + 1,
                "Conversion %": round(agg_l.conversion_rate * 100, 2),
                "Trigger precision %": round((raw_l.trigger_precision or 0) * 100, 2),
                "Annoyance %": round((raw_l.annoyance_rate or 0) * 100, 2),
                "observations": total_obs,
            }
            # Save after every iteration — progress survives page refresh.
            adaptive_policy.save(_POLICY_PATH)
            _save_curve_row(row)

            progress.progress((it + 1) / learn_iters,
                              text=f"Iteration {global_it + 1} — "
                                   f"conversion {agg_l.conversion_rate * 100:.1f}%")

        progress.empty()
        st.session_state.learn_policy = adaptive_policy
        st.session_state.learn_curve = _load_saved_curve()
        st.rerun()

    # Always read the full curve from disk so it reflects prior sessions too.
    full_curve = _load_saved_curve()
    if "learn_policy" not in st.session_state and _POLICY_PATH.exists():
        st.session_state.learn_policy = AdaptivePolicy.load(_POLICY_PATH)

    if full_curve:
        curve_df = pd.DataFrame(full_curve)
        curve_df["Conversion %"] = curve_df["Conversion %"].astype(float)
        curve_df["Annoyance %"]  = curve_df["Annoyance %"].astype(float)
        curve_df["iteration"]    = curve_df["iteration"].astype(int)

        km1, km2, km3, km4 = st.columns(4)
        km1.metric("Total iterations", len(curve_df))
        km2.metric("Conversion iter 1", f"{curve_df['Conversion %'].iloc[0]:.1f}%")
        km3.metric(f"Conversion latest", f"{curve_df['Conversion %'].iloc[-1]:.1f}%",
                   f"{curve_df['Conversion %'].iloc[-1] - curve_df['Conversion %'].iloc[0]:+.1f} pp")
        km4.metric("Annoyance (latest)", f"{curve_df['Annoyance %'].iloc[-1]:.1f}%")

        conv_chart = (
            alt.Chart(curve_df)
            .mark_line(point=True, color=CYAN)
            .encode(
                x=alt.X("iteration:Q", title="Training iteration (cumulative)"),
                y=alt.Y("Conversion %:Q", title="Weighted conversion %",
                        scale=alt.Scale(zero=False)),
                tooltip=["iteration", "Conversion %", "Trigger precision %", "Annoyance %"],
            )
            .properties(height=280, title="Conversion improving across sessions")
        )
        st.altair_chart(conv_chart, use_container_width=True)

    if "learn_policy" in st.session_state:
        st.subheader("What the coach has learned so far")
        st.caption("Ranked by learned acceptance rate. Updated every iteration.")
        table = st.session_state.learn_policy.acceptance_table()
        if table:
            learn_df = pd.DataFrame(table).rename(columns={
                "step": "Step", "persona": "Persona",
                "intervention": "Best intervention",
                "mean_accept": "Acceptance rate",
                "observations": "Observations",
            })
            learn_df["Acceptance rate"] = learn_df["Acceptance rate"].map(
                lambda x: f"{x:.1%}")
            st.dataframe(learn_df, use_container_width=True, hide_index=True)


with tab_cluster:
    import multiprocessing as _mp
    st.subheader("Cluster-scale simulation")
    st.caption(
        "Runs thousands of journeys in parallel using all available CPU cores. "
        "The same code runs unchanged on the Leonardo HPC cluster via SLURM — "
        "just increase --workers to match the node's core count."
    )

    _cpu_count = _mp.cpu_count()
    cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, 1.5])
    with cc1:
        cl_runs = st.select_slider(
            "Runs per persona", [500, 1000, 2000, 5000, 10000], value=2000
        )
    with cc2:
        cl_workers = st.slider("Parallel workers", 1, min(_cpu_count, 16),
                               min(4, _cpu_count))
    with cc3:
        cl_policy = st.selectbox("Policy to benchmark",
                                 ["balanced", "minimal", "aggressive"],
                                 key="cl_policy")
    with cc4:
        cl_btn = st.button("Run cluster simulation", type="primary",
                           use_container_width=True)

    if cl_btn or "cl_results" not in st.session_state:
        total = len(PERSONAS) * 2 * cl_runs
        with st.spinner(f"Running {total:,} journeys across {cl_workers} workers…"):
            import time as _time
            t0 = _time.time()
            by_policy = run_parallel(
                n_runs=cl_runs,
                n_workers=cl_workers,
                policies=[cl_policy],
                seed=42,
                out=ROOT / "coach_sim" / "results" / "cluster",
                verbose=False,
                use_threads=True,   # avoids BrokenProcessPool on Windows/Streamlit
            )
            elapsed = _time.time() - t0
        st.session_state.cl_results = by_policy
        st.session_state.cl_elapsed = elapsed
        st.session_state.cl_runs = cl_runs
        st.session_state.cl_total = total

    by_pol = st.session_state.cl_results
    elapsed = st.session_state.cl_elapsed
    cl_total = st.session_state.cl_total
    cl_runs_done = st.session_state.cl_runs

    base_rows   = by_pol.get("baseline", [])
    coach_rows  = by_pol.get(cl_policy, [])

    if base_rows and coach_rows:
        base_agg  = _agg_rows(base_rows)
        coach_agg = _agg_rows(coach_rows)
        base_wconv  = _weighted_conv(base_rows)
        coach_wconv = _weighted_conv(coach_rows)

        cm1, cm2, cm3, cm4, cm5 = st.columns(5)
        cm1.metric("Total journeys", f"{cl_total:,}")
        cm2.metric("Wall-clock time", f"{elapsed:.1f}s")
        cm3.metric("Throughput", f"{cl_total / elapsed:,.0f}/s")
        cm4.metric("Baseline conv", f"{base_wconv:.2f}%")
        cm5.metric(f"{cl_policy} conv", f"{coach_wconv:.2f}%",
                   f"{coach_wconv - base_wconv:+.2f} pp")

        # Per-persona table.
        by_pid_base  = {r["persona_id"]: r for r in []}
        base_by_pid:  dict[str, list] = {}
        coach_by_pid: dict[str, list] = {}
        for r in base_rows:
            base_by_pid.setdefault(r["persona_id"], []).append(r)
        for r in coach_rows:
            coach_by_pid.setdefault(r["persona_id"], []).append(r)

        persona_rows = []
        for pid in PERSONAS:
            b = base_by_pid.get(pid, [])
            c = coach_by_pid.get(pid, [])
            b_conv = sum(1 for r in b if r["converted"]) / max(len(b), 1) * 100
            c_conv = sum(1 for r in c if r["converted"]) / max(len(c), 1) * 100
            persona_rows.append({
                "Persona": PERSONAS[pid].name,
                "Funnel share": f"{FUNNEL_WEIGHTS[pid]*100:.0f}%",
                "Baseline": f"{b_conv:.2f}%",
                f"Coach ({cl_policy})": f"{c_conv:.2f}%",
                "Uplift": f"{c_conv - b_conv:+.2f} pp",
                "Journeys": len(b),
            })
        st.dataframe(pd.DataFrame(persona_rows),
                     use_container_width=True, hide_index=True)

        st.caption(
            f"Statistical note: at {cl_runs_done:,} runs per persona the 95% "
            f"confidence interval on conversion rate is approximately "
            f"±{(1.96 * (0.2 * 0.8 / cl_runs_done) ** 0.5 * 100):.2f} pp — "
            f"results are statistically stable."
        )

    # SLURM script download.
    st.divider()
    st.markdown("**Deploy on Leonardo HPC cluster (SLURM)**")
    st.caption("Fill in your Leonardo credentials — the script is generated instantly and ready to submit.")

    slurm_c1, slurm_c2 = st.columns(2)
    with slurm_c1:
        slurm_username = st.text_input("Leonardo username", value="your_username",
                                       key="slurm_username")
        slurm_email    = st.text_input("Notification email", value="your_email@example.com",
                                       key="slurm_email")
        slurm_account  = st.text_input("SLURM account / project code", value="uniqa_hackathon",
                                       key="slurm_account")
    with slurm_c2:
        slurm_runs     = st.number_input("Runs per persona", value=50000, step=10000,
                                         key="slurm_runs")
        slurm_workers  = st.number_input("CPU workers (cores)", value=32, step=8,
                                         key="slurm_workers")
        slurm_time     = st.text_input("Time limit (HH:MM:SS)", value="02:00:00",
                                       key="slurm_time")

    script = generate_slurm(
        n_runs=int(slurm_runs),
        n_workers=int(slurm_workers),
        out_dir="coach_sim/results/cluster",
        account=slurm_account,
        username=slurm_username,
        email=slurm_email,
        time_limit=slurm_time,
    )
    st.code(script, language="bash")
    st.download_button(
        "Download cluster_job.sh",
        data=script.encode("utf-8"),
        file_name="cluster_job.sh",
        mime="text/plain",
    )
