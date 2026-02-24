# LabClaw Multi-Domain Science Roadmap

LabClaw's core architecture is **domain-agnostic** — the plugin system supports any science domain through `DomainPlugin`. This document outlines the planned domain expansions.

## Current Status (v0.0.2)

- **Core:** Domain-agnostic engine with 5-layer stack
- **Built-in domains:** Generic, Neuroscience (shenlab domain pack)
- **Plugin types:** DevicePlugin, DomainPlugin, AnalysisPlugin

## Domain Plugin Architecture

Each domain plugin provides:

```python
class DomainPlugin(Protocol):
    def sample_types(self) -> list[type[GraphNode]]: ...
    def sentinel_rules(self) -> list[SentinelRule]: ...
    def hypothesis_templates(self) -> list[str]: ...
    def analysis_defaults(self) -> dict[str, Any]: ...
```

A new domain = **< 100 lines** of Python to define sample types, safety rules, and analysis defaults.

## Planned Domains

### Tier 1 — Near-term (v0.1.x)

These domains have clear data formats and the highest demand.

| Domain | Key Instruments | Data Types | Status |
|--------|----------------|------------|--------|
| **Neuroscience** | Two-photon, EEG, behavioral rigs | TIFF, NWB, CSV, video | **Built** (shenlab) |
| **Molecular Biology** | qPCR, gel imager, plate reader | CSV, TIFF, absorbance | **Partial** (qPCR driver exists) |
| **Chemistry** | Spectrometers, HPLC, LC-MS | CSV, mzML, JCAMP-DX | Planned |
| **Materials Science** | SEM, XRD, tensile testing | TIFF, CSV, CIF | Planned |

### Tier 2 — Mid-term (v0.2.x)

| Domain | Key Instruments | Data Types |
|--------|----------------|------------|
| **Genomics/Bioinformatics** | Sequencers, flow cytometers | FASTQ, BAM, FCS |
| **Medical/Clinical** | Imaging, lab analyzers | DICOM, HL7/FHIR, CSV |
| **Cell Biology** | Confocal, flow cytometry, incubators | TIFF, FCS, time-lapse |
| **Pharmacology** | Plate readers, dose-response | CSV, dose-response curves |

### Tier 3 — Long-term (v1.0+)

| Domain | Key Instruments | Data Types |
|--------|----------------|------------|
| **Physics** | Oscilloscopes, laser systems | HDF5, ROOT, CSV |
| **Environmental Science** | Weather stations, water samplers | NetCDF, CSV, GeoJSON |
| **Robotics/AI** | Robot arms, sensors, cameras | ROS bags, video, telemetry |
| **Computer Science/ML** | GPU clusters, experiment trackers | JSON, W&B logs, TensorBoard |
| **Agriculture** | Soil sensors, drone imaging | GeoTIFF, CSV, multispectral |

## Domain-Specific Features

### Neuroscience (current)

```
labclaw-neuro plugin:
├── AnimalSampleNode (species, strain, age, sex)
├── Sentinel rules (behavioral thresholds, neural activity alerts)
├── Hypothesis templates (neural correlates, behavioral patterns)
├── Device drivers (two-photon TIFF, Olympus BX, behavioral video)
└── Analysis defaults (spike sorting params, behavioral metrics)
```

### Chemistry (planned)

```
labclaw-chem plugin:
├── ReactionSampleNode (reagents, conditions, yield)
├── Sentinel rules (yield thresholds, safety alerts, temperature limits)
├── Hypothesis templates (structure-activity, reaction optimization)
├── Device drivers (HPLC CSV, spectrophotometer, balance)
└── Analysis defaults (peak detection, concentration curves)
```

### Materials Science (planned)

```
labclaw-materials plugin:
├── MaterialSampleNode (composition, processing, properties)
├── Sentinel rules (property thresholds, phase transition alerts)
├── Hypothesis templates (composition-property, processing-structure)
├── Device drivers (SEM TIFF, XRD CSV, tensile CSV)
└── Analysis defaults (peak fitting, stress-strain analysis)
```

### Genomics (planned)

```
labclaw-genomics plugin:
├── SequencingSampleNode (organism, library type, coverage)
├── Sentinel rules (quality scores, contamination alerts)
├── Hypothesis templates (differential expression, variant effects)
├── Device drivers (Illumina output, 10x Genomics, Nanopore)
└── Analysis defaults (QC thresholds, alignment params)
```

## Creating a Domain Plugin

```bash
# Scaffold a new domain plugin
labclaw plugin create my-domain

# Structure:
labclaw-my-domain/
├── pyproject.toml          # entry_points for labclaw.plugins.domain
├── src/
│   └── labclaw_my_domain/
│       ├── __init__.py     # DomainPlugin implementation
│       ├── nodes.py        # Custom GraphNode subclasses
│       ├── rules.py        # Sentinel rules
│       └── drivers/        # Device drivers (optional)
└── tests/
```

```python
# Minimal domain plugin (~50 lines)
from labclaw.plugins.base import PluginMetadata

class MyDomainPlugin:
    metadata = PluginMetadata(
        name="labclaw-my-domain",
        version="0.1.0",
        description="My science domain for LabClaw",
    )

    def sample_types(self):
        return [MySampleNode]

    def sentinel_rules(self):
        return [MyQualityRule()]

    def hypothesis_templates(self):
        return ["If {condition}, then {outcome} because {mechanism}"]

    def analysis_defaults(self):
        return {"correlation_threshold": 0.5}
```

## Community Contribution Model

```
Phase 1: Core team builds 3-4 domain packs (neuro, chem, bio, materials)
Phase 2: Template + docs enable community domain contributions
Phase 3: Domain Plugin Hub — searchable registry of community plugins
Phase 4: Cross-domain analysis — LabClaw finds patterns ACROSS domains
```

## Cross-Domain Discovery (v1.0+ vision)

The ultimate power of LabClaw: a lab running both chemistry and biology experiments where LabClaw discovers that a chemical compound (from chemistry data) correlates with a biological response (from biology data) — a cross-domain insight that siloed tools would never find.

```
Chemistry data ──┐
                 ├──► LabClaw Knowledge Graph ──► Cross-domain patterns
Biology data ────┘
```

This requires:
1. Shared knowledge graph (Tier B) across domains
2. Domain-aware embedding for cross-domain similarity
3. LLM-powered cross-domain hypothesis generation

## Contributing a Domain

See [plugin-development.md](plugin-development.md) for the full plugin development guide.

1. Fork the repo
2. `labclaw plugin create your-domain`
3. Implement `DomainPlugin` protocol
4. Add sample data + tests
5. Submit PR

We welcome domain experts who want to bring LabClaw to their field.
