"""
doc_answering.py — Documentation & Knowledge Q&A (no log file required)

Pipeline position:
  User Query (no file) → [THIS MODULE] → Final Response

This module handles all questions when NO log file is loaded:
  1. Classifies the question type (documentation / general GNSS / off-topic / needs-log)
  2. Routes documentation questions through KB retrieval + synthesis
  3. Answers general GNSS questions from LLM knowledge
  4. Politely declines off-topic questions
  5. Tells user to upload a log if the question needs telemetry data

KEY PRINCIPLE:
  Never dump raw KB chunks at the user.
  Always synthesize a proper answer from retrieved content.
  If KB has no relevant content, say so — don't hallucinate.
"""

from __future__ import annotations
import time


# ═══════════════════════════════════════════════════════════════════
# QUERY CLASSIFICATION
# Deterministic keyword-based — no LLM call needed for routing.
# ═══════════════════════════════════════════════════════════════════

# Keywords that indicate the question needs a LOG FILE to answer
_NEEDS_LOG_KEYWORDS = {
    "my file", "this file", "uploaded", "in the file", "in my log",
    "in the log", "analyze", "check my", "from my", "my data",
    "log file", "do i have", "do we have", "is there any",
    "show me", "list all", "how many records", "time range",
}

# Keywords that indicate NovAtel/GNSS DOCUMENTATION question
_DOC_KEYWORDS = {
    "what is", "what are", "explain", "define", "definition",
    "how does", "how do", "difference between", "describe",
    "meaning of", "purpose of", "format of", "structure of",
    "fields in", "message format", "log format", "command",
    "configure", "configuration", "parameter", "syntax",
    "novatel", "oem7", "oem6", "bestpos", "rxstatus", "trackstat",
    "inspva", "heading2", "range", "satvis", "rtcm", "rinex",
    "nmea", "gpgga", "gprmc", "sbas", "waas", "rtk",
    "ppp", "corrections", "base station", "rover",
    "gnss", "gps", "glonass", "galileo", "beidou",
    "antenna", "multipath", "ionosphere", "troposphere",
    "pdop", "hdop", "gdop", "dilution of precision",
    "ambiguity", "integer ambiguity", "float solution",
    "l1", "l2", "l5", "dual frequency", "multi frequency",
}

# Keywords that are clearly off-topic
_OFF_TOPIC_INDICATORS = {
    "weather", "stock", "recipe", "movie", "music", "sports",
    "politics", "news", "joke", "poem", "story", "code",
    "python", "javascript", "java", "c++", "html",
    "write me", "generate code", "help me with",
}


def classify_query(question: str) -> str:
    """
    Classify a no-file query into one of:
      - "needs_log"    : requires uploaded telemetry data
      - "documentation": NovAtel/GNSS documentation question → use KB
      - "general_gnss" : general GNSS concept → LLM knowledge is fine
      - "off_topic"    : unrelated to GNSS/NovAtel → politely decline

    Returns classification string.
    """
    q_lower = question.lower()

    # Check needs-log first
    for kw in _NEEDS_LOG_KEYWORDS:
        if kw in q_lower:
            return "needs_log"

    # Check off-topic
    for kw in _OFF_TOPIC_INDICATORS:
        if kw in q_lower:
            return "off_topic"

    # Check documentation
    doc_score = sum(1 for kw in _DOC_KEYWORDS if kw in q_lower)
    if doc_score >= 1:
        return "documentation"

    # Default: treat as general GNSS if it has any technical-sounding words
    _general_gnss = {"satellite", "signal", "receiver", "position", "navigation",
                     "fix", "accuracy", "frequency", "carrier", "pseudorange",
                     "ephemeris", "almanac", "clock", "orbit", "measurement"}
    if any(kw in q_lower for kw in _general_gnss):
        return "general_gnss"

    # If nothing matches — still try documentation (benefit of the doubt)
    return "documentation"


# ═══════════════════════════════════════════════════════════════════
# KB-BASED DOCUMENTATION ANSWERING
# ═══════════════════════════════════════════════════════════════════

_DOC_SYNTHESIS_PROMPT = """You are a NovAtel OEM7 GNSS technical documentation expert.

Answer the user's question as completely as possible. Use the reference material provided below as your PRIMARY source. If the reference material only partially covers the question, supplement with your knowledge of NovAtel OEM7 receiver configuration and GNSS systems.

RULES:
- Prioritize information from the reference material — cite specific field names, bit positions, commands, and values from it.
- If the reference material is insufficient for a complete answer, use your general knowledge of NovAtel OEM7 commands and procedures to fill in the gaps.
- For configuration/setup questions: provide step-by-step procedures with actual OEM7 commands.
- For log/message questions: describe purpose, key fields with indices, units, and typical values.
- Be practical and actionable — engineers need commands they can type, not just descriptions.
- Structure your answer with clear headers and numbered steps for procedures.
- Include example commands using realistic parameter values.
- If you are supplementing beyond the reference material, do so seamlessly — do not break the flow to say "this is from general knowledge."
- Never invent non-existent OEM7 commands. Stick to real NovAtel command syntax.

USER QUESTION:
{question}

REFERENCE MATERIAL (from NovAtel Knowledge Base):
{kb_content}

Now provide your complete answer:"""


_GENERAL_GNSS_PROMPT = """You are a NovAtel OEM7 GNSS expert assistant with deep knowledge of receiver configuration, GNSS positioning, and NovAtel command syntax.

Answer the following question thoroughly and practically. If it's about configuration or setup, provide step-by-step procedures with actual OEM7 commands. If it's conceptual, explain clearly with relevant technical details.

Be specific to NovAtel OEM7 where applicable — use real command names (FRESET, LOG, PPPSOURCE, etc.) and realistic parameters.

Question: {question}

Provide a complete, actionable answer:"""


_NEEDS_LOG_RESPONSE = """This question requires an uploaded log file to answer.

**To analyze telemetry data, please:**
1. Click the 📎 attachment button to upload a NovAtel log file (.log, .txt, .ascii, .gps, .bin)
2. Once uploaded, I can analyze the receiver data and answer questions about positioning, signal quality, interference, and more.

**Questions I can answer without a file:**
- NovAtel log message formats and field definitions
- GNSS concepts (RTK, PPP, multipath, ionosphere, etc.)
- Receiver configuration and commands
- Troubleshooting guides"""


_OFF_TOPIC_RESPONSE = """I'm a specialized NovAtel GNSS log analysis assistant. I can help with:

- **Log analysis**: Upload a receiver log file and ask about positioning, signal quality, interference, etc.
- **Documentation**: Ask about NovAtel log formats, field definitions, commands, and configuration
- **GNSS concepts**: RTK, PPP, multipath, ionosphere, satellite constellations, and more

Please ask a GNSS-related question and I'll be happy to help."""


# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def answer_without_file(question: str, session_id: str = "") -> str:
    """
    Answer a question when no log file is loaded.

    Routes through:
      - KB retrieval + synthesis for documentation questions
      - Direct LLM for general GNSS questions
      - Static responses for needs-log and off-topic

    Args:
        question:    User's query
        session_id:  For status tracking

    Returns:
        Final markdown response string
    """
    from src.main import get_llm, set_status, kb_search
    from langchain_core.messages import HumanMessage

    t0 = time.time()
    classification = classify_query(question)
    print(f"[DOC_ANSWER] classification={classification} question={question!r}")

    # ── Needs log file ────────────────────────────────────────────────
    if classification == "needs_log":
        if session_id:
            set_status(session_id, "")
        return _NEEDS_LOG_RESPONSE

    # ── Off-topic ─────────────────────────────────────────────────────
    if classification == "off_topic":
        if session_id:
            set_status(session_id, "")
        return _OFF_TOPIC_RESPONSE

    # ── General GNSS (no KB needed) ───────────────────────────────────
    if classification == "general_gnss":
        if session_id:
            set_status(session_id, "Answering from GNSS knowledge...")
        try:
            prompt = _GENERAL_GNSS_PROMPT.format(question=question)
            resp = get_llm().invoke([HumanMessage(content=prompt)])
            elapsed = time.time() - t0
            print(f"[DOC_ANSWER] general_gnss answered in {elapsed:.2f}s")
            return resp.content.strip()
        except Exception as e:
            return f"Error generating response: {e}"

    # ── Documentation (KB retrieval + synthesis) ──────────────────────
    if session_id:
        set_status(session_id, "Searching NovAtel documentation...")

    # Retrieve relevant KB chunks
    try:
        kb_results = kb_search(question, max_results=8)
    except Exception as e:
        print(f"[DOC_ANSWER] KB search failed: {e}")
        kb_results = []

    if not kb_results:
        # KB returned nothing — fall back to general GNSS knowledge
        if session_id:
            set_status(session_id, "No documentation found — answering from knowledge...")
        try:
            prompt = _GENERAL_GNSS_PROMPT.format(question=question)
            resp = get_llm().invoke([HumanMessage(content=prompt)])
            return resp.content.strip()
        except Exception as e:
            return f"No relevant documentation found and could not generate a response. ({e})"

    # Synthesize answer from KB content (NEVER dump raw chunks)
    if session_id:
        set_status(session_id, "Synthesizing answer from documentation...")

    # Build context from top results — use markdown content, skip low scores
    kb_content_parts = []
    for i, el in enumerate(kb_results):
        score = el.get("score", 0)
        content = el.get("content_markdown", "").strip()
        if not content or score < 0.1:
            continue
        # Truncate very long chunks
        if len(content) > 1500:
            content = content[:1500] + "..."
        source = el.get("source_uri", "")
        source_label = f" (source: {source.split('/')[-1]})" if source else ""
        kb_content_parts.append(f"--- Reference {i+1}{source_label} ---\n{content}")

    if not kb_content_parts:
        # All results were low quality
        if session_id:
            set_status(session_id, "Answering from general knowledge...")
        try:
            prompt = _GENERAL_GNSS_PROMPT.format(question=question)
            resp = get_llm().invoke([HumanMessage(content=prompt)])
            return resp.content.strip()
        except Exception as e:
            return f"Could not find relevant documentation. ({e})"

    kb_content = "\n\n".join(kb_content_parts[:6])  # Cap at 6 references

    prompt = _DOC_SYNTHESIS_PROMPT.format(
        question=question,
        kb_content=kb_content,
    )

    try:
        resp = get_llm().invoke([HumanMessage(content=prompt)])
        elapsed = time.time() - t0
        print(f"[DOC_ANSWER] documentation answered in {elapsed:.2f}s ({len(kb_results)} KB results used)")
        if session_id:
            set_status(session_id, "Complete ✓")
        return resp.content.strip()
    except Exception as e:
        print(f"[DOC_ANSWER] synthesis failed: {e}")
        return f"Found relevant documentation but could not synthesize an answer. ({e})"
