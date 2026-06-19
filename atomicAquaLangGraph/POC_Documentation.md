# NovAtel GNSS Log Intelligence Agent — POC Documentation

**Project:** NovAtel OEM7 GNSS Telemetry Intelligence Platform  
**Version:** POC v1.0  
**Date:** June 2026  
**Prepared by:** Sravan  

---

## 1. Executive Summary

This document describes the design, development, and architecture of a **Proof of Concept (POC)** for a GNSS Telemetry Intelligence Agent built for NovAtel OEM7 receivers.

The system transforms the traditional approach of manually analyzing receiver log files into an **AI-powered diagnostic platform** that:

- Accepts NovAtel OEM7 log files (ASCII and binary formats)
- Automatically analyzes telemetry data across multiple log types
- Detects anomalies, interference events, positioning issues, and INS problems
- Provides natural language explanations of findings
- Answers documentation questions about NovAtel receivers

The core innovation is a **correlation-based architecture** where deterministic analysis tools compute all evidence first, and the LLM is used only for explanation — not for data analysis. This eliminates hallucination and ensures consistent, accurate results.

---

## 2. Problem Statement

### Current State (Before POC)

GNSS engineers analyzing NovAtel OEM7 receiver logs faced the following challenges:

| Problem | Impact |
|---|---|
| Manual log analysis requires deep NovAtel expertise | High time investment, specialized knowledge needed |
| Correlating across multiple log types (BESTPOS, RXSTATUS, TRACKSTAT) is tedious | Root causes often missed |
| No automated interference / jamming / spoofing detection | Security events go unnoticed |
| Standard chatbots hallucinate on hex values and bit fields | Unreliable answers on technical data |
| Binary log files require separate conversion tools | Workflow friction |

### Goal

Build a conversational AI assistant that can:

1. Ingest any NovAtel OEM7 log file
2. Answer analytical questions about the data
3. Detect and diagnose GNSS anomalies automatically
4. Answer documentation and configuration questions

---

## 3. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Frontend UI** | Streamlit (Python) | Web-based chat interface with file upload |
| **LLM** | AWS Bedrock — Claude Sonnet 4.6 | Natural language reasoning and explanation |
| **Knowledge Base** | AWS Bedrock Knowledge Bases | Vector search over NovAtel documentation |
| **Web Crawler** | Bedrock KB Web Crawler | Indexes docs.novatel.com |
| **Memory** | Bedrock AgentCore Memory | Cross-session conversation persistence |
| **Guardrails** | AWS Bedrock Guardrails | Content safety on input and output |
| **File Processing** | NovAtel EDIE library | Binary-to-ASCII log conversion |
| **Data Processing** | Pandas, Python | Log parsing, metrics computation |
| **Parallelism** | ThreadPoolExecutor | Concurrent tool execution |
| **Orchestration** | LangChain + custom pipeline | LLM invocation and message management |
| **Deployment** | Bedrock AgentCore | Production deployment entrypoint |
| **Streaming** | LangChain ChatBedrock SSE | Token-by-token response streaming |

---

## 4. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Browser)                           │
│                   Streamlit Chat Interface                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │  Upload File / Ask Question
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Correlation Pipeline                          │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   Domain    │  │  Evidence    │  │  Parallel Tool        │  │
│  │ Extraction  │→ │  Planner     │→ │  Execution (13 tools) │  │
│  │ (Keywords)  │  │ (Log check)  │  │  (ThreadPoolExecutor) │  │
│  └─────────────┘  └──────────────┘  └───────────┬───────────┘  │
│                                                  │              │
│  ┌──────────────────────┐  ┌────────────────────┐│              │
│  │  Diagnostic Rule     │  │  Semantic Event    ││              │
│  │  Engine (10 rules)   │← │  Engine (20+types) │←             │
│  └──────────┬───────────┘  └────────────────────┘              │
│             │                                                    │
│             ▼                                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              LLM Reasoning Layer (Claude Sonnet)         │   │
│  │  Receives: Diagnostics + Events + Metrics (JSON)         │   │
│  │  Produces: Natural language explanation (streamed)       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
  AWS Bedrock    AWS Bedrock    AWS Bedrock
  Knowledge      AgentCore      Guardrails
  Bases (KB)     Memory
```

### Pipeline Flow (Per Query)

```
User Query
    │
    ├── [Greeting / Off-topic] ──────────────────→ Instant response
    │
    ├── [Documentation question] ──────────────→ KB Search → LLM Synthesis → Stream
    │
    └── [Telemetry analysis] ──────────────────→ Full Pipeline:
              │
              ▼
         Phase 1: Domain Extraction
         (keyword matching, 9 domains, zero LLM)
              │
              ▼
         Phase 1b: Evidence Planning
         (domain → tool mapping, log availability check)
              │
              ▼
         Phase 2: Parallel Tool Execution
         (13 tools, ThreadPoolExecutor, structured JSON output)
              │
              ▼
         Phase 3: Semantic Event Generation
         (20+ event types, confidence scores, rule-based)
              │
              ▼
         Phase 4: Diagnostic Rule Engine
         (10 expert rules, named diagnoses, root cause chains)
              │
              ▼
         Phase 5: LLM Reasoning (single call)
         (receives Correlation JSON, streams explanation)
              │
              ▼
         Phase 5b: Response Formatting
         (severity header + LLM text + diagnostic cards + metrics)
```

---

## 5. Development Phases

### Phase 0 — Initial POC (Chatbot)

**What was built:**
- Basic Streamlit UI with file upload
- NovAtel ASCII log parser (regex-based)
- YAML-driven keyword-to-tool mapping (`use_cases_config.yaml`)
- Single-tool execution per query
- LLM-based answer formatting

**Architecture:**
```
Query → Keyword Match → Single Tool → LLM Format → Answer
```

**Limitations identified:**
- Could not correlate across multiple log types
- Keyword matching failed on unseen questions
- LLM hallucinated on raw telemetry data
- No root cause analysis capability

---

### Phase 1 — Domain Ontology and Evidence Planning

**Files created:**
- `src/domain_ontology.py`
- `src/evidence_planner.py`

**What was built:**

**Domain Ontology:** Defined 9 fixed telemetry domains:
| Domain | Coverage |
|---|---|
| positioning | Fix type, accuracy, RTK/INS state |
| satellite_tracking | Satellite count, visibility, constellations |
| signal_quality | C/No, signal strength, scintillation |
| interference | Jamming, spoofing, RF interference |
| corrections | Differential corrections, RTK base, correction age |
| receiver_status | Health, errors, warnings, antenna status |
| time | GPS time, UTC, time gaps |
| inertial | IMU, INS attitude, alignment |
| data_integrity | Log completeness, gaps, record counts |

**Tool Registry:** 13 tools registered with:
- Required log types (checked against file contents)
- Output field contracts
- Domain mappings
- Priority ordering

**Evidence Planner:** `build_execution_plan(query, available_logs)`:
- Extracts relevant domains from query via keyword matching
- Maps domains to tools via static registry
- Checks log availability before scheduling tool execution
- Returns `ExecutionPlan` with runnable/skipped tool lists

**Key principle:** Tool selection is 100% deterministic — zero LLM calls.

---

### Phase 2 — Multi-Tool Parallel Execution

**Files created:**
- `src/correlation_orchestrator.py`

**What was built:**

13 analysis tools, each returning structured JSON:

| Tool | Source Log | Output |
|---|---|---|
| bestpos_analyzer | BESTPOS | Fix type distribution, accuracy, satellite count, correction age |
| cn0_analyzer | TRACKSTAT | C/No stats, constellation/signal breakdown, reject code filtering |
| rxstatus_analyzer | RXSTATUS | Jamming, spoofing, antenna errors, status bit frequencies |
| itdetect_analyzer | ITDETECTSTATUS | RF interference events, spectrum detections, RF power |
| correction_age_analyzer | BESTPOS | Differential age stats, high-age events |
| satellite_count_analyzer | BESTPOS | Satellite count trends, drop events |
| ins_analyzer | INSPVA/INSPVAX | INS status timeline, attitude stats, first/last status timestamps |
| receiver_health_analyzer | RXSTATUS + HWMONITOR | Comprehensive health summary |
| time_analyzer | Any log | File time range, duration, time status |
| data_gap_analyzer | Any log | Gap detection, continuity percentage |
| log_inventory | Any log | Complete log type inventory with counts |
| satvis2_analyzer | SATVIS2 | Per-constellation satellite visibility |
| chanconfiglist_analyzer | CHANCONFIGLIST | Configured signal assignments |

**Fixed-schema Correlation JSON:**
```json
{
  "query": "...",
  "domains": ["positioning", "corrections"],
  "evidence": { "tool_id": { ...tool_output } },
  "events": [ { "event": "...", "severity": "...", "confidence": 0.95 } ],
  "metrics": { "avg_cn0": 42.5, "dominant_fix_type": "NARROW_INT" },
  "diagnostics": [ { "diagnostic_id": "...", "confidence": 0.97 } ],
  "unavailable_evidence": [ { "tool_id": "...", "reason": "..." } ],
  "execution_meta": { "tools_run": [...], "elapsed_seconds": 1.5 }
}
```

**LLM Reasoning Layer** (`src/reasoning_layer.py`):
- Single LLM call per query
- Receives Correlation JSON (pre-computed evidence)
- Streams explanation token-by-token

---

### Phase 3 — Semantic Event Generation

**Files created:**
- `src/semantic_event_engine.py`

**What was built:**

20+ semantic event types generated from tool outputs:

| Event | Source | Severity |
|---|---|---|
| JAMMING_DETECTED | RXSTATUS bit 15 | Critical |
| SPOOFING_DETECTED | RXSTATUS bit 9 | Critical |
| COMPOUND_INTERFERENCE_SIGNATURE | rxstatus + cn0 + bestpos correlation | Critical |
| RF_INTERFERENCE_DETECTED | ITDETECTSTATUS | High |
| ANTENNA_OPEN_CIRCUIT | RXSTATUS bit 5 | High |
| ANTENNA_SHORT_CIRCUIT | RXSTATUS bit 6 | High |
| CRITICALLY_LOW_SIGNAL_QUALITY | C/No < 30 dB-Hz | Critical |
| DEGRADED_SIGNAL_QUALITY | C/No < 35 dB-Hz | High |
| IONOSPHERIC_SCINTILLATION_SUSPECTED | C/No std_dev ≥ 5 | Medium |
| RTK_FLOAT_DOMINANT | >30% float records | Medium/High |
| POSITION_DEGRADED_TO_SINGLE | >20% single records | High |
| SATELLITE_DROP_EVENT | >30% count drop | Medium/High |
| HIGH_CORRECTION_AGE | avg age > 10s | Medium |
| CORRECTION_OUTAGE_DETECTED | max age > 30s | High |
| INS_NOT_CONVERGED | bad INS status dominant | High |
| DATA_GAPS_DETECTED | gaps in log | Medium/High |
| RTK_INSTABILITY_DIAGNOSED | float + correction age correlation | High |
| CORRECTION_LOSS_CAUSED_RTK_FLOAT | multi-source correlation | High |

Each event carries: `event`, `category`, `severity`, `confidence` (0.0–1.0), `description`, `evidence_refs`, `metrics`, `timestamp_first/last`.

**Cross-tool correlation events** identify patterns that require evidence from multiple tools simultaneously:
- `COMPOUND_INTERFERENCE_SIGNATURE` — jamming + low C/No + satellite loss together
- `RTK_INSTABILITY_DIAGNOSED` — float dominant + high correction age + satellite drops
- `CORRECTION_LOSS_CAUSED_RTK_FLOAT` — correction outage timing correlates with RTK float

---

### Phase 4 — Diagnostic Rule Engine

**Files created:**
- `src/diagnostic_engine.py`

**What was built:**

10 expert diagnostic rules, each producing a named diagnosis:

| Rule | Fires When | Confidence |
|---|---|---|
| ACTIVE_JAMMING_ATTACK | RXSTATUS bit 15 confirmed | 1.0 (firmware) |
| GNSS_SPOOFING_ATTACK | RXSTATUS bit 9 confirmed | 1.0 (firmware) |
| ANTENNA_HARDWARE_FAULT | Open or short circuit bits set | 1.0 |
| RTK_POSITION_INSTABILITY | Float dominant + root cause analysis | 0.90–0.98 |
| SIGNAL_QUALITY_DEGRADATION | C/No below threshold (non-jamming) | 0.90 |
| IONOSPHERIC_SCINTILLATION | C/No std_dev ≥ 5, no jamming | 0.60–0.90 |
| CORRECTION_SERVICE_OUTAGE | High correction age (standalone) | 0.93 |
| INS_ALIGNMENT_FAILURE | INS in bad/aligning state | 0.78–0.92 |
| DATA_COMPLETENESS_ISSUE | Significant data gaps | 1.0 |
| NOMINAL_OPERATION | No critical/high events | 0.85 |

Each diagnostic carries:
- `title` — short human-readable name
- `conclusion` — one-sentence finding
- `confidence` — 0.0–1.0
- `severity` — critical / high / medium / low
- `root_cause` — causal chain description
- `contributing_factors` — list of supporting evidence
- `recommended_actions` — deterministic engineer recommendations
- `evidence_refs` — traceable to specific tools and log fields
- `rule_id` — auditable rule identifier

---

### Phase 5 — Final LLM Synthesis and Response Formatting

**Files created:**
- `src/response_formatter.py`
- `src/doc_answering.py`

**What was built:**

**Response Formatter:** Structures every response with:
1. **Severity header** — `🔴 [CRITICAL] Active Jamming Attack Detected`
2. **LLM explanation** — streamed natural language analysis
3. **Diagnostic cards** — deterministic summary per diagnosis (confidence, factors, actions)
4. **Key metrics table** — relevant numbers from evidence
5. **Evidence footer** — which tools ran, what was missing, elapsed time

**Documentation Q&A module** (`doc_answering.py`):
- Classifies query as: `documentation` / `general_gnss` / `needs_log` / `off_topic`
- Documentation questions → KB search → LLM synthesis (never dumps raw chunks)
- General GNSS questions → LLM knowledge
- Off-topic / greetings → instant static response

---

## 6. Key Engineering Decisions

### Decision 1: Deterministic Tools, Not LLM Tool Calling

**Why:** LLM function calling adds latency (one LLM roundtrip per tool), is non-deterministic, and can miss relevant tools. Our approach: Python code selects tools based on domain mapping, then calls them directly.

**Impact:** Tool selection takes <1ms vs 2-3s per LLM tool-selection call. Results are reproducible.

### Decision 2: Separation of Evidence and Explanation

**Why:** LLMs hallucinate when given raw telemetry (hex values, bit fields, statistical data). By pre-computing all evidence and giving the LLM only structured JSON with named findings, hallucination is eliminated on factual data.

**Impact:** Answer accuracy on factual questions (satellite count, C/No values, fix type distribution) is 100% deterministic.

### Decision 3: Fixed Correlation JSON Schema

**Why:** Without a fixed schema, the LLM reasoning prompt is unstable. A fixed schema means the LLM always knows where to find diagnostics, events, metrics, and missing evidence.

**Impact:** Consistent LLM prompting regardless of which tools ran or what evidence was found.

### Decision 4: Single LLM Call Per Query

**Why:** Each additional LLM call adds 8-15 seconds of latency. The entire pipeline from domain extraction through diagnostic rules produces all necessary evidence. Only one LLM call is needed to explain pre-computed findings.

**Impact:** Total latency: 2-3s (tool execution) + 8-15s (LLM streaming) = 10-18s total. User sees first token at ~3s.

### Decision 5: Streaming UI

**Why:** 12-16 second total response time feels slow if the user stares at a spinner. Streaming tokens from second 3 onwards makes perceived latency much lower.

**Impact:** User experience significantly improved — response builds progressively rather than appearing all at once.

---

## 7. GNSS Expert Rules and Thresholds

All thresholds are based on NovAtel OEM7 field experience and industry standards. Validated against NovAtel's production NAS UI source code.

| Metric | Warning Threshold | Critical Threshold | Source |
|---|---|---|---|
| C/No | < 35 dB-Hz | < 30 dB-Hz | NovAtel NAS UI |
| C/No std_dev (scintillation) | ≥ 5 dB-Hz | — | Industry standard |
| Correction age | > 10 seconds | > 30 seconds | NovAtel OEM7 manual |
| Satellite drop | > 30% in one epoch | — | Expert knowledge |
| Min satellites for RTK | < 5 | < 4 | GNSS RTK requirement |
| RTK float percentage | > 30% | > 60% | Expert knowledge |
| Data continuity | < 95% | — | Operational standard |
| Lock time (stable channel) | < 30 seconds | — | NovAtel NAS UI |

---

## 8. Log Types Supported

The system supports analysis of the following NovAtel OEM7 log types:

| Log | Analysis Capability |
|---|---|
| BESTPOS / BESTPOSA | Fix type, accuracy, satellite count, correction age |
| TRACKSTAT / TRACKSTATA | C/No, constellation/signal breakdown, reject codes, lock time |
| RXSTATUS / RXSTATUSA | Jamming, spoofing, antenna faults, all status bits |
| ITDETECTSTATUS / ITDETECTSTATUSA | RF interference spectrum analysis |
| INSPVA / INSPVAX / INSPVAXA | INS status timeline, attitude, alignment state |
| SATVIS2 / SATVIS2A | Per-constellation satellite visibility |
| CHANCONFIGLIST / CHANCONFIGLISTA | Configured signal assignments |
| BESTVEL / BESTVELA | Velocity analysis |
| HWMONITOR / HWMONITORA | Hardware health monitoring |
| Any log | Time range, data gaps, log inventory |

**Binary file support:** Binary NovAtel logs are automatically converted to ASCII using the NovAtel EDIE library before processing.

---

## 9. File Structure

```
atomicAquaLangGraph/
├── streamlit_app.py              ← Web UI (Streamlit)
├── gnss_knowledge_base.md        ← GNSS knowledge context
├── .env                          ← AWS configuration
├── requirements.txt
└── src/
    ├── main.py                   ← Entrypoint, routing, pipeline orchestration
    ├── domain_ontology.py        ← Phase 1: Domain vocabulary + tool registry
    ├── evidence_planner.py       ← Phase 1: Query → execution plan
    ├── correlation_orchestrator.py ← Phase 2: Tool execution + JSON assembly
    ├── semantic_event_engine.py  ← Phase 3: Semantic event generation
    ├── diagnostic_engine.py      ← Phase 4: Expert diagnostic rules
    ├── reasoning_layer.py        ← Phase 5: LLM synthesis
    ├── response_formatter.py     ← Phase 5: Structured output formatting
    ├── doc_answering.py          ← Documentation Q&A module
    └── model/
        └── load.py               ← AWS Bedrock model configuration
```

---

## 10. AWS Services Used

| Service | Configuration | Purpose |
|---|---|---|
| Bedrock Runtime | us-east-1, Claude Sonnet 4.6 | LLM inference and streaming |
| Bedrock Knowledge Bases | KB ID: FH00WKSBPL, us-west-2 | NovAtel documentation vector search |
| Bedrock KB Web Crawler | docs.novatel.com/OEM7/* | Documentation indexing |
| Bedrock AgentCore | BedrockAgentCoreApp | Production deployment entrypoint |
| Bedrock AgentCore Memory | MEMORY_ID (env var) | Conversation history persistence |
| Bedrock Guardrails | ID: gcorc7d9sd08, us-west-2 | Content safety |
| S3 | S3_BUCKET (env var), ap-south-1 | Large file storage (>5MB) |

---

## 11. Sample Interactions

### Example 1: Interference Detection

**User:** "Is there jamming in this file?"

**System flow:**
1. Domain: `interference` → Tools: `rxstatus_analyzer`, `itdetect_analyzer`
2. RXSTATUS analyzer detects bit 15 set in 12 records
3. ITDETECTSTATUS analyzer finds 8 spectrum analysis events
4. Semantic engine generates: `JAMMING_DETECTED` (conf: 1.0), `COMPOUND_INTERFERENCE_SIGNATURE` (conf: 0.97)
5. Diagnostic engine fires: `ACTIVE_JAMMING_ATTACK` (conf: 1.0)
6. LLM explains with root cause and recommended actions

**Response includes:**
- 🔴 [CRITICAL] severity header
- Explanation of jamming detection with timestamps
- Diagnostic card with contributing factors and 5 recommended actions
- Metrics table: jamming_event_count, avg_cn0, min_satellites

---

### Example 2: RTK Instability Root Cause

**User:** "Why did RTK become unstable?"

**System flow:**
1. Domain: `positioning`, `corrections` → 4 tools run in parallel
2. BESTPOS analyzer: 55% float, max correction age 42s
3. Correction age analyzer: 25% of records with high age
4. Semantic engine generates: `RTK_FLOAT_DOMINANT`, `CORRECTION_LOSS_CAUSED_RTK_FLOAT`
5. Diagnostic engine fires: `RTK_POSITION_INSTABILITY` with root cause chain
6. LLM explains the causal relationship

---

### Example 3: Documentation Question

**User:** "How do I configure PPP on OEM7?"

**System flow:**
1. No domains matched (not a telemetry question)
2. Classified as `documentation`
3. KB search retrieves PPP-related chunks from NovAtel docs
4. LLM synthesizes complete step-by-step configuration guide
5. Response includes actual OEM7 commands

---

## 12. Performance Metrics (POC)

| Metric | Value |
|---|---|
| Tool execution time (parallel) | 1.5–3 seconds |
| LLM streaming latency (first token) | ~3 seconds from query |
| Total response time | 10–18 seconds |
| Supported log file size | Up to 350 MB |
| Max parallel tools | 4 (ThreadPoolExecutor) |
| LLM calls per query | 1 (always) |
| Deterministic phases | Phases 1–4 (0 LLM calls) |

---

## 13. Known Limitations (POC Scope)

| Limitation | Impact | Proposed Solution |
|---|---|---|
| Tools re-compute on every query | Latency per query | Pre-compute all tools at upload time, cache Correlation JSON |
| In-memory log store | Single process only | Move to Redis/DynamoDB for multi-instance deployment |
| No temporal correlation | Cannot detect "event A caused event B 5s later" | Build event timeline with timestamps |
| Knowledge base has partial content | Some NovAtel questions not answered | Complete web crawler indexing of docs.novatel.com |
| Binary log conversion requires EDIE | Dependency on NovAtel library | Pre-convert files before upload as alternative |

---

## 14. Next Steps (Post-POC)

### Priority 1: Precomputation at Upload
Run all 13 analysis tools once when the file is uploaded, cache the full Correlation JSON. On subsequent queries, reuse cached evidence and only invoke the LLM reasoning layer. Expected latency reduction: 60–70%.

### Priority 2: Temporal Event Correlation
Store events with GPS timestamps and detect temporal patterns — e.g., satellite drop at T=100s followed by RTK loss at T=102s. This enables timeline-based root cause analysis.

### Priority 3: Production Deployment
- Docker container packaging
- AWS ECS/EKS deployment via Bedrock AgentCore
- CloudWatch monitoring for latency and error rates
- Redis for session state (multi-instance support)

### Priority 4: Evaluation Framework
Implement automated accuracy evaluation using:
- DeepEval/Ragas for answer faithfulness and relevance
- Ground truth dataset from known log scenarios
- Regression testing for diagnostic rule accuracy

---

## 15. Conclusion

The POC successfully demonstrates that a **correlation-based telemetry intelligence architecture** outperforms a traditional LLM chatbot for GNSS log analysis in three key areas:

1. **Accuracy** — Deterministic tools compute all metrics, eliminating LLM hallucination on factual data
2. **Explainability** — Every diagnostic is traced to specific tools, log fields, and rule IDs
3. **Unseen question support** — Domain-based routing handles questions the system was never explicitly trained on

The system is ready for production hardening with the improvements outlined in Section 14.

---

*End of POC Documentation*
