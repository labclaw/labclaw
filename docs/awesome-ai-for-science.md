# Awesome AI for Science — LabClaw Integration Stack

> High-quality tools, MCP servers, skills, APIs, and agents that LabClaw integrates with or builds upon. Curated for quality — every entry is production-ready or widely adopted.

---

## Contents

- [Agent Platforms & Skills](#agent-platforms--skills)
- [MCP Servers](#mcp-servers)
- [Neuroscience Tools](#neuroscience-tools)
- [Data APIs](#data-apis)
- [Lab Automation](#lab-automation)
- [Foundation Models](#foundation-models)
- [Autonomous Science Agents](#autonomous-science-agents)
- [Benchmarks](#benchmarks)
- [Related Awesome Lists](#related-awesome-lists)
- [How LabClaw Uses This Stack](#how-labclaw-uses-this-stack)

---

## Agent Platforms & Skills

### Anthropic Life Sciences (Official)

> From [anthropic.com/life-sciences](https://www.anthropic.com/news/claude-for-life-sciences) — official MCP servers and skills.

| Type | Name | Function |
|------|------|----------|
| MCP | **PubMed** | Search 36M+ biomedical articles |
| MCP | **BioRender** | Scientific illustrations and templates |
| MCP | **Synapse** | Collaborative research data (Sage Bionetworks) |
| MCP | **Wiley Scholar Gateway** | Peer-reviewed scientific publications |
| MCP | **10x Genomics** | Single-cell and spatial genomics (local MCP) |
| Connector | **bioRxiv/medRxiv** | Search preprints (announced, Claude web product) |
| Connector | **ChEMBL** | Bioactive molecules (announced, Claude web product) |
| Connector | **ClinicalTrials.gov** | Clinical trial registry (announced, Claude web product) |
| Connector | **Open Targets** | Target-disease associations (announced, Claude web product) |
| Skill | `single-cell-rna-qc` | scRNA-seq quality control pipeline |
| Skill | `scvi-tools` | Deep generative single-cell analysis |
| Skill | `nextflow-development` | Bioinformatics pipeline development |
| Skill | `instrument-data-to-allotrope` | Convert instrument data to Allotrope format |

**Key partnerships:** Allen Institute (multi-agent neuroscience), HHMI/Janelia (connectomics), DOE Genesis (17 national labs)

### K-Dense Scientific Skills

> From [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) — 147+ skills, MIT license, ![Stars](https://img.shields.io/github/stars/K-Dense-AI/claude-scientific-skills?style=flat-square)

**P0 — Core for LabClaw** (daily use in discovery pipeline):

| Skill | Why It Matters |
|-------|----------------|
| `scikit-learn` | ML backbone for pattern mining and classification |
| `statsmodels` | Statistical testing in validation step |
| `scipy` | Core scientific computing (already a dependency) |
| `plotly` | Interactive visualization in dashboard |
| `numpy` / `polars` | Data processing (already dependencies) |
| `umap-learn` | Dimensionality reduction in unsupervised discovery |
| `pymc` | Bayesian modeling in optimization step |
| `shap` | Model interpretability for CONCLUDE step |
| `networkx` | Knowledge graph analysis, connectivity |
| `neurokit2` | Biosignal processing (EEG, EMG, EDA) |

**P1 — Domain Extensions** (per-lab activation):

| Skill | Domain |
|-------|--------|
| `scanpy` + `anndata` + `scvi-tools` | Single-cell RNA-seq |
| `biopython` + `gget` + `bioservices` | Bioinformatics queries |
| `deepchem` + `rdkit` | Molecular ML / drug discovery |
| `esm` | Protein language models |
| `pymatgen` | Materials science |
| `pytorch-lightning` + `transformers` | Deep learning |

**P2 — Scientific Workflows** (agent-invoked):

| Skill | Function |
|-------|----------|
| `scientific-writing` | Paper drafting from discovery results |
| `literature-review` | Systematic review for hypothesis context |
| `hypothesis-generation` | Structured hypothesis formulation |
| `statistical-analysis` | Guided statistical testing |
| `exploratory-data-analysis` | Comprehensive EDA |
| `citation-management` | Reference management |
| `research-grants` | Grant proposal writing |

**P2 — Database Skills** (API wrappers, use via skills or direct API):

| Skill | Database | Records |
|-------|----------|---------|
| `pubmed-database` | PubMed | 36M+ articles |
| `openalex-database` | OpenAlex | 250M+ works |
| `uniprot-database` | UniProt | 250M+ proteins |
| `chembl-database` | ChEMBL | 2.4M+ compounds |
| `ensembl-database` | Ensembl | Genome annotations |
| `string-database` | STRING | PPI networks |
| `kegg-database` | KEGG | Pathways, reactions |
| `geo-database` | GEO | Gene expression data |
| `clinvar-database` | ClinVar | Variant interpretations |
| `biorxiv-database` | bioRxiv | Preprints |

**P2 — Lab Platform Integrations**:

| Skill | Platform | Why |
|-------|----------|-----|
| `benchling-integration` | Benchling R&D | ELN integration |
| `opentrons-integration` | Opentrons robots | Liquid handling |
| `omero-integration` | OMERO | Microscopy data management |
| `protocolsio-integration` | protocols.io | Protocol sharing |

## MCP Servers

> Community and official MCP servers. Only listing servers with 50+ stars or official backing.

### Literature (highest priority for discovery engine)

| Server | Stars | Install | Why |
|--------|-------|---------|-----|
| **[arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)** | 1.9K+ | `uvx arxiv-mcp-server` | Primary paper search for HYPOTHESIZE step |
| **[mcp.science](https://github.com/pathintegral-institute/mcp.science)** | 110+ | `npx @mcp.science/server` | Unified science search (Semantic Scholar + arXiv + PubMed) |

### Infrastructure

| Server | Stars | Install | Why |
|--------|-------|---------|-----|
| **[github-mcp-server](https://github.com/github/github-mcp-server)** | 27K+ | Official | Code search, issue tracking |
| **[jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server)** | 900+ | pip | Notebook execution for analysis |

## Neuroscience Tools

> The core tool ecosystem LabClaw orchestrates. Only battle-tested tools with active maintenance.

### Behavior Tracking (OBSERVE step)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[DeepLabCut](https://github.com/DeepLabCut/DeepLabCut)** | 5.5K | Markerless multi-animal pose estimation | Output → edge watcher → NWB |
| **[SLEAP](https://github.com/talmolab/sleap)** | 550+ | Multi-animal pose tracking (top-down + bottom-up) | Output → edge watcher → NWB |

### Behavioral Analysis (ASK step)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[keypoint-MoSeq](https://github.com/dattalab/keypoint-moseq)** | 100+ | Unsupervised behavioral syllable discovery | Pose → syllables → pattern mining |
| **[SimBA](https://github.com/sgoldenlab/simba)** | 300+ | Social interaction classifiers | Behavior labels → correlations |
| **[B-SOiD](https://github.com/YttriLab/B-SOID)** | 200+ | Unsupervised behavior segmentation | Pose → clusters → mining |
| **[Pynapple](https://github.com/pynapple-org/pynapple)** | 330+ | Neural time series analysis | Time series → temporal patterns |

### Electrophysiology (OBSERVE step)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[SpikeInterface](https://github.com/SpikeInterface/spikeinterface)** | 700+ | Unified spike sorting (10+ backends) | Raw → sorted spikes → NWB |
| **[Kilosort4](https://github.com/MouseLand/Kilosort)** | 590+ | GPU-accelerated spike sorting | Via SpikeInterface |
| **[MNE-Python](https://github.com/mne-tools/mne-python)** | 3.2K | MEG/EEG full pipeline | EEG → features → mining |

### Calcium Imaging (OBSERVE step)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[Suite2p](https://github.com/MouseLand/suite2p)** | 420+ | Two-photon imaging pipeline | Raw → ROIs → NWB |
| **[CaImAn](https://github.com/flatironinstitute/CaImAn)** | 710+ | CNMF calcium analysis | Raw → traces → NWB |
| **[Cellpose](https://github.com/MouseLand/cellpose)** | 2.1K+ | Generalist cell segmentation | Images → masks → quantification |

### NWB Ecosystem (data standard)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[PyNWB](https://github.com/NeurodataWithoutBorders/pynwb)** | 200+ | NWB file read/write | Core data format for LabClaw |
| **[NeuroConv](https://github.com/catalystneuro/neuroconv)** | 70+ | 47+ formats → NWB conversion | Edge node format standardization |
| **[HDMF](https://github.com/hdmf-dev/hdmf)** | 50+ | Hierarchical data modeling framework | PyNWB backend |

### Hardware Control (EXPERIMENT step)

| Tool | Stars | Description | Integration |
|------|-------|-------------|-------------|
| **[PyVISA](https://github.com/pyvisa/pyvisa)** | 910+ | VISA instrument control | Device manager adapter |
| **[NI-DAQmx](https://github.com/ni/nidaqmx-python)** | 550+ | National Instruments DAQ | Hardware I/O adapter |
| **[Pycro-Manager](https://github.com/micro-manager/pycro-manager)** | 170+ | Microscope control | Microscope device adapter |

## Data APIs

> APIs that LabClaw agents query for context, literature, and cross-referencing.

### Neuroscience Data (P0)

| API | Content | Auth | Client | Why |
|-----|---------|------|--------|-----|
| **[DANDI Archive](https://api.dandiarchive.org/)** | 790+ dandisets | API key (free) | `dandi` | Reference datasets for benchmarking |
| **[Allen Brain Observatory](https://allensdk.readthedocs.io/)** | Visual coding, connectivity | None | `allensdk` | Cross-reference neural data |
| **[OpenNeuro](https://openneuro.org/)** | 1,800+ BIDS datasets | None | `openneuro-py` | Public neuro datasets |

### Literature (P0)

| API | Content | Rate | Client | Why |
|-----|---------|------|--------|-----|
| **[Semantic Scholar](https://api.semanticscholar.org/)** | 200M+ papers | 10/sec (key) | `semanticscholar` | Citation graph for hypothesis context |
| **[OpenAlex](https://docs.openalex.org/)** | 250M+ works | 100K/day | `pyalex` | Broad literature search |
| **[NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/)** | 36M+ PubMed | 10/sec (key) | `biopython` | Biomedical literature |

### Biology (P1)

| API | Content | Client | Why |
|-----|---------|--------|-----|
| **[UniProt](https://www.uniprot.org/help/api)** | 250M+ proteins | `httpx` | Protein annotations |
| **[STRING](https://string-db.org/help/api/)** | PPI networks | `httpx` | Interaction context |
| **[Ensembl](https://rest.ensembl.org/)** | Genome annotations | `httpx` | Gene info |

## Lab Automation

> Lab OS and orchestration platforms — LabClaw's peers and integration targets.

| Platform | Stars | Description | Relation to LabClaw |
|----------|-------|-------------|---------------------|
| **[AlabOS](https://github.com/CederGroupHub/alabos)** | — | SDL orchestration (LBNL) | Peer — hardware orchestration layer |
| **[PyLabRobot](https://github.com/PyLabRobot/pylabrobot)** | 370+ | Vendor-agnostic liquid handling | Integration target for EXPERIMENT step |
| **[Opentrons](https://github.com/Opentrons/opentrons)** | 490+ | Open-source liquid handling robots | Hardware target |
| **[Bonsai](https://github.com/bonsai-rx/bonsai)** | 180 | Real-time data stream processing | Edge node integration |

## Foundation Models

> Models that LabClaw agents can call for domain-specific reasoning.

| Model | Domain | Access | Why |
|-------|--------|--------|-----|
| **[ESM-3](https://github.com/facebookresearch/esm)** | Protein sequences | Open weights | Protein function prediction |
| **[scGPT](https://github.com/bowang-lab/scGPT)** | Single-cell multi-omics | Open weights | Cell type annotation |
| **[Geneformer](https://huggingface.co/ctheodoris/Geneformer)** | Single-cell genomics | Open weights | Gene network inference |
| **[AlphaFold 3](https://alphafoldserver.com/)** | Protein structure | Server API | Structure prediction |

## Autonomous Science Agents

> Reference implementations — what LabClaw learns from and differentiates against.

| Agent | Approach | Key Innovation | Open Source |
|-------|----------|----------------|-------------|
| **[AI Scientist v2](https://github.com/SakanaAI/AI-Scientist)** | End-to-end research pipeline | Idea → experiment → paper → review | Yes (Apache-2.0) |
| **[Robin](https://arxiv.org/abs/2505.13400)** (FutureHouse) | Multi-agent drug discovery | Multi-agent pipeline with candidate nomination | No |
| **[Coscientist](https://github.com/gomesgroup/coscientist)** | LLM + robotic chemistry | GPT-4 planned & executed synthesis | Source-available (Apache-2.0 + Commons Clause) |
| **[PaperQA2](https://github.com/Future-House/paper-qa)** | RAG literature agent | Answers with citations, 200M+ papers | Yes (Apache-2.0) |
| **[MARS](https://doi.org/10.1016/j.matt.2025.102577)** | 19 agents + 16 tools | Hierarchical multi-agent materials discovery | No |
| **[DOLPHIN](https://arxiv.org/abs/2501.03916)** | Closed-loop scientific method | LLM generates → experiments → evaluates → iterates | Yes |
| **[Google AI Co-Scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/)** | Multi-agent reasoning | Tournament-style hypothesis ranking | No |

**LabClaw's design combines:** (1) 24/7 self-evolution, (2) three-tier persistent memory, (3) hardware-software full stack, (4) neuroscience specialization, (5) complete scientific method loop.

## Benchmarks

| Benchmark | Tasks | Best Score | Link |
|-----------|-------|------------|------|
| **[ScienceAgentBench](https://github.com/OSU-NLP-Group/ScienceAgentBench)** | 102 tasks, 4 disciplines | 42.2% (o1-preview) | [Leaderboard](https://hal.cs.princeton.edu/scienceagentbench) |
| **[FrontierScience](https://openai.com/index/frontierscience/)** | AI scientific reasoning | — | OpenAI |
| **[MLAgentBench](https://arxiv.org/abs/2310.03302)** | 13 ML experimentation tasks | — | arXiv |

## Related Awesome Lists

> Curated lists we reference and contribute to. Sorted by relevance to LabClaw.

### Direct Relevance

| List | Stars | Focus | Last Active |
|------|-------|-------|-------------|
| **[awesome-self-driving-labs](https://github.com/AccelerationConsortium/awesome-self-driving-labs)** | 209 | Self-driving labs (chemistry/materials) | 2025-10 |
| **[awesome-ai-for-science](https://github.com/ai-boost/awesome-ai-for-science)** | 1.3K | Broad AI+Science tools and papers | 2026-02 |
| **[Awesome-Self-Evolving-Agents](https://github.com/EvoAgentX/Awesome-Self-Evolving-Agents)** | 1.8K | Self-evolving agent architectures | 2025-10 |
| **[Awesome-LLM-Scientific-Discovery](https://github.com/HKUST-KnowComp/Awesome-LLM-Scientific-Discovery)** | 299 | 3-level autonomy framework for LLM scientists | 2025-11 |
| **[Awesome-AI-Scientists](https://github.com/tsinghua-fib-lab/Awesome-AI-Scientists)** | 25 | Full-pipeline AI scientist systems | 2025-12 |
| **[Awesome-AI-Scientist-Papers](https://github.com/openags/Awesome-AI-Scientist-Papers)** | 126 | Robot scientist lineage papers | 2025-09 |

### Neuroscience

| List | Stars | Focus | Last Active |
|------|-------|-------|-------------|
| **[awesome-neuroscience](https://github.com/analyticalmonk/awesome-neuroscience)** | 1.6K | Full-stack neuroscience tools | 2024-10 |
| **[awesome-neurofm](https://github.com/mazabou/awesome-neurofm)** | 78 | Neural foundation models (POYO, NDT2) | 2025-12 |
| **[awesome-neural-geometry](https://github.com/neurreps/awesome-neural-geometry)** | 1.1K | Geometric deep learning + neuroscience | 2026-02 |
| **[ElectrophysiologySoftware](https://github.com/openlists/ElectrophysiologySoftware)** | 126 | EEG/MEG/ECoG tools | 2025-02 |
| **[awesome-computational-neuroscience](https://github.com/sakimarquis/awesome-computational-neuroscience)** | 50 | Computational neuroscience theory | 2024-07 |

### Life Sciences & Biology

| List | Stars | Focus | Last Active |
|------|-------|-------|-------------|
| **[Awesome-Bioinformatics](https://github.com/danielecook/Awesome-Bioinformatics)** | 3.9K | Bioinformatics CLI tools | 2025-03 |
| **[awesome-single-cell](https://github.com/seandavi/awesome-single-cell)** | 3.7K | Single-cell genomics (300+ tools) | 2026-02 |
| **[Awesome-Scientific-Language-Models](https://github.com/yuzhimanhua/Awesome-Scientific-Language-Models)** | 641 | 260+ domain-specific scientific LLMs | 2025-06 |
| **[awesome-computational-biology](https://github.com/inoue0426/awesome-computational-biology)** | 120 | Broad computational biology | 2026-02 |
| **[awesome-bioie](https://github.com/caufieldjh/awesome-bioie)** | 417 | Biomedical NLP / information extraction | 2024-05 |

### Chemistry & Materials

| List | Stars | Focus | Last Active |
|------|-------|-------|-------------|
| **[awesome-python-chemistry](https://github.com/lmmentel/awesome-python-chemistry)** | 1.4K | Python chemistry packages | 2025-09 |
| **[best-of-atomistic-machine-learning](https://github.com/JuDFTteam/best-of-atomistic-machine-learning)** | 618 | 510 projects, auto-ranked by quality | 2026-02 |
| **[awesome-cheminformatics](https://github.com/hsiaoyi0504/awesome-cheminformatics)** | 836 | Cheminformatics tools | 2024-03 |
| **[awesome-materials-informatics](https://github.com/tilde-lab/awesome-materials-informatics)** | 491 | Materials databases + ML | 2025-08 |

### Drug Discovery & Protein Design

| List | Stars | Focus | Last Active |
|------|-------|-------|-------------|
| **[papers_for_protein_design_using_DL](https://github.com/Peldom/papers_for_protein_design_using_DL)** | 1.9K | 500+ protein design papers | 2026-02 |
| **[papers-for-molecular-design-using-DL](https://github.com/AspirinCode/papers-for-molecular-design-using-DL)** | 920 | 400+ molecular design papers | 2026-02 |
| **[awesome-drug-discovery](https://github.com/yboulaamane/awesome-drug-discovery)** | 97 | Computational drug discovery | 2025-11 |

### Research Institutions

| List | Source | Focus |
|------|--------|-------|
| **[awesome-janelia-software](https://github.com/JaneliaSciComp/awesome-janelia-software)** | HHMI/Janelia | Connectomics, research infra |
| **[Allen Institute Open Tools](https://alleninstitute.org/open-science-tools/)** | Allen Institute | Brain atlases, SDKs |

---

## How LabClaw Uses This Stack

```
OBSERVE  ─→  DeepLabCut/SLEAP → SpikeInterface → Suite2p
              │ edge watchers ingest outputs, convert via NeuroConv → NWB
              ▼
ASK      ─→  Pattern mining (scikit-learn, scipy, statsmodels)
              │ keypoint-MoSeq for behavior syllables
              │ MCP servers (arxiv, pubmed) for literature context
              ▼
HYPOTHESIZE → Claude API + K-Dense hypothesis-generation skill
              │ Semantic Scholar API for citation context
              ▼
PREDICT  ─→  PyMC (Bayesian), scikit-learn (predictive models)
              │ SHAP for interpretability
              ▼
EXPERIMENT → PyLabRobot / Opentrons (liquid handling)
              │ PyVISA / NI-DAQmx (instruments)
              │ Pycro-Manager (microscopes)
              ▼
ANALYZE  ─→  Domain tools (Pynapple, MNE-Python, CaImAn)
              │ K-Dense EDA + statistical-analysis skills
              ▼
CONCLUDE ─→  Validation (cross-val, provenance)
              │ K-Dense scientific-writing skill for reports
              │ NWB export via PyNWB for reproducibility
```

---

## License

Apache-2.0 — Part of [LabClaw](https://github.com/labclaw/labclaw)
