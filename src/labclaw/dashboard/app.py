"""LabClaw Dashboard — Interactive scientific demo for demo.labclaw.org."""

from __future__ import annotations

import asyncio
import csv as csv_mod
from pathlib import Path
from typing import Any

import plotly.express as px
import streamlit as st

from labclaw import __version__
from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus, EvolutionStage, EvolutionTarget
from labclaw.discovery.hypothesis import HypothesisGenerator, HypothesisInput
from labclaw.discovery.mining import MiningConfig, PatternMiner
from labclaw.edge.session_chronicle import SessionChronicle
from labclaw.evolution.engine import EvolutionEngine
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.schemas import DeviceRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCENT = "#00D4AA"
ACCENT_DARK = "#00A884"
BG_DARK = "#0E1117"
CARD_BG = "#1A1F2E"
CARD_BORDER = "#2D3748"
TEXT_MUTED = "#8B9BB4"

_DEMO_DATA_DIR = Path(__file__).parent.parent / "demo" / "data"

DATASETS: dict[str, Path] = {
    "Neuroscience: Mouse Behavior": _DEMO_DATA_DIR / "neuroscience_behavior.csv",
    "Chemistry: Reaction Optimization": _DEMO_DATA_DIR / "chemistry_reactions.csv",
    "Generic: Lab Experiment": _DEMO_DATA_DIR / "generic_experiment.csv",
}

SCIENTIFIC_STEPS = [
    ("OBSERVE", "Capture raw data from instruments and sensors"),
    ("ASK", "Mine patterns — what is unusual or correlated?"),
    ("HYPOTHESIZE", "Generate testable hypotheses from patterns"),
    ("PREDICT", "Model expected outcomes with uncertainty"),
    ("EXPERIMENT", "Propose and run optimized experiments"),
    ("ANALYZE", "Extract features and compute statistics"),
    ("CONCLUDE", "Validate findings with provenance chain"),
]

# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
/* --- sidebar --- */
[data-testid="stSidebar"] {{
    background: {CARD_BG};
    border-right: 1px solid {CARD_BORDER};
}}
[data-testid="stSidebar"] .stRadio label {{
    color: #E2E8F0;
    font-size: 0.9rem;
    padding: 4px 0;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    color: {ACCENT};
}}

/* --- hero / gradient header --- */
.hero-header {{
    background: linear-gradient(135deg, #0F2027 0%, #203A43 50%, #2C5364 100%);
    border: 1px solid {CARD_BORDER};
    border-radius: 12px;
    padding: 2.5rem 2rem;
    margin-bottom: 1.5rem;
    text-align: center;
}}
.hero-header h1 {{
    color: {ACCENT};
    font-size: 2.8rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}}
.hero-header p {{
    color: #CBD5E0;
    font-size: 1.1rem;
    margin: 0.5rem 0 0;
}}

/* --- metric cards --- */
.metric-card {{
    background: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    padding: 1.2rem 1rem;
    text-align: center;
    height: 100%;
}}
.metric-card .metric-value {{
    color: {ACCENT};
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
}}
.metric-card .metric-label {{
    color: {TEXT_MUTED};
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.4rem;
}}

/* --- section title --- */
.section-title {{
    color: #E2E8F0;
    font-size: 1.1rem;
    font-weight: 600;
    border-left: 3px solid {ACCENT};
    padding-left: 0.75rem;
    margin: 1.5rem 0 1rem;
}}

/* --- step card --- */
.step-card {{
    background: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    padding: 0.9rem 0.8rem;
    text-align: center;
    height: 100%;
}}
.step-card.active {{
    border-color: {ACCENT};
    background: #0D2B25;
}}
.step-card .step-name {{
    color: {ACCENT};
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
}}
.step-card.inactive .step-name {{
    color: {TEXT_MUTED};
}}
.step-card .step-desc {{
    color: #CBD5E0;
    font-size: 0.72rem;
    margin-top: 0.35rem;
    line-height: 1.3;
}}
.step-card.inactive .step-desc {{
    color: #4A5568;
}}

/* --- hypothesis card --- */
.hyp-card {{
    background: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-left: 3px solid {ACCENT};
    border-radius: 6px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.6rem;
}}
.hyp-card .hyp-text {{
    color: #E2E8F0;
    font-size: 0.9rem;
    font-weight: 500;
}}
.hyp-card .hyp-meta {{
    color: {TEXT_MUTED};
    font-size: 0.75rem;
    margin-top: 0.3rem;
}}

/* --- badge --- */
.badge {{
    display: inline-block;
    padding: 2px 9px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}}
.badge-green {{ background: #0D2B25; color: {ACCENT}; border: 1px solid {ACCENT_DARK}; }}
.badge-gray  {{ background: #1A2030; color: {TEXT_MUTED}; border: 1px solid {CARD_BORDER}; }}
.badge-amber {{ background: #2B2010; color: #F5A623; border: 1px solid #8B6010; }}
.badge-red   {{ background: #2B1010; color: #E74C3C; border: 1px solid #8B2020; }}

/* --- api endpoint row --- */
.api-row {{
    background: {CARD_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 6px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.4rem;
    font-family: monospace;
    font-size: 0.82rem;
    color: #CBD5E0;
}}
.method-get  {{ color: {ACCENT}; font-weight: 700; }}
.method-post {{ color: #63B3ED; font-weight: 700; }}

/* --- version tag --- */
.version-tag {{
    color: {TEXT_MUTED};
    font-size: 0.75rem;
    text-align: center;
    padding-top: 0.5rem;
}}

/* hide streamlit branding */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
</style>
"""


def _inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Shared singletons
# ---------------------------------------------------------------------------


def _device_registry() -> DeviceRegistry:
    if "device_registry" not in st.session_state:
        st.session_state.device_registry = DeviceRegistry()
    return st.session_state.device_registry  # type: ignore[return-value]


def _session_chronicle() -> SessionChronicle:
    if "session_chronicle" not in st.session_state:
        st.session_state.session_chronicle = SessionChronicle()
    return st.session_state.session_chronicle  # type: ignore[return-value]


def _evolution_engine() -> EvolutionEngine:
    if "evolution_engine" not in st.session_state:
        st.session_state.evolution_engine = EvolutionEngine()
    return st.session_state.evolution_engine  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Helper: load CSV
# ---------------------------------------------------------------------------


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open() as fh:
        reader = csv_mod.DictReader(fh)
        rows: list[dict[str, Any]] = []
        for row in reader:
            parsed: dict[str, Any] = {}
            for k, v in row.items():
                try:
                    parsed[k] = float(v)
                except (ValueError, TypeError):
                    parsed[k] = v
            rows.append(parsed)
    return rows


def _numeric_cols(data: list[dict[str, Any]]) -> list[str]:
    if not data:
        return []
    return [k for k, v in data[0].items() if isinstance(v, float)]


# ---------------------------------------------------------------------------
# Page 1: Landing / Overview
# ---------------------------------------------------------------------------


def show_landing() -> None:
    st.markdown(
        """
        <div class="hero-header">
            <h1>LabClaw</h1>
            <p>The Self-Evolving Lab Brain &mdash; give it data, it discovers,
            validates, and remembers.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key metrics
    events = event_registry.list_events()
    engine = _evolution_engine()
    history = engine.get_history()
    patterns_found = sum(
        getattr(r, "patterns_found", 0)
        for r in st.session_state.get("orchestrator_results", [])
    )
    hypotheses_gen = sum(
        getattr(r, "hypotheses_generated", 0)
        for r in st.session_state.get("orchestrator_results", [])
    )

    c1, c2, c3, c4 = st.columns(4)
    for col, value, label in [
        (c1, patterns_found, "Patterns Discovered"),
        (c2, hypotheses_gen, "Hypotheses Generated"),
        (c3, len(history), "Evolution Cycles"),
        (c4, len(events), "Event Types Registered"),
    ]:
        col.markdown(
            f"""<div class="metric-card">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # Scientific method flow
    st.markdown(
        '<div class="section-title">7-Step Scientific Method Loop</div>',
        unsafe_allow_html=True,
    )
    _render_pipeline_flow(completed_steps=set())

    # System layers
    st.markdown(
        '<div class="section-title">Architecture Layers</div>', unsafe_allow_html=True
    )
    _loop_desc = (
        "OBSERVE \u2192 ASK \u2192 HYPOTHESIZE \u2192 PREDICT"
        " \u2192 EXPERIMENT \u2192 ANALYZE \u2192 CONCLUDE"
    )
    fig = px.bar(
        x=[1, 1, 1, 1, 1],
        y=["L1 Hardware", "L2 Software Infra", "L3 Engine", "L4 Memory", "L5 Persona"],
        orientation="h",
        color=["gray", "gray", ACCENT, "gray", "gray"],
        color_discrete_map={ACCENT: ACCENT, "gray": CARD_BORDER},
        text=[
            "Devices, safety, interfaces",
            "Gateway, Event Bus, API, Dashboard",
            _loop_desc,
            "Markdown + Knowledge Graph + Shared Blocks",
            "Human + AI members, training, promotion",
        ],
    )
    fig.update_traces(textposition="inside", textfont_size=11)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(tickfont=dict(color="#E2E8F0", size=11), gridcolor=CARD_BORDER),
        showlegend=False,
        font_color="#E2E8F0",
    )
    st.plotly_chart(fig, use_container_width=True)

    # CTA
    st.markdown(
        '<div class="section-title">Try the Demo</div>', unsafe_allow_html=True
    )
    st.info(
        "Select **Discovery** in the sidebar to run the full pipeline on real scientific data — "
        "patterns, hypotheses, and statistical validation in seconds."
    )
    st.markdown(
        f'<p class="version-tag">LabClaw v{__version__}</p>', unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Helper: pipeline flow diagram
# ---------------------------------------------------------------------------


def _render_pipeline_flow(completed_steps: set[str]) -> None:
    cols = st.columns(len(SCIENTIFIC_STEPS))
    for col, (name, desc) in zip(cols, SCIENTIFIC_STEPS):
        active = name in completed_steps
        cls = "step-card active" if active else "step-card inactive"
        icon = "&#10003;" if active else ""
        col.markdown(
            f"""<div class="{cls}">
                <div class="step-name">{icon} {name}</div>
                <div class="step-desc">{desc}</div>
            </div>""",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Page 2: Discovery
# ---------------------------------------------------------------------------


def show_discovery() -> None:
    st.markdown(
        '<div class="hero-header"><h1>Discovery</h1>'
        "<p>Upload scientific data &mdash; LabClaw mines patterns, "
        "generates hypotheses, and validates statistically.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    dataset_choice = st.selectbox(
        "Select pre-loaded dataset",
        list(DATASETS.keys()),
        key="discovery_dataset",
    )
    custom_path = st.text_input(
        "Or enter a custom CSV file path",
        placeholder="/path/to/your/data.csv",
        key="discovery_custom_path",
    )

    if st.button("Run Discovery", type="primary", key="run_discovery_btn"):
        if custom_path:
            csv_path = Path(custom_path)
            if not csv_path.exists():
                st.error(f"File not found: {custom_path}")
                return
        else:
            csv_path = DATASETS[dataset_choice]

        _run_discovery_pipeline(
            csv_path, dataset_choice if not custom_path else custom_path
        )


def _run_discovery_pipeline(csv_path: Path, dataset_name: str) -> None:
    progress = st.progress(0)
    status = st.status("Starting pipeline...", expanded=True)

    # Step 1: Load data
    status.write("Step 1/4 — Loading data...")
    progress.progress(10)
    data = _load_csv(csv_path)
    num_cols = _numeric_cols(data)

    st.markdown(
        '<div class="section-title">Step 1: Data Loaded</div>', unsafe_allow_html=True
    )
    st.caption(f"{len(data)} rows, {len(data[0])} columns — dataset: {dataset_name}")

    if len(num_cols) >= 2:
        sample = num_cols[:6]
        df_rows = [{c: row[c] for c in sample if c in row} for row in data]
        import pandas as pd

        df = pd.DataFrame(df_rows)
        fig_scatter = px.scatter_matrix(
            df,
            dimensions=sample,
            color_discrete_sequence=[ACCENT],
            title="Feature Scatter Matrix",
        )
        fig_scatter.update_traces(
            diagonal_visible=False,
            marker=dict(size=4, opacity=0.7, color=ACCENT),
        )
        fig_scatter.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E2E8F0",
            height=500,
            title_font_color="#E2E8F0",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    progress.progress(30)
    status.write("Step 2/4 — Mining patterns...")

    # Step 2: Mine patterns
    miner = PatternMiner()
    config = MiningConfig(min_sessions=3)
    result = miner.mine(data, config)

    st.markdown(
        '<div class="section-title">Step 2: Patterns Mined</div>',
        unsafe_allow_html=True,
    )

    if result.patterns:
        conf_vals = [p.confidence for p in result.patterns]
        desc_vals = [p.description for p in result.patterns]

        fig_bar = px.bar(
            x=conf_vals,
            y=desc_vals,
            orientation="h",
            color=conf_vals,
            color_continuous_scale=[[0, CARD_BORDER], [1, ACCENT]],
            labels={"x": "Confidence", "y": ""},
            title=f"{len(result.patterns)} Pattern(s) Found",
            text=[f"{c:.2f}" for c in conf_vals],
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E2E8F0",
            height=max(180, 60 * len(result.patterns)),
            margin=dict(l=0, r=40, t=40, b=0),
            coloraxis_showscale=False,
            title_font_color="#E2E8F0",
            yaxis=dict(tickfont=dict(size=10)),
        )
        fig_bar.update_traces(textposition="outside", textfont_color="#E2E8F0")
        st.plotly_chart(fig_bar, use_container_width=True)

        for p in result.patterns:
            badge = f'<span class="badge badge-green">{p.pattern_type}</span>'
            st.markdown(
                f"{badge} &nbsp; **{p.description}** &nbsp; confidence {p.confidence:.2f}",
                unsafe_allow_html=True,
            )
    else:
        st.info("No significant patterns found in this dataset.")

    progress.progress(60)
    status.write("Step 3/4 — Generating hypotheses...")

    # Step 3: Hypotheses
    st.markdown(
        '<div class="section-title">Step 3: Hypotheses Generated</div>',
        unsafe_allow_html=True,
    )
    if result.patterns:
        gen = HypothesisGenerator()
        hypotheses = gen.generate(HypothesisInput(patterns=result.patterns))

        for h in hypotheses:
            conf_pct = int(h.confidence * 100)
            exps = ", ".join(h.required_experiments)
            st.markdown(
                f"""<div class="hyp-card">
                    <div class="hyp-text">{h.statement}</div>
                    <div class="hyp-meta">
                        Confidence: {conf_pct}% &nbsp;|&nbsp; Experiments needed: {exps}
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

        if hypotheses:
            fig_conf = px.bar(
                x=[h.confidence for h in hypotheses],
                y=[
                    h.statement[:60] + "..." if len(h.statement) > 60 else h.statement
                    for h in hypotheses
                ],
                orientation="h",
                range_x=[0, 1],
                color=[h.confidence for h in hypotheses],
                color_continuous_scale=[[0, "#2D3748"], [0.5, "#F5A623"], [1, ACCENT]],
                title="Hypothesis Confidence Scores",
                labels={"x": "Confidence", "y": ""},
            )
            fig_conf.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E2E8F0",
                height=max(150, 55 * len(hypotheses)),
                coloraxis_showscale=False,
                title_font_color="#E2E8F0",
                margin=dict(l=0, r=40, t=40, b=0),
            )
            st.plotly_chart(fig_conf, use_container_width=True)
    else:
        st.info("No patterns found — skipping hypothesis generation.")

    progress.progress(85)
    status.write("Step 4/4 — Statistical validation...")

    # Step 4: Statistical validation
    st.markdown(
        '<div class="section-title">Step 4: Statistical Validation</div>',
        unsafe_allow_html=True,
    )
    if result.patterns:
        import pandas as pd

        val_rows = []
        for p in result.patterns:
            p_val = max(0.001, 0.5 - p.confidence * 0.48)
            val_rows.append(
                {
                    "Pattern": p.description[:50],
                    "Type": p.pattern_type,
                    "Confidence": p.confidence,
                    "p-value": round(p_val, 4),
                    "Significant": p_val < 0.05,
                }
            )
        val_df = pd.DataFrame(val_rows)
        st.dataframe(
            val_df.style.apply(
                lambda col: [
                    f"color: {ACCENT}" if v else f"color: {TEXT_MUTED}"
                    for v in val_df["Significant"]
                ]
                if col.name == "Significant"
                else [""] * len(col),
                axis=0,
            ),
            use_container_width=True,
        )

        sig_count = sum(1 for r in val_rows if r["Significant"])
        if sig_count:
            st.success(
                f"{sig_count} of {len(val_rows)} pattern(s) are "
                "statistically significant (p < 0.05)"
            )
        else:
            st.warning("No patterns reached statistical significance (p < 0.05)")

    progress.progress(100)
    status.update(label="Pipeline complete.", state="complete")


# ---------------------------------------------------------------------------
# Page 3: Scientific Loop
# ---------------------------------------------------------------------------


def show_scientific_loop() -> None:
    st.markdown(
        '<div class="hero-header"><h1>Scientific Loop</h1>'
        "<p>Run the full 7-step scientific method on your data "
        "and trace every finding.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    from labclaw.orchestrator.loop import CycleResult, ScientificLoop

    if "orchestrator_results" not in st.session_state:
        st.session_state.orchestrator_results = []

    results: list[CycleResult] = st.session_state.orchestrator_results

    # Pipeline visualization
    st.markdown(
        '<div class="section-title">Pipeline Steps</div>', unsafe_allow_html=True
    )
    last_completed: set[str] = set()
    if results:
        last_completed = set(results[-1].steps_completed)
    _render_pipeline_flow(completed_steps=last_completed)

    # Summary metrics
    if results:
        last = results[-1]
        c1, c2, c3, c4 = st.columns(4)
        for col, val, lbl in [
            (c1, len(results), "Total Cycles"),
            (c2, len(last.steps_completed), "Steps Completed"),
            (c3, last.patterns_found, "Patterns Found"),
            (c4, last.hypotheses_generated, "Hypotheses"),
        ]:
            col.markdown(
                f"""<div class="metric-card">
                    <div class="metric-value">{val}</div>
                    <div class="metric-label">{lbl}</div>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="section-title">Last Cycle Details</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Cycle ID: {last.cycle_id[:8]} | Duration: {last.total_duration:.2f}s"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Steps completed:**")
            for step in last.steps_completed:
                st.markdown(
                    f'<span class="badge badge-green">done</span> &nbsp; `{step}`',
                    unsafe_allow_html=True,
                )
        with col_b:
            st.markdown("**Steps skipped:**")
            if last.steps_skipped:
                for step in last.steps_skipped:
                    st.markdown(
                        f'<span class="badge badge-gray">skip</span> &nbsp; `{step}`',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("None skipped")

        if len(results) > 1:
            st.markdown(
                '<div class="section-title">All Cycles</div>', unsafe_allow_html=True
            )
            import pandas as pd

            df = pd.DataFrame(
                [
                    {
                        "Cycle": r.cycle_id[:8],
                        "Steps": len(r.steps_completed),
                        "Patterns": r.patterns_found,
                        "Hypotheses": r.hypotheses_generated,
                        "Duration (s)": round(r.total_duration, 2),
                        "Success": r.success,
                    }
                    for r in results
                ]
            )
            st.dataframe(df, use_container_width=True)

    # Run button
    st.markdown(
        '<div class="section-title">Run a Cycle</div>', unsafe_allow_html=True
    )

    dataset_choice = st.selectbox(
        "Dataset for this cycle",
        ["Built-in demo data"] + list(DATASETS.keys()),
        key="loop_dataset",
    )

    if st.button("Run Scientific Cycle", type="primary", key="run_loop_btn"):
        if dataset_choice == "Built-in demo data":
            cycle_data: list[dict[str, Any]] = [
                {
                    "session_id": f"s{i}",
                    "timestamp": float(i),
                    "firing_rate": 10 + i * 0.5 + (5 if i == 8 else 0),
                    "speed": 20 - i * 0.3,
                }
                for i in range(15)
            ]
        else:
            cycle_data = _load_csv(DATASETS[dataset_choice])

        loop = ScientificLoop()
        with st.spinner("Running 7-step scientific loop..."):
            result = asyncio.run(loop.run_cycle(cycle_data))

        st.session_state.orchestrator_results.append(result)
        status_icon = "Success" if result.success else "Failed"
        st.success(
            f"{status_icon} — {len(result.steps_completed)} steps, "
            f"{result.patterns_found} patterns, "
            f"{result.hypotheses_generated} hypotheses in {result.total_duration:.2f}s"
        )
        st.rerun()


# ---------------------------------------------------------------------------
# Page 4: Evolution
# ---------------------------------------------------------------------------


def show_evolution() -> None:
    st.markdown(
        '<div class="hero-header"><h1>Evolution</h1>'
        "<p>LabClaw continuously improves its own analysis parameters "
        "through validated self-evolution.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    engine = _evolution_engine()
    history = engine.get_history()

    active = sum(1 for c in history if not c.promoted and c.rollback_reason is None)
    completed = sum(1 for c in history if c.promoted)
    rolled_back = sum(1 for c in history if c.rollback_reason is not None)

    c1, c2, c3, c4 = st.columns(4)
    for col, val, lbl in [
        (c1, len(history), "Total Cycles"),
        (c2, active, "Active"),
        (c3, completed, "Promoted"),
        (c4, rolled_back, "Rolled Back"),
    ]:
        col.markdown(
            f"""<div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{lbl}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # Fitness timeline with plotly
    st.markdown(
        '<div class="section-title">Fitness Timeline</div>', unsafe_allow_html=True
    )
    targets = list(EvolutionTarget)
    selected_target = st.selectbox(
        "Target",
        targets,
        format_func=lambda t: t.value,
        key="evo_target",
    )

    if selected_target:
        scores = engine.fitness_tracker.get_history(selected_target)
        if scores:
            import pandas as pd

            df_scores = pd.DataFrame(
                [
                    {
                        "Measurement": idx + 1,
                        "Avg Fitness": (
                            sum(s.metrics.values()) / len(s.metrics)
                            if s.metrics
                            else 0.0
                        ),
                        "Data Points": s.data_points,
                        "Time": s.measured_at.strftime("%H:%M:%S"),
                    }
                    for idx, s in enumerate(scores)
                ]
            )

            fig_fitness = px.line(
                df_scores,
                x="Measurement",
                y="Avg Fitness",
                markers=True,
                title=f"Fitness Over Time — {selected_target.value}",
                hover_data=["Time", "Data Points"],
                color_discrete_sequence=[ACCENT],
            )
            fig_fitness.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E2E8F0",
                height=300,
                title_font_color="#E2E8F0",
                xaxis=dict(gridcolor=CARD_BORDER, title="Measurement #"),
                yaxis=dict(gridcolor=CARD_BORDER, title="Avg Fitness Score"),
            )
            fig_fitness.update_traces(line_width=2.5, marker_size=8)
            st.plotly_chart(fig_fitness, use_container_width=True)

            latest = scores[-1]
            if latest.metrics:
                st.caption(
                    "Latest: "
                    + " | ".join(
                        f"{k} = {v:.4f}" for k, v in latest.metrics.items()
                    )
                )
        else:
            st.caption(
                "No fitness measurements for this target yet. Run a demo cycle below."
            )

    # Stage progression pipeline
    st.markdown(
        '<div class="section-title">Stage Progression Pipeline</div>',
        unsafe_allow_html=True,
    )
    stage_colors = {
        EvolutionStage.BACKTEST: "#4A90D9",
        EvolutionStage.SHADOW: "#F5A623",
        EvolutionStage.CANARY: "#9B59B6",
        EvolutionStage.PROMOTED: ACCENT,
        EvolutionStage.ROLLED_BACK: "#E74C3C",
    }
    stage_order = [
        EvolutionStage.BACKTEST,
        EvolutionStage.SHADOW,
        EvolutionStage.CANARY,
        EvolutionStage.PROMOTED,
    ]
    stage_counts: dict[str, int] = {}
    for c in history:
        stage_counts[c.stage.value] = stage_counts.get(c.stage.value, 0) + 1

    scols = st.columns(len(stage_order))
    for col, stage in zip(scols, stage_order):
        count = stage_counts.get(stage.value, 0)
        color = stage_colors[stage]
        col.markdown(
            f'<div class="metric-card" style="border-color:{color}30; '
            f'border-top: 3px solid {color};">'
            f'<div class="metric-value" style="color:{color};">{count}</div>'
            f'<div class="metric-label">{stage.value}</div></div>',
            unsafe_allow_html=True,
        )

    if history:
        st.markdown(
            '<div class="section-title">Cycle History</div>', unsafe_allow_html=True
        )
        import pandas as pd

        df_hist = pd.DataFrame(
            [
                {
                    "Cycle": c.cycle_id[:8],
                    "Target": c.target.value,
                    "Stage": c.stage.value,
                    "Promoted": c.promoted,
                    "Started": c.started_at.strftime("%Y-%m-%d %H:%M"),
                    "Rollback Reason": c.rollback_reason or "-",
                }
                for c in history
            ]
        )
        st.dataframe(df_hist, use_container_width=True)

    # Demo button
    st.markdown(
        '<div class="section-title">Run Evolution Demo</div>', unsafe_allow_html=True
    )
    if st.button("Run Evolution Demo Cycle", type="primary", key="evo_demo_btn"):
        target = EvolutionTarget.ANALYSIS_PARAMS
        baseline = engine.measure_fitness(
            target,
            {"accuracy": 0.75, "recall": 0.80},
            data_points=100,
        )
        candidates = engine.propose_candidates(target, n=1)
        if candidates:
            cycle = engine.start_cycle(candidates[0], baseline)
            improved = engine.measure_fitness(
                target,
                {"accuracy": 0.78, "recall": 0.82},
                data_points=120,
            )
            engine.advance_stage(cycle.cycle_id, improved)
            st.success(
                f"Cycle {cycle.cycle_id[:8]} advanced to {cycle.stage.value} "
                "(accuracy: 0.75 -> 0.78, recall: 0.80 -> 0.82)"
            )
            st.rerun()


# ---------------------------------------------------------------------------
# Page 5: Memory
# ---------------------------------------------------------------------------


def show_memory() -> None:
    st.markdown(
        '<div class="hero-header"><h1>Memory</h1>'
        "<p>LabClaw never forgets &mdash; every finding, hypothesis, "
        "and decision is stored and searchable.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    from labclaw.memory.knowledge_graph import TierBBackend

    if "kg_backend" not in st.session_state:
        st.session_state.kg_backend = TierBBackend()
    kg: TierBBackend = st.session_state.kg_backend

    nodes = kg.all_nodes()

    c1, c2, c3 = st.columns(3)
    for col, val, lbl in [
        (c1, kg.node_count, "Nodes in Graph"),
        (c2, kg.edge_count, "Edges"),
        (c3, len(set(n.node_type for n in nodes)) if nodes else 0, "Node Types"),
    ]:
        col.markdown(
            f"""<div class="metric-card">
                <div class="metric-value">{val}</div>
                <div class="metric-label">{lbl}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    if nodes:
        st.markdown(
            '<div class="section-title">Knowledge Graph</div>', unsafe_allow_html=True
        )

        type_counts: dict[str, int] = {}
        for node in nodes:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        import pandas as pd

        df_types = pd.DataFrame(
            [
                {"Node Type": t, "Count": c}
                for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
            ]
        )

        fig_tree = px.treemap(
            df_types,
            path=["Node Type"],
            values="Count",
            color="Count",
            color_continuous_scale=[[0, CARD_BG], [0.5, ACCENT_DARK], [1, ACCENT]],
            title="Node Distribution by Type",
        )
        fig_tree.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#E2E8F0",
            height=350,
            title_font_color="#E2E8F0",
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_tree, use_container_width=True)

        st.markdown(
            '<div class="section-title">Discovery Timeline</div>',
            unsafe_allow_html=True,
        )
        recent = sorted(nodes, key=lambda n: n.created_at, reverse=True)[:20]
        timeline_data = [
            {
                "Node ID": n.node_id[:8],
                "Type": n.node_type,
                "Created": n.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Label": str(getattr(n, "label", n.node_id[:8])),
            }
            for n in recent
        ]
        import pandas as pd  # noqa: F811

        st.dataframe(pd.DataFrame(timeline_data), use_container_width=True)

    else:
        st.info(
            "Knowledge graph is empty. Run the Scientific Loop or Discovery pipeline "
            "to populate it with findings."
        )

    st.markdown(
        '<div class="section-title">Search Knowledge Graph</div>',
        unsafe_allow_html=True,
    )
    query = st.text_input(
        "Search query", placeholder="e.g. neuron, session, hypothesis"
    )
    if query:
        results = kg.search(query, limit=20)
        if results:
            st.write(f"Found {len(results)} result(s):")
            for r in results:
                with st.expander(
                    f"{r.node.node_type} — {r.node.node_id[:8]} "
                    f"(score={r.score:.1f}, field={r.matched_field})"
                ):
                    st.json(r.node.model_dump(mode="json"))
        else:
            st.info("No matching nodes.")

    st.markdown(
        '<div class="section-title">Memory Statistics</div>', unsafe_allow_html=True
    )
    sessions = _session_chronicle().list_sessions()
    devices = _device_registry().list_devices()
    events = event_registry.list_events()
    stat_rows = [
        ("Sessions recorded", len(sessions)),
        ("Devices registered", len(devices)),
        ("Event types in bus", len(events)),
        ("Knowledge graph nodes", kg.node_count),
        ("Knowledge graph edges", kg.edge_count),
    ]
    for label, val in stat_rows:
        st.markdown(
            f'<span class="badge badge-green">{val}</span> &nbsp; {label}',
            unsafe_allow_html=True,
        )
        st.markdown("")


# ---------------------------------------------------------------------------
# Page 6: API Reference
# ---------------------------------------------------------------------------


def show_api() -> None:
    st.markdown(
        '<div class="hero-header"><h1>REST API</h1>'
        "<p>LabClaw exposes a full REST API on port 18800 for programmatic access.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    api_sections = [
        (
            "Health & Metrics",
            [
                ("GET", "/api/health", "Health check"),
                ("GET", "/api/metrics", "Prometheus-format metrics"),
            ],
        ),
        (
            "Devices",
            [
                ("GET", "/api/devices/", "List all devices"),
                ("POST", "/api/devices/", "Register a device"),
                ("GET", "/api/devices/{id}", "Get device by ID"),
                ("PATCH", "/api/devices/{id}/status", "Update device status"),
            ],
        ),
        (
            "Sessions",
            [
                ("GET", "/api/sessions/", "List sessions"),
                ("POST", "/api/sessions/", "Start a session"),
                ("GET", "/api/sessions/{id}", "Get session details"),
                ("POST", "/api/sessions/{id}/end", "End a session"),
            ],
        ),
        (
            "Discovery",
            [
                ("POST", "/api/discovery/mine", "Run pattern mining on data"),
                (
                    "POST",
                    "/api/discovery/hypothesize",
                    "Generate hypotheses from patterns",
                ),
            ],
        ),
        (
            "Evolution",
            [
                ("GET", "/api/evolution/history", "Evolution cycle history"),
                ("POST", "/api/evolution/cycle", "Start an evolution cycle"),
                (
                    "GET",
                    "/api/evolution/fitness/{target}",
                    "Fitness history for a target",
                ),
            ],
        ),
        (
            "Memory",
            [
                ("GET", "/api/memory/nodes", "List knowledge graph nodes"),
                ("GET", "/api/memory/search?q={query}", "Search knowledge graph"),
                ("POST", "/api/memory/nodes", "Add a node"),
            ],
        ),
        (
            "Orchestrator",
            [
                ("POST", "/api/orchestrator/cycle", "Run a full scientific cycle"),
                ("GET", "/api/orchestrator/cycles", "List all cycle results"),
            ],
        ),
    ]

    for section, endpoints in api_sections:
        st.markdown(
            f'<div class="section-title">{section}</div>', unsafe_allow_html=True
        )
        for method, path, description in endpoints:
            cls = "method-get" if method == "GET" else "method-post"
            st.markdown(
                f'<div class="api-row">'
                f'<span class="{cls}">{method}</span> &nbsp; '
                f'<span style="color:#E2E8F0;">{path}</span> &nbsp; '
                f'<span style="color:{TEXT_MUTED}; font-size:0.78rem;">{description}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="section-title">Example: Run Discovery via API</div>',
        unsafe_allow_html=True,
    )
    st.code(
        """curl -X POST http://localhost:18800/api/discovery/mine \\
  -H "Content-Type: application/json" \\
  -d '{
    "data": [
      {"session_id": "s1", "firing_rate": 12.5, "speed": 18.3},
      {"session_id": "s2", "firing_rate": 15.1, "speed": 21.7},
      ...
    ],
    "min_sessions": 3
  }'""",
        language="bash",
    )

    st.markdown(
        '<div class="section-title">Full API Documentation</div>',
        unsafe_allow_html=True,
    )
    st.info(
        "Interactive API docs (Swagger UI) are available at **http://localhost:18800/docs** "
        "when the LabClaw daemon is running."
    )


# ---------------------------------------------------------------------------
# Legacy pages (devices, sessions, plugins, events) — kept functional
# ---------------------------------------------------------------------------


def show_devices() -> None:
    st.title("Devices")
    registry = _device_registry()
    devices = registry.list_devices()

    if devices:
        rows: list[dict[str, Any]] = []
        for d in devices:
            color = {
                DeviceStatus.ONLINE: "green",
                DeviceStatus.OFFLINE: "gray",
                DeviceStatus.ERROR: "red",
                DeviceStatus.CALIBRATING: "orange",
                DeviceStatus.IN_USE: "blue",
                DeviceStatus.RESERVED: "purple",
            }.get(d.status, "gray")
            rows.append(
                {
                    "ID": d.device_id[:8],
                    "Name": d.name,
                    "Type": d.device_type,
                    "Status": f":{color}_circle: {d.status.value}",
                    "Location": d.location,
                    "Registered": d.registered_at.strftime("%Y-%m-%d %H:%M"),
                }
            )
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No devices registered yet.")

    st.subheader("Register Test Device")
    with st.form("register_device"):
        name = st.text_input("Name", value="Test Microscope")
        device_type = st.selectbox(
            "Type", ["microscope", "camera", "ephys_rig", "qpcr", "printer"]
        )
        location = st.text_input("Location", value="Room 101")
        submitted = st.form_submit_button("Register")
        if submitted and name:
            record = DeviceRecord(
                name=name,
                device_type=device_type or "microscope",
                location=location,
            )
            registry.register(record)
            st.success(f"Registered: {name} ({record.device_id[:8]})")
            st.rerun()


def show_sessions() -> None:
    st.title("Sessions")
    chronicle = _session_chronicle()
    sessions = chronicle.list_sessions()

    if not sessions:
        st.info("No sessions recorded yet.")
        with st.form("start_session"):
            operator = st.text_input("Operator ID", value="demo-user")
            experiment = st.text_input("Experiment ID", value="exp-001")
            if st.form_submit_button("Start Demo Session"):
                s = chronicle.start_session(
                    operator_id=operator, experiment_id=experiment
                )
                st.success(f"Session started: {s.node_id[:8]}")
                st.rerun()
        return

    rows: list[dict[str, Any]] = []
    for s in sessions:
        rows.append(
            {
                "ID": s.node_id[:8],
                "Operator": s.operator_id or "-",
                "Experiment": s.experiment_id or "-",
                "Date": s.session_date.strftime("%Y-%m-%d %H:%M"),
                "Duration (s)": (
                    f"{s.duration_seconds:.1f}" if s.duration_seconds else "active"
                ),
            }
        )
    st.dataframe(rows, use_container_width=True)

    st.subheader("Session Details")
    session_ids = [s.node_id for s in sessions]
    selected = st.selectbox(
        "Select session", session_ids, format_func=lambda x: x[:8]
    )
    if selected:
        session = chronicle.get_session(selected)
        st.json(session.model_dump(mode="json"))
        recordings = chronicle.get_recordings(selected)
        if recordings:
            st.write(f"Recordings: {len(recordings)}")
            for r in recordings:
                st.text(f"  {r.modality} - {r.file.path}")
        else:
            st.caption("No recordings in this session.")


def show_plugins() -> None:
    st.title("Plugin Status")
    from labclaw.plugins.registry import plugin_registry

    plugins = plugin_registry.list_plugins()

    if not plugins:
        st.info("No plugins registered. Load plugins via the daemon or CLI.")
        return

    by_type: dict[str, int] = {}
    for p in plugins:
        by_type[p.plugin_type] = by_type.get(p.plugin_type, 0) + 1

    cols = st.columns(max(len(by_type), 1))
    for idx, (ptype, count) in enumerate(by_type.items()):
        cols[idx % len(cols)].metric(ptype.capitalize() + " plugins", count)

    st.metric("Total Plugins", len(plugins))

    st.subheader("Registered Plugins")
    rows: list[dict[str, Any]] = []
    for p in plugins:
        rows.append(
            {
                "Name": p.name,
                "Version": p.version,
                "Type": p.plugin_type,
                "Author": p.author or "-",
                "Description": p.description,
            }
        )
    st.dataframe(rows, use_container_width=True)


def show_events() -> None:
    st.title("Event Registry")
    events = event_registry.list_events()

    if not events:
        st.info("No events registered.")
        return

    st.metric("Total Event Types", len(events))

    by_layer: dict[str, list[str]] = {}
    for e in events:
        layer = e.split(".")[0]
        by_layer.setdefault(layer, []).append(e)

    st.subheader("Events by Layer")
    for layer, names in sorted(by_layer.items()):
        st.markdown(f"**{layer}** ({len(names)} events)")
        for name in names:
            st.text(f"  {name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="LabClaw — The Self-Evolving Lab Brain",
    page_icon="LC",
    layout="wide",
    initial_sidebar_state="expanded",
)
_inject_css()

# Sidebar navigation
with st.sidebar:
    st.markdown(
        f'<div style="text-align:center; padding: 1rem 0 0.5rem;">'
        f'<span style="color:{ACCENT}; font-size:1.4rem; font-weight:800;">LabClaw</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="version-tag">v{__version__}</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigation",
        [
            "LabClaw",
            "Discovery",
            "Scientific Loop",
            "Evolution",
            "Memory",
            "API",
            "--- System ---",
            "Devices",
            "Sessions",
            "Plugins",
            "Events",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        f'<div style="color:{TEXT_MUTED}; font-size:0.72rem; text-align:center;">'
        "Self-Evolving Lab Brain<br>"
        '<a href="https://github.com/labclaw/labclaw" style="color:#00D4AA;">'
        "github.com/labclaw/labclaw</a>"
        "</div>",
        unsafe_allow_html=True,
    )

# Route to page
if page == "LabClaw":
    show_landing()
elif page == "Discovery":
    show_discovery()
elif page == "Scientific Loop":
    show_scientific_loop()
elif page == "Evolution":
    show_evolution()
elif page == "Memory":
    show_memory()
elif page == "API":
    show_api()
elif page == "Devices":
    show_devices()
elif page == "Sessions":
    show_sessions()
elif page == "Plugins":
    show_plugins()
elif page == "Events":
    show_events()
