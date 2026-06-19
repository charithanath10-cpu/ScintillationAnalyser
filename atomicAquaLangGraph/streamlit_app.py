import sys
import os
import base64
from pathlib import Path


sys.path.append(os.path.abspath("."))

os.environ.setdefault("S3_BUCKET", "naspocuser-s3")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("KB_ID", "FH00WKSBPL")

import streamlit as st
import uuid
import asyncio
import base64
import io
from concurrent.futures import ThreadPoolExecutor

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config as BotocoreConfig

from src.main import (
    invoke as agent_invoke,
    get_status as agent_get_status,
    run_correlation_pipeline_streaming,
    run_scintillation_analysis,
    save_to_memory,
)
from src.scintillation_handler import is_scintillation_question

S3_BUCKET      = os.environ.get("S3_BUCKET", "naspocuser-s3")
S3_REGION      = os.environ.get("AWS_REGION", "ap-south-1")
SIZE_THRESHOLD = 5 * 1024 * 1024
MAX_UPLOAD     = 350 * 1024 * 1024

_s3_client = None
def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=S3_REGION, config=BotocoreConfig(read_timeout=300))
    return _s3_client

st.set_page_config(page_title="NovAtel AI", layout="wide", initial_sidebar_state="collapsed")

_executor = ThreadPoolExecutor(max_workers=4)
def run_async(coro):
    return _executor.submit(lambda: asyncio.run(coro)).result()

@st.cache_data
def get_logo_data_url():
    logo_path = Path(__file__).parent / "src" / "Novatel_Logo.png"
    if not logo_path.exists():
        st.error(f"Logo not found at: {logo_path}")
        return ""
    b64 = base64.b64encode(logo_path.read_bytes()).decode()
    # change image/png to image/jpeg or image/svg+xml if your file is different
    return f"data:image/png;base64,{b64}"
 
LOGO_URL = get_logo_data_url()

def upload_to_s3_with_progress(file_bytes: bytes, filename: str) -> str:
    key = f"logs/{filename}"
    cfg = TransferConfig(multipart_threshold=8*1024*1024, multipart_chunksize=8*1024*1024, max_concurrency=4, use_threads=True)
    try:
        get_s3_client().upload_fileobj(io.BytesIO(file_bytes), S3_BUCKET, key, Config=cfg)
        return key
    except Exception as e:
        raise Exception(f"S3 upload failed: {str(e)}")

if "session_id"                not in st.session_state: st.session_state.session_id                = str(uuid.uuid4())
if "chat"                      not in st.session_state: st.session_state.chat                      = []
if "pending_chip"              not in st.session_state: st.session_state.pending_chip              = None
if "client_id"                 not in st.session_state: st.session_state.client_id                 = str(uuid.uuid4())
if "pending_upload"            not in st.session_state: st.session_state.pending_upload            = None
# Scintillation flow state
if "pending_scintillation"     not in st.session_state: st.session_state.pending_scintillation     = None   # question text awaiting env choice
if "pending_scint_run"         not in st.session_state: st.session_state.pending_scint_run         = None   # question text ready to run

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>',
    unsafe_allow_html=True,
)

st.markdown("""
<style>
:root {
  --navy:       #00284c;
  --blue:       #005198;
  --blue-light: #1a6bb5;
  --blue-frost: #e8f2fa;
  --sky:        #4a9fd4;
  --off-white:  #f4f8fc;
  --border:     #b8d0e8;
  --border-dim: #d6e6f2;
  --text:       #00284c;
  --text-mid:   #2a5070;
  --text-dim:   #6080a0;
  --surface:    #ffffff;
  --r:          5px;
  --rlg:        10px;
  --mono:       'OpenSans-Regular';
  --ui:         'OpenSans-Regular';
}

/* ── Kill Streamlit chrome ── */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="collapsedControl"],
section[data-testid="stSidebar"] { display: none !important; }
div[style*="rgba(38, 39, 48"],
div[style*="rgba(14, 17, 23"]   { display: none !important; }
[data-testid="stBottom"]::before,
.stChatFloatingInputContainer::before { display: none !important; }

html, body, [class*="css"] { font-family: var(--ui) !important; background: var(--off-white) !important; }
.stApp { background: var(--off-white) !important; }

.block-container,
[data-testid="stAppViewBlockContainer"] {
  max-width: 880px !important;
  padding: 0 !important;
  margin: 0 auto !important;
}
[data-baseweb="textarea"]{
background-color:none
}
/* ── Bottom bar ── */
[data-testid="stBottom"] {
  max-width: 880px !important;
  margin: 0 auto !important;
  background: var(--off-white) !important;
  box-shadow: none !important;
  border-top: none !important;
  padding: 0 !important;
}
[data-testid="stBottom"] > div {
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  background: var(--off-white) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
  position: fixed !important;
  bottom: 0px !important;
  left: max(26px, calc(50% - 440px + 26px)) !important;
  width: calc(100% - 88px) !important;
  max-width: 827px !important;
  z-index: 999 !important;
  height: 60px;
  background: var(--off-white) !important;
}
[data-testid="stChatInput"] > :first-child { 
  border: none !important; 
  background: var(--off-white) !important;
}
[data-testid="stChatInput"] > div {
  background: var(--off-white) !important;
}
[data-testid="stChatInput"] textarea {
  font-family: var(--mono) !important;
  font-size: 14px !important;
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  color: var(--text) !important;
  line-height: 1.5 !important;
  padding: 10px 14px 20px !important;
  resize: none !important;
  width: 95% !important;
  min-height: 40px !important;
  max-height: 40px !important;
  min-width: 100px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,40,76,.08) !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 3px rgba(0,81,152,.1), 0 2px 8px rgba(0,40,76,.12) !important;
  outline: none !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--text-dim) !important; }

/* ── Hide submit button ── */
[data-testid="stChatInputSubmitButton"] {
  display: none !important;
}

/* ── Paperclip uploader — fixed size, never grows ── */
[data-testid="stFileUploader"] {
  position: fixed !important;
    bottom: 10px !important;
    right: max(20px, calc(50% - 410px)) !important;
    z-index: 1000 !important;
    width: 36px !important;
    height: 36px !important;
    overflow: hidden !important;
}

/* ── Hide post-upload chips/file info without touching the dropzone ── */
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploader"] [data-testid="stFileChips"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"],
[data-testid="stFileUploader"] [class*="uploadedFile"],
[data-testid="stFileUploader"] [class*="FileChip"],
[data-testid="stFileUploader"] [class*="fileChip"],
[data-testid="stFileUploader"] small,
[data-testid="stFileUploader"] button[kind="icon"],
[data-testid="stFileUploader"] button[kind="secondary"] {
  display: none !important;
  height: 0 !important;
  width: 0 !important;
  overflow: hidden !important;
  position: absolute !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
/* Scope span hiding to inside the dropzone instructions only */
[data-testid="stFileUploaderDropzoneInstructions"] span:not(:empty) {
  display: none !important;
}

/* ── Dropzone locked to exact icon size ── */
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
  width: 36px !important;
  height: 36px !important;
  min-width: unset !important;
  min-height: unset !important;
  max-height: 36px !important;
  padding: 0 !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--r) !important;
  background: var(--surface) !important;
  display: grid !important;
  place-items: center !important;
  cursor: pointer !important;
  transition: border-color .15s, background .15s !important;
  overflow: hidden !important;
}
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--blue) !important;
  background: var(--blue-frost) !important;
}
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]::before {
  content: "" !important;
  display: block !important;
  width: 18px !important;
  height: 18px !important;
  background-color: var(--text-dim) !important;
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'/%3E%3C/svg%3E") !important;
  mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'/%3E%3C/svg%3E") !important;
  -webkit-mask-repeat: no-repeat !important;
  mask-repeat: no-repeat !important;
  -webkit-mask-position: center !important;
  mask-position: center !important;
  -webkit-mask-size: contain !important;
  mask-size: contain !important;
  pointer-events: none !important;
  position:relative;
  top:6px;
}
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]:hover::before {
  background-color: var(--blue) !important;
}

/* ── Avatar labels ── */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
  font-size: 0 !important;
  color: transparent !important;
  display: grid !important;
  place-items: center !important;
  flex-shrink: 0 !important;
  align-self: flex-start !important;
}
[data-testid="stChatMessageAvatarUser"] *,
[data-testid="stChatMessageAvatarAssistant"] * { display: none !important; }
[data-testid="stChatMessageAvatarUser"] {
  background: linear-gradient(135deg, var(--blue-light) 0%, var(--sky) 100%) !important;
  border: 1px solid rgba(74,159,212,.35) !important;
  border-radius: 6px !important;
}
[data-testid="stChatMessageAvatarAssistant"] {
  background: linear-gradient(135deg, var(--navy) 0%, var(--blue) 100%) !important;
  border: 1px solid rgba(0,81,152,.4) !important;
  border-radius: 6px !important;
}
[data-testid="stChatMessageAvatarUser"]::after {
  content: "YOU";
  font-family: 'OpenSans-Regular' !important;
  font-size: 8px !important; font-weight: 600 !important;
  color: #fff !important; letter-spacing: .04em !important;
}
[data-testid="stChatMessageAvatarAssistant"]::after {
  content: "AI";
  font-family: 'OpenSans-Regular' !important;
  font-size: 10px !important; font-weight: 600 !important;
  color: #fff !important; letter-spacing: .04em !important;
}

/* ══════════════════════════════════════════════
   CHAT BUBBLES
   ══════════════════════════════════════════════ */

[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 8px 0 !important;
  gap: 10px !important;
  align-items: flex-start !important;
  justify-content: flex-start !important;
  animation: fadeUp .2s ease both;
}
@keyframes fadeUp {
  from { opacity:0; transform:translateY(6px); }
  to   { opacity:1; transform:translateY(0); }
}

/* ── USER: push to right, avatar after bubble via order ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  justify-content: flex-end !important;
  flex-direction: row !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] {
  order: 2 !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
  order: 1 !important;
  background: linear-gradient(135deg, var(--blue) 0%, var(--blue-light) 100%) !important;
  border-radius: 12px !important;
  padding: 10px 15px 20px 15px !important;
  flex: 0 1 auto !important;
  width: fit-content !important;
  max-width: 68% !important;
  min-width: 0 !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(0,81,152,.18) !important;
  margin: 0 !important;
  min-height: 40px;
}
[data-testid="stMarkdownContainer"] .filesize {
  color: rgb(96, 128, 160) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) span,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) li {
  color: #fff !important;
  font-family: var(--mono) !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
  margin: 0 !important;
  letter-spacing: 0.6px;
}

/* ── AI: left-aligned ── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
  background: var(--surface) !important;
  border-radius: 6px !important;
  padding: 10px 15px 20px 15px !important;
  flex: 0 1 auto !important;
  width: fit-content !important;
  max-width: 72% !important;
  min-width: 0 !important;
  border: 1px solid var(--border-dim) !important;
  box-shadow: 0 1px 4px rgba(0,40,76,.06) !important;
  margin: 0 !important;
  min-height: 40px;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) span {
  color: var(--text) !important;
  font-family: var(--mono) !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
  letter-spacing: 0.6px;
  margin: 0 !important;
}
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {
  color: var(--text);
            background:transparent;
  font-family: var(--mono);
  font-size: 14px;
  text-decoration:none;
}
.st-b1{
            background-color:transparent !important
            }
/* ── Chip buttons ── */
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button {
  padding: 7px 15px !important;
  border: 1px solid var(--border) !important;
  border-radius: 20px !important;
  font-size: 11.5px !important;
  font-family: var(--mono) !important;
  color: var(--text-mid) !important;
  background: var(--surface) !important;
  box-shadow: none !important;
  height: auto !important; min-height: unset !important;
  line-height: 1.4 !important;
  width: 100% !important;
  transition: border-color .15s, color .15s, background .15s !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover {
  border-color: var(--blue) !important; color: var(--blue) !important;
  background: var(--blue-frost) !important;
  box-shadow: 0 2px 8px rgba(0,81,152,.12) !important;
}

/* ── Misc ── */
[data-testid="stAlert"] { font-family: var(--mono) !important; font-size: 12px !important; border-radius: 6px !important; margin: 4px 24px !important; }
[data-testid="stSpinner"] p { font-family: var(--mono) !important; font-size: 12px !important; color: var(--text-dim) !important; }

/* ── Status messages (italic text in assistant bubbles) ── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) em,
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) i {
  color: var(--text-dim) !important;
  font-style: italic !important;
  font-size: 12px !important;
  opacity: 0.85 !important;
}
</style>
""", unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────
st.markdown(f"""
<header style="display:flex;align-items:center;gap:14px;padding:0 24px;
  background:#00284c;border-bottom:2px solid #005198;
  position:relative;overflow:hidden;height:60px;
  max-width:880px;margin:0 auto;
  box-shadow:0 0 0 1px rgba(0,40,76,.08),0 4px 32px rgba(0,40,76,.06);">
  <div style="position:absolute;right:-60px;top:-40px;width:220px;height:140px;
    background:radial-gradient(ellipse at center,rgba(0,81,152,.45) 0%,transparent 70%);pointer-events:none;"></div>
  <div style="width:36px;height:36px;border-radius:5px;flex-shrink:0;
    background-image:url('{LOGO_URL}');
    background-size:34px;
    background-repeat:no-repeat;
    background-position:center;
    background-color:white;
    box-shadow:0 0 0 1px rgba(255,255,255,.15),0 2px 8px rgba(0,0,0,.3);">
  </div>
  <div style="flex:1;">
    <div style="font-family:'OpenSans-Regular';font-size:16px;font-weight:600;letter-spacing:.07em;color:#fff;line-height:1;padding-top:1px;">NovAtel AI Assistant</div>
    <div style="font-size:12px;color:rgba(255,255,255,.52);margin-top:3px;letter-spacing:.07em;font-family:'OpenSans-Regular';">Query documentation &middot; Analyse logs &middot; GNSS insights</div>
  </div>
</header>
""", unsafe_allow_html=True)
 
 
# ── Welcome screen ────────────────────────────────────────────────────
if not st.session_state.chat:
    st.markdown(f"""
<div style="display:flex;flex-direction:column;align-items:center;gap:10px;
  padding:48px 32px 20px;text-align:center;">
  <div style="width:56px;height:56px;border-radius:14px;margin-bottom:8px;
    background-image:url('{LOGO_URL}');
    background-size:50px;
    background-repeat:no-repeat;
    background-position:center;
    background-color:white;
    box-shadow:0 4px 20px rgba(0,81,152,.3);">
  </div>
  <strong style="font-family:'OpenSans-Regular';font-size:16px;font-weight:600;color:#00284c;letter-spacing:.05em;">NovAtel AI Assistant</strong>
  <p style="font-size:14px;color:#6080a0;max-width:360px;line-height:1.6;font-family:'OpenSans-Regular';margin:0 0 4px;">
    Ask about logs, message formats, or upload a receiver log file to begin analysis.
  </p>
</div>
""", unsafe_allow_html=True)



# ── Flush pending chip ────────────────────────────────────────────────
if st.session_state.pending_chip:
    chip_text = st.session_state.pending_chip
    st.session_state.pending_chip = None
    st.session_state.chat.append(("user", chip_text))
    st.rerun()

# ── Render chat ───────────────────────────────────────────────────────
for role, msg in st.session_state.chat:
    if role == "agent":
        with st.chat_message("assistant"):
            st.markdown(msg)
    elif role == "file":
        with st.chat_message("user"):
            st.markdown(msg, unsafe_allow_html=True)
    else:
        with st.chat_message("user"):
            st.markdown(msg)

# ── Paperclip file uploader ───────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload file", type=["txt", "log", "ascii", "abbrev_ascii", "dat", "bin", "json", "csv", "gpf", "gps"],
    key="file_upload", label_visibility="collapsed"
)

# ── Chat input ────────────────────────────────────────────────────────
user_input = st.chat_input("Ask about NovAtel logs, message formats, GNSS…")

# ── Handle file upload ────────────────────────────────────────────────
if uploaded_file and uploaded_file.file_id not in st.session_state.get("processed_files", set()):
    print(f"[UPLOAD][1] File widget triggered: name={uploaded_file.name} size={uploaded_file.size} id={uploaded_file.file_id}")
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    st.session_state.processed_files.add(uploaded_file.file_id)
    file_size = uploaded_file.size
    file_name = uploaded_file.name

    if file_size > MAX_UPLOAD:
        print(f"[UPLOAD][2] REJECTED: file too large ({file_size} bytes, max {MAX_UPLOAD})")
        st.error(f"File is {file_size / (1024*1024):.1f} MB. Max allowed is {MAX_UPLOAD / (1024*1024):.0f} MB.")
    else:
        print(f"[UPLOAD][2] Accepted: {file_name} ({file_size/1024/1024:.1f} MB), path=large" if file_size > SIZE_THRESHOLD else f"[UPLOAD][2] Accepted: {file_name} ({file_size/1024:.1f} KB), path=small")
        size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024*1024):.1f} MB"
        file_chip_html = f"""
        <div style="display:inline-flex;align-items:center;gap:7px;
          background:#e8f2fa;border:1px solid #b8d0e8;border-radius:8px;
          padding:6px 12px;font-size:12px;color:#005198;font-family:monospace;position:relative;bottom:3px;">
          📄&nbsp;<strong>{file_name}</strong>&nbsp;<span class="filesize">{size_str}</span>
        </div>
        """
        st.session_state.chat.append(("file", file_chip_html))
        st.session_state.session_id = "session-" + uuid.uuid4().hex[:10]
        print(f"[UPLOAD][3] New session_id={st.session_state.session_id}")

        if file_size > SIZE_THRESHOLD:
            print(f"[UPLOAD][4] Large file path: reading bytes from widget...")
            with st.spinner(f"⬆️ Uploading {file_name} ({size_str}) to cloud..."):
                try:
                    import time as _time
                    t0 = _time.time()
                    file_bytes = uploaded_file.read()
                    print(f"[UPLOAD][5] Widget read complete: {len(file_bytes)} bytes in {_time.time()-t0:.2f}s")
                    print(f"[UPLOAD][6] Starting S3 upload to bucket={S3_BUCKET}...")
                    t1 = _time.time()
                    s3_key = upload_to_s3_with_progress(file_bytes, file_name)
                    print(f"[UPLOAD][7] S3 upload complete: key={s3_key} in {_time.time()-t1:.2f}s")
                    del file_bytes  # free RAM immediately
                    st.session_state.pending_upload = {
                        "s3_key": s3_key,
                        "file_name": file_name,
                        "file_size": file_size,
                    }
                    print(f"[UPLOAD][8] pending_upload set with s3_key, calling st.rerun()")
                except Exception as e:
                    import traceback
                    print(f"[UPLOAD][ERROR] Large file upload failed:\n{traceback.format_exc()}")
                    st.error(f"Upload failed: {e}")
                    st.session_state.pending_upload = None
        else:
            print(f"[UPLOAD][4] Small file path: reading bytes into session_state...")
            import time as _time
            t0 = _time.time()
            file_bytes = uploaded_file.read()
            print(f"[UPLOAD][5] Widget read complete: {len(file_bytes)} bytes in {_time.time()-t0:.2f}s")
            st.session_state.pending_upload = {
                "file_bytes": file_bytes,
                "file_name": file_name,
                "file_size": file_size,
            }
            print(f"[UPLOAD][6] pending_upload set with file_bytes, calling st.rerun()")

        st.rerun()

# ── Process pending upload (runs on the rerun after chip is shown) ────
if st.session_state.pending_upload:
    upload_info = st.session_state.pending_upload
    st.session_state.pending_upload = None  # clear immediately

    file_name  = upload_info["file_name"]
    file_size  = upload_info["file_size"]
    file_session_id = st.session_state.session_id
    path_type  = "s3" if "s3_key" in upload_info else "bytes"
    print(f"[PROCESS][1] Processing pending upload: {file_name} ({file_size/1024/1024:.1f} MB) path={path_type} session={file_session_id}")

    with st.chat_message("assistant", avatar="🛰"):
        # Use st.status so we can send live updates to the browser every few seconds.
        # This keeps the WebSocket alive during long operations (parsing 300 MB files
        # takes 130+ seconds which exceeds Streamlit Cloud's idle WebSocket timeout).
        with st.status(f"📂 Processing {file_name}...", expanded=True) as status_box:
            import threading, time as _time, queue as _queue

            result_q = _queue.Queue()

            def _invoke_background():
                try:
                    import time as _t
                    t0 = _t.time()
                    print(f"[PROCESS][2] Background thread: calling agent_invoke path={path_type}")
                    if "s3_key" in upload_info:
                        response = asyncio.run(agent_invoke({
                            "s3_key": upload_info["s3_key"],
                            "filename": file_name,
                            "session_id": file_session_id,
                        }))
                    else:
                        file_b64 = base64.b64encode(upload_info["file_bytes"]).decode("utf-8")
                        response = asyncio.run(agent_invoke({
                            "file": file_b64,
                            "filename": file_name,
                            "session_id": file_session_id,
                        }))
                    elapsed = _t.time() - t0
                    print(f"[PROCESS][4] agent_invoke complete in {elapsed:.2f}s")
                    result_q.put(("ok", response))
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    print(f"[PROCESS][ERROR] agent_invoke failed:\n{tb}")
                    result_q.put(("error", str(e), tb))

            thread = threading.Thread(target=_invoke_background, daemon=True)
            thread.start()

            # Heartbeat loop — updates st.status every 3s to keep WebSocket alive
            _steps = [
                "⬆️ File received",
                "🔍 Parsing log records...",
                "📊 Indexing telemetry events...",
                "🧠 Analysing file content...",
                "✅ Almost done...",
            ]
            _step_idx = 0
            _elapsed = 0
            st.write(_steps[0])

            while thread.is_alive():
                _time.sleep(3)
                _elapsed += 3
                if _step_idx < len(_steps) - 1:
                    _step_idx += 1
                    st.write(f"{_steps[_step_idx]} ({_elapsed}s)")
                else:
                    # Keep sending updates so WebSocket stays alive
                    st.write(f"⏳ Still working... ({_elapsed}s)")

            # Thread finished — get result
            try:
                outcome = result_q.get_nowait()
            except _queue.Empty:
                outcome = ("error", "No response from agent", "")

            if outcome[0] == "ok":
                response = outcome[1]
                result_text = response.get("result", str(response)) if response else "Error processing file."
                print(f"[PROCESS][5] result_text length={len(result_text)} chars")
                status_box.update(label=f"✅ {file_name} processed", state="complete", expanded=False)
            else:
                result_text = f"Error processing file: {outcome[1]}\n\n```\n{outcome[2]}\n```"
                status_box.update(label=f"❌ Processing failed", state="error", expanded=True)

    print(f"[PROCESS][6] Appending result to chat, calling st.rerun()")
    st.session_state.chat.append(("agent", result_text))
    st.rerun()

# ── Handle typed message ──────────────────────────────────────────────
if user_input:
    # Detect scintillation questions — gate them behind the env choice dialog
    if is_scintillation_question(user_input):
        st.session_state.chat.append(("user", user_input))
        st.session_state.pending_scintillation = user_input   # hold the question
    else:
        st.session_state.chat.append(("user", user_input))
    st.rerun()

# ── Scintillation: show environment choice ────────────────────────────
if st.session_state.pending_scintillation:
    question_held = st.session_state.pending_scintillation
    with st.chat_message("assistant"):
        st.markdown(
            "**Can you describe the type of environment this file has been recorded in?**"
        )
        col_open, col_obs = st.columns(2, gap="small")
        with col_open:
            if st.button("🌤 Open Sky", key="env_open_sky", use_container_width=True):
                st.session_state.pending_scintillation = None
                st.session_state.pending_scint_run = question_held
                st.rerun()
        with col_obs:
            if st.button("🏙 Obstructed Environment", key="env_obstructed", use_container_width=True):
                st.session_state.pending_scintillation = None
                st.session_state.chat.append((
                    "agent",
                    "Scintillation analysis requires an **Open Sky** environment. "
                    "In an obstructed environment, lock-loss and signal fades are caused "
                    "by buildings or foliage rather than the ionosphere, so the analysis "
                    "would not be meaningful.\n\n"
                    "If your recording was actually taken in open sky, please try again "
                    "and select **Open Sky**.",
                ))
                st.rerun()
    # Stop here — don't let the normal pipeline fire while waiting for a choice
    st.stop()

# ── Scintillation: run analysis when env = Open Sky ───────────────────
if st.session_state.pending_scint_run:
    scint_question = st.session_state.pending_scint_run
    st.session_state.pending_scint_run = None
    session_id = st.session_state.session_id

    import threading
    import time
    import queue

    scint_queue = queue.Queue()

    def _scint_background():
        try:
            for chunk in run_scintillation_analysis(session_id, scint_question):
                scint_queue.put(("token", chunk))
        except Exception as exc:
            scint_queue.put(("error", str(exc)))
        finally:
            scint_queue.put(("done", None))

    threading.Thread(target=_scint_background, daemon=True).start()

    # Status banner while pipeline runs
    scint_status_ph = st.empty()
    with scint_status_ph.container():
        with st.chat_message("assistant", avatar="🛰"):
            st.markdown("*🔬 Running scintillation pipeline…*")

    # Wait for first token
    first_tok = False
    while not first_tok:
        try:
            _t, _d = scint_queue.get(timeout=0.3)
            scint_queue.put((_t, _d))
            first_tok = True
        except queue.Empty:
            cur = agent_get_status(session_id)
            if cur and cur != "Complete ✓":
                with scint_status_ph.container():
                    with st.chat_message("assistant", avatar="🛰"):
                        st.markdown(f"*{cur}*")

    scint_status_ph.empty()

    def _scint_tokens():
        while True:
            try:
                typ, dat = scint_queue.get(timeout=1000)  # 5 min — scintillation pipeline can be slow
                if typ == "token":
                    yield dat
                elif typ == "done":
                    break
                elif typ == "error":
                    yield f"\n\nError: {dat}"
                    break
            except queue.Empty:
                yield "\n\n⚠️ Analysis timed out. The file may be too large or the service is busy. Please try again."
                break

    with st.chat_message("assistant"):
        scint_text = st.write_stream(_scint_tokens())

    scint_text = scint_text or ""
    st.session_state.chat.append(("agent", scint_text))
    if scint_text:
        save_to_memory(session_id, scint_question, scint_text)
    st.rerun()

# ── Answer last user message (normal pipeline) ────────────────────────
_scint_waiting = bool(
    st.session_state.pending_scintillation or st.session_state.pending_scint_run
)
if (
    st.session_state.chat
    and st.session_state.chat[-1][0] == "user"
    and not _scint_waiting
):
    # Capture values from session state
    user_prompt = st.session_state.chat[-1][1]
    session_id = st.session_state.session_id

    import threading
    import time
    import queue

    # Strategy:
    # 1. Run streaming pipeline in background thread (tools execute, then LLM streams)
    # 2. While waiting for first token, show live status updates
    # 3. Once first token arrives, switch to st.write_stream for live rendering

    token_queue = queue.Queue()

    # Capture chat history on main thread (threads can't access st.session_state)
    chat_hist = [(role, text) for role, text in st.session_state.chat
                 if role in ("user", "agent")]

    def background_stream():
        """Run the streaming pipeline, push chunks to queue."""
        try:
            for chunk in run_correlation_pipeline_streaming(user_prompt, session_id, chat_history=chat_hist):
                token_queue.put(("token", chunk))
        except Exception as e:
            token_queue.put(("error", str(e)))
        finally:
            token_queue.put(("done", None))

    # Start pipeline in background
    stream_thread = threading.Thread(target=background_stream, daemon=True)
    stream_thread.start()

    # Show live status updates until first token arrives
    status_placeholder = st.empty()
    last_status = "Analyzing your question..."

    with status_placeholder.container():
        with st.chat_message("assistant", avatar="🛰"):
            st.markdown(f"*{last_status}*")

    first_token_received = False
    while not first_token_received:
        # Check for first token (non-blocking, 200ms timeout)
        try:
            msg_type, msg_data = token_queue.get(timeout=0.2)
            token_queue.put((msg_type, msg_data))  # Put back for stream loop
            first_token_received = True
            break
        except queue.Empty:
            pass

        # Update status from pipeline
        current_status = agent_get_status(session_id)
        if current_status and current_status != last_status and current_status != "Complete ✓":
            last_status = current_status
            with status_placeholder.container():
                with st.chat_message("assistant", avatar="🛰"):
                    st.markdown(f"*{current_status}*")

    # Clear status — switch to streaming output
    status_placeholder.empty()

    # Stream tokens into chat bubble
    def token_generator():
        while True:
            try:
                msg_type, msg_data = token_queue.get(timeout=300)  # 5 min — LLM + tool execution can be slow
                if msg_type == "token":
                    yield msg_data
                elif msg_type == "done":
                    break
                elif msg_type == "error":
                    yield f"\n\nError: {msg_data}"
                    break
            except queue.Empty:
                yield "\n\n⚠️ Response timed out. The service may be busy — please try again."
                break

    with st.chat_message("assistant"):
        streamed_text = st.write_stream(token_generator())

    # Save full response to chat history and memory
    streamed_text = streamed_text or ""
    st.session_state.chat.append(("agent", streamed_text))
    if streamed_text:
        save_to_memory(session_id, user_prompt, streamed_text)
    st.rerun()