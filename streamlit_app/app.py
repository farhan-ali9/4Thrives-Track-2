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
from coach_sim.metrics import aggregate, per_persona, weighted_from_personas  # noqa: E402
from coach_sim.personas import FUNNEL_WEIGHTS, PERSONAS, PersonaBot  # noqa: E402
from coach_sim.sim import JourneyResult, run_journey  # noqa: E402


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

WINNING_DEMO_SEEDS = {
    "judith": "judith:demo:8",
    "franz": "franz:demo:9",
    "peter": "peter:demo:7",
}

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
    coach = None
    if policy:
        coach = Coach(CoachConfig(policy=policy), persona_id=persona_id)  # type: ignore[arg-type]
    return run_journey(bot, coach=coach, detector=Detector())


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
    policy = st.selectbox("Coach policy", ["balanced", "minimal", "aggressive"], index=0)
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


tab_demo, tab_batch, tab_llm = st.tabs(["Live demo", "Results dashboard", "LLM persona"])

with tab_demo:
    st.subheader("Live side-by-side journey")
    st.caption("Use Winning demo for presentation, or Custom seed when you want the seed to change the deterministic run.")

    pid = persona_id
    if demo_mode == "Winning demo":
        seed_str = WINNING_DEMO_SEEDS[persona_id]
        wants = True
    else:
        seed_str = f"{persona_id}:{int(seed)}:live"
        wants = True if force else None
    baseline = make_result(pid, seed_str, None, wants)
    coached = make_result(pid, seed_str, policy, wants)

    b_status, _ = status_label(baseline)
    c_status, _ = status_label(coached)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Persona", PERSONAS[pid].name)
    m2.metric("Without Coach", b_status)
    m3.metric("With Coach", c_status)
    m4.metric("Accepted", f"{coached.interventions_accepted}/{coached.interventions_shown}")
    m5.metric("Run seed", "demo" if demo_mode == "Winning demo" else str(int(seed)))

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
