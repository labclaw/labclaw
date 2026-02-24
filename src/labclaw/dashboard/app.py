"""LabClaw Dashboard — Streamlit-based monitoring UI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from labclaw import __version__
from labclaw.core.events import event_registry
from labclaw.core.schemas import DeviceStatus, EvolutionTarget
from labclaw.discovery.hypothesis import HypothesisGenerator, HypothesisInput
from labclaw.discovery.mining import MiningConfig, PatternMiner
from labclaw.edge.session_chronicle import SessionChronicle
from labclaw.evolution.engine import EvolutionEngine
from labclaw.hardware.registry import DeviceRegistry
from labclaw.hardware.schemas import DeviceRecord

# ---------------------------------------------------------------------------
# Shared state (singleton per Streamlit session)
# ---------------------------------------------------------------------------

def _get_device_registry() -> DeviceRegistry:
    if "device_registry" not in st.session_state:
        st.session_state.device_registry = DeviceRegistry()
    return st.session_state.device_registry


def _get_session_chronicle() -> SessionChronicle:
    if "session_chronicle" not in st.session_state:
        st.session_state.session_chronicle = SessionChronicle()
    return st.session_state.session_chronicle


def _get_evolution_engine() -> EvolutionEngine:
    if "evolution_engine" not in st.session_state:
        st.session_state.evolution_engine = EvolutionEngine()
    return st.session_state.evolution_engine


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def show_overview() -> None:
    st.title("LabClaw -- Lab Intelligence Dashboard")
    st.caption(f"v{__version__}")

    events = event_registry.list_events()
    devices = _get_device_registry().list_devices()
    sessions = _get_session_chronicle().list_sessions()

    col1, col2, col3 = st.columns(3)
    col1.metric("Registered Events", len(events))
    col2.metric("Devices", len(devices))
    col3.metric("Sessions", len(sessions))

    st.subheader("System Layers")
    layers = [
        ("L1 Hardware", "Device registry, safety, interfaces"),
        ("L2 Software Infra", "Gateway, Event Bus, API, Dashboard"),
        ("L3 Scientific Engine",
         "OBSERVE -> ASK -> HYPOTHESIZE -> PREDICT -> EXPERIMENT -> ANALYZE -> CONCLUDE"),
        ("L4 Memory", "Markdown + Knowledge Graph + Shared Blocks"),
        ("L5 Persona", "Human + AI members, training, promotion"),
    ]
    for name, desc in layers:
        st.text(f"{name}: {desc}")


def show_devices() -> None:
    st.title("Devices")
    registry = _get_device_registry()
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
            rows.append({
                "ID": d.device_id[:8],
                "Name": d.name,
                "Type": d.device_type,
                "Status": f":{color}_circle: {d.status.value}",
                "Location": d.location,
                "Registered": d.registered_at.strftime("%Y-%m-%d %H:%M"),
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No devices registered yet.")

    st.subheader("Register Test Device")
    with st.form("register_device"):
        name = st.text_input("Name", value="Test Microscope")
        device_type = st.selectbox("Type", ["microscope", "camera", "ephys_rig", "qpcr", "printer"])
        location = st.text_input("Location", value="Room 101")
        submitted = st.form_submit_button("Register")
        if submitted and name:
            record = DeviceRecord(
                name=name, device_type=device_type or "microscope", location=location,
            )
            registry.register(record)
            st.success(f"Registered: {name} ({record.device_id[:8]})")
            st.rerun()


def show_sessions() -> None:
    st.title("Sessions")
    chronicle = _get_session_chronicle()
    sessions = chronicle.list_sessions()

    if not sessions:
        st.info("No sessions recorded yet.")
        with st.form("start_session"):
            operator = st.text_input("Operator ID", value="demo-user")
            experiment = st.text_input("Experiment ID", value="exp-001")
            if st.form_submit_button("Start Demo Session"):
                s = chronicle.start_session(operator_id=operator, experiment_id=experiment)
                st.success(f"Session started: {s.node_id[:8]}")
                st.rerun()
        return

    rows: list[dict[str, Any]] = []
    for s in sessions:
        rows.append({
            "ID": s.node_id[:8],
            "Operator": s.operator_id or "-",
            "Experiment": s.experiment_id or "-",
            "Date": s.session_date.strftime("%Y-%m-%d %H:%M"),
            "Duration (s)": f"{s.duration_seconds:.1f}" if s.duration_seconds else "active",
        })
    st.dataframe(rows, use_container_width=True)

    st.subheader("Session Details")
    session_ids = [s.node_id for s in sessions]
    selected = st.selectbox("Select session", session_ids, format_func=lambda x: x[:8])
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


def show_discovery() -> None:
    st.title("Discovery Pipeline")
    st.caption("Mine patterns from experimental data and generate hypotheses.")

    csv_path = st.text_input("CSV data path", placeholder="/path/to/data.csv")

    if st.button("Run Mining Pipeline") and csv_path:
        path = Path(csv_path)
        if not path.exists():
            st.error(f"File not found: {csv_path}")
            return

        try:
            import csv as csv_mod

            with path.open() as f:
                reader = csv_mod.DictReader(f)
                data: list[dict[str, Any]] = []
                for row in reader:
                    parsed: dict[str, Any] = {}
                    for k, v in row.items():
                        try:
                            parsed[k] = float(v)
                        except (ValueError, TypeError):
                            parsed[k] = v
                    data.append(parsed)

            st.write(f"Loaded {len(data)} rows from CSV.")

            miner = PatternMiner()
            config = MiningConfig(min_sessions=3)
            result = miner.mine(data, config)

            st.subheader("Patterns Found")
            if result.patterns:
                for p in result.patterns:
                    st.markdown(
                        f"**[{p.pattern_type}]** {p.description} "
                        f"(confidence: {p.confidence:.2f})",
                    )
            else:
                st.info("No significant patterns found.")

            st.subheader("Generated Hypotheses")
            if result.patterns:
                gen = HypothesisGenerator()
                hypotheses = gen.generate(HypothesisInput(patterns=result.patterns))
                for h in hypotheses:
                    st.markdown(f"- **{h.statement}**")
                    exps = ", ".join(h.required_experiments)
                    st.caption(
                        f"  Confidence: {h.confidence:.2f} | Experiments needed: {exps}",
                    )
            else:
                st.info("No patterns to generate hypotheses from.")

        except Exception as exc:
            st.error(f"Mining failed: {exc}")

    st.divider()
    st.subheader("Quick Demo (no file needed)")
    if st.button("Run Demo Mining"):
        demo_data: list[dict[str, Any]] = [
            {
                "session_id": f"s{i}", "timestamp": i,
                "firing_rate": 10 + i * 0.5 + (5 if i == 8 else 0),
                "speed": 20 - i * 0.3,
            }
            for i in range(15)
        ]
        miner = PatternMiner()
        result = miner.mine(demo_data, MiningConfig(min_sessions=3))
        st.write(f"Found {len(result.patterns)} pattern(s) in demo data:")
        for p in result.patterns:
            st.markdown(f"- **[{p.pattern_type}]** {p.description}")

        if result.patterns:
            gen = HypothesisGenerator()
            hypotheses = gen.generate(HypothesisInput(patterns=result.patterns))
            st.subheader("Hypotheses")
            for h in hypotheses:
                st.markdown(f"- {h.statement}")


def show_evolution() -> None:
    st.title("Evolution Engine")
    engine = _get_evolution_engine()

    history = engine.get_history()
    if history:
        st.subheader("Evolution Cycles")
        rows: list[dict[str, Any]] = []
        for c in history:
            rows.append({
                "Cycle": c.cycle_id[:8],
                "Target": c.target.value,
                "Stage": c.stage.value,
                "Promoted": c.promoted,
                "Started": c.started_at.strftime("%Y-%m-%d %H:%M"),
                "Rollback": c.rollback_reason or "-",
            })
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No evolution cycles yet.")

    st.subheader("Fitness History")
    targets = list(EvolutionTarget)
    selected_target = st.selectbox("Target", targets, format_func=lambda t: t.value)
    if selected_target:
        scores = engine.fitness_tracker.get_history(selected_target)
        if scores:
            for s in scores:
                metrics_str = json.dumps(s.metrics)
                st.text(
                    f"  {s.measured_at.strftime('%H:%M:%S')} - {metrics_str} (n={s.data_points})",
                )
        else:
            st.caption("No fitness measurements for this target.")

    st.subheader("Quick Demo")
    if st.button("Run Demo Evolution Cycle"):
        target = EvolutionTarget.ANALYSIS_PARAMS
        baseline = engine.measure_fitness(
            target, {"accuracy": 0.75, "recall": 0.80}, data_points=100,
        )
        candidates = engine.propose_candidates(target, n=1)
        if candidates:
            cycle = engine.start_cycle(candidates[0], baseline)
            improved = engine.measure_fitness(
                target, {"accuracy": 0.78, "recall": 0.82}, data_points=120,
            )
            engine.advance_stage(cycle.cycle_id, improved)
            st.success(f"Cycle {cycle.cycle_id[:8]} advanced to {cycle.stage.value}")
            st.rerun()


def show_events() -> None:
    st.title("Event Registry")
    events = event_registry.list_events()

    if not events:
        st.info("No events registered.")
        return

    st.metric("Total Event Types", len(events))

    # Group by layer
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

st.set_page_config(page_title="LabClaw", page_icon="\U0001f9e0", layout="wide")

page = st.sidebar.selectbox("Navigate", [
    "Overview",
    "Devices",
    "Sessions",
    "Discovery",
    "Evolution",
    "Events",
])

if page == "Overview":
    show_overview()
elif page == "Devices":
    show_devices()
elif page == "Sessions":
    show_sessions()
elif page == "Discovery":
    show_discovery()
elif page == "Evolution":
    show_evolution()
elif page == "Events":
    show_events()
