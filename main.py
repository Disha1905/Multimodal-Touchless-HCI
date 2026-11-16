"""Multimodal Touchless Human-Computer Interaction Engine -- Streamlit dashboard.
Run:  python -m streamlit run main.py"""
import html
import time

import streamlit as st

from config.profiles import PROFILE_NAMES, CONTEXT_GESTURES
from core import context
from modules.perf import system_stats
from security.accounts import AccountStore, AccountError

st.set_page_config(page_title="Multimodal Touchless HCI", page_icon="🖐", layout="wide",
                   initial_sidebar_state="collapsed")

THEME_CSS = """
<style>
html {font-size: 14px;}
.stApp {background: linear-gradient(180deg,#060a14 0%,#0b1630 45%,#10234a 100%); color:#e6edf7;}
header[data-testid="stHeader"] {background: transparent; height: 2.2rem;}
[data-testid="stStatusWidget"] {visibility: hidden;}
.block-container {padding-top: 1.4rem; padding-bottom: .4rem; max-width: 1400px;}
/* no grey-out flicker while the live panels refresh */
[data-stale="true"], .stale-element {opacity: 1 !important; transition: none !important; filter: none !important;}
[data-testid="stElementContainer"] {transition: none !important;}
h1,h2,h3,h4,h5 {color:#fff; letter-spacing:-0.01em;}
h2 {font-size: 1.5rem !important; margin: 0 0 .1rem 0 !important; padding: .2rem 0 !important;}
h5 {margin: .1rem 0 .3rem 0 !important; padding: 0 !important;}
.apptitle {font-size: 1.15rem; font-weight: 700; color:#fff; margin: -.9rem 0 .2rem 0;}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background: linear-gradient(90deg,#6a5ae0,#3f87e0) !important; border:0 !important; color:#fff !important;
  min-height: 2.4rem; border-radius:10px !important; font-weight:600;}
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
  background: transparent !important; border:1px solid #2a3a5c !important; color:#c5d2ea !important;
  min-height: 2.4rem; border-radius:10px !important;}
button:disabled {opacity:.5;}
button[data-baseweb="tab"] {color:#e6edf7;}
button[data-baseweb="tab"][aria-selected="true"] {color:#7c6cf0;}
.card {background:#101a33; border:1px solid #22304f; border-radius:12px; padding:9px 12px;}
.card .lbl {font-size:.74rem; color:#9fb0cf; margin-bottom:2px;}
.card .val {font-size:1.45rem; font-weight:600; color:#fff; line-height:1.1;}
.tag {font-size:.62rem; letter-spacing:.14em; color:#8ea2c8; text-transform:uppercase; font-weight:700;}
.big {font-size:1.25rem; font-weight:700; color:#fff; margin:0 0 4px 0;}
.muted {color:#9fb0cf; font-size:.85rem; line-height:1.35;}
.grid {display:grid; grid-template-columns: 1fr 1fr; gap: 6px 14px; margin-top:8px; font-size:.9rem;}
.grid .full {grid-column: 1 / span 2;}
.grid .v {overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.preview {background:#0f1a33; border:1px solid #22304f; border-radius:14px; text-align:center;
          height: 42vh; display:flex; align-items:center; justify-content:center; overflow:hidden;}
.preview img {display:block; max-height: 42vh; max-width:100%; width:auto; margin:auto;}
.recent {color:#9fb0cf; font-size:.85rem; line-height:1.55; margin-top:4px;}
.recent b {color:#e6edf7; font-weight:600;}
.note {color:#9fb0cf; font-size:.8rem; margin:2px 0;}
.alert {border-radius:10px; padding:8px 12px; margin-bottom:8px; font-weight:600; font-size:.95rem;}
.alert.on {background:#12392a; border:1px solid #1f7a4f; color:#8cf0bd;}
.alert.off {background:#2a2f3d; border:1px solid #475066; color:#cfd6e6;}
.alert.error {background:#442222; border:1px solid #8a3a3a; color:#ffb4b4;}
.step {font-weight:700; color:#fff; margin:.5rem 0 .1rem 0; font-size:1rem;}
.heard {font-size:.88rem; line-height:1.6; color:#c5d2ea;}
.heard .ok {color:#8cf0bd;} .heard .no {color:#8ea2c8;} .heard .blocked {color:#f3d27a;}
.chips span {display:inline-block; background:#16254a; border:1px solid #2a3a5c; border-radius:14px;
             padding:1px 9px; margin:2px 3px 2px 0; font-size:.82rem; color:#dbe5fa;}
.chip-title {font-weight:700; color:#fff; margin:.2rem 0 .1rem 0;}
.shot {background:#0f1a33; border:1px solid #22304f; border-radius:12px; overflow:hidden; text-align:center;}
.shot img {display:block; max-height: 26vh; max-width:100%; width:auto; margin:auto;}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

FACE_HELP = """
**Calibration:** after the camera starts, face it directly with both eyes open and a relaxed face for about
2 seconds.

| Do this | What happens |
|---|---|
| Close **one eye** briefly (keep the other open) | Left wink = left click, right wink = right click (sides as seen in the mirrored preview) |
| Keep your **mouth open** for about one second (a progress bar shows on the preview) | Starts / stops MAX Voice (you hear a beep and see a green banner) |
| Raise eyebrows, blink normally | Shown on screen only - they do not trigger actions |

Computer control must be enabled for winks. Facial interaction is not face authentication.
"""


def card(label: str, value: str) -> str:
    return (f'<div class="card"><div class="lbl">{html.escape(label)}</div>'
            f'<div class="val">{html.escape(value)}</div></div>')


@st.cache_resource
def get_store():
    import os, sys
    from pathlib import Path
    p = (Path(os.environ.get("LOCALAPPDATA", ".")) / "MultimodalTouchlessHCI" / "access.json") if getattr(sys, "frozen", False) else Path("user_data/access.json")
    return AccountStore(str(p))


@st.cache_resource
def get_controller():
    from core.controller import Controller
    return Controller()


@st.cache_resource
def get_speaker():
    from modules.speech import Speaker
    return Speaker()


# ------------------------------------------------------------------ account gate
def gate() -> bool:
    if st.session_state.get("user"):
        return True
    store = get_store()
    st.title("🖐 Multimodal Touchless HCI Engine")
    st.caption("Local account access (username + PIN). This is not face authentication.")
    tabs = st.tabs(["Log in", "Create account", "Recover PIN"])
    with tabs[0]:
        u = st.text_input("Username", key="li_u")
        p = st.text_input("PIN", type="password", key="li_p")
        if st.button("Log in", type="primary"):
            try:
                store.login(u, p)
                st.session_state["user"] = store.data["users"][u.lower()]["username"]
                st.rerun()
            except AccountError as e:
                st.error(str(e))
    with tabs[1]:
        u = st.text_input("Username (3-32 letters/digits)", key="rg_u")
        p = st.text_input("PIN (6-12 digits)", type="password", key="rg_p")
        if st.button("Create account", type="primary"):
            try:
                code = store.register(u, p)
                st.success("Account created. Save this recovery code now - it is shown only once:")
                st.code(code)
            except AccountError as e:
                st.error(str(e))
    with tabs[2]:
        u = st.text_input("Username", key="rc_u")
        c = st.text_input("Recovery code", key="rc_c")
        p = st.text_input("New PIN", type="password", key="rc_p")
        if st.button("Reset PIN", type="primary"):
            try:
                new_code = store.recover(u, c, p)
                st.success("PIN reset. New recovery code (save it):")
                st.code(new_code)
            except AccountError as e:
                st.error(str(e))
    return False


if not gate():
    st.stop()

ctl = get_controller()
store = get_store()
speaker = get_speaker()
user = st.session_state["user"]


def alert_html() -> str:
    """Brief banner after the microphone is switched on/off (also while voice stays on)."""
    a = ctl.alert
    if a and time.monotonic() - a[1] < 4:
        return f'<div class="alert {a[2]}">{"🎙" if a[2] != "error" else "âš "} {html.escape(a[0])}</div>'
    if ctl.voice.active:
        return '<div class="alert on">🎙 Microphone is ON - listening for commands</div>'
    return ""


st.markdown('<div class="apptitle">🖐 Multimodal Touchless HCI Engine</div>', unsafe_allow_html=True)
tab_modes, tab_ai, tab_voice, tab_settings, tab_about, tab_account = st.tabs(
    ["Interaction modes", "Screen AI", "MAX Voice", "Settings", "About & limitations", "Account settings"])

# ================================================================== Interaction modes
with tab_modes:
    c1, c2, c3, c4 = st.columns([1.1, 1.1, 1.4, 2.4])
    if c1.button("Start camera", type="primary", disabled=ctl.running, use_container_width=True):
        if not ctl.start():
            st.error("Could not open the webcam. Close other apps using it, or change the camera index in Settings.")
        st.rerun()
    if c2.button("Stop camera", disabled=not ctl.running, use_container_width=True):
        ctl.stop()
        st.rerun()
    on = ctl.policy.controls_enabled
    if c3.button("Pause controls" if on else "Enable controls", type="primary", use_container_width=True):
        ctl.set_controls(not on)
        st.rerun()
    face_on = c4.toggle("Facial interaction (wink / mouth-open)", key="face_on",
                        help="Optional. Interaction events only - this is not face authentication.")
    if ctl.running and face_on != ctl.face_enabled:
        ctl.set_face(face_on)
    elif not ctl.running and face_on:
        ctl.face_enabled = False
    st.markdown('<div class="note">Computer control starts <b>paused</b>: check the preview first, then press '
                'Enable controls.</div>', unsafe_allow_html=True)

    @st.fragment(run_every=1.0)
    def metrics_row():
        stats = system_stats()
        vals = [("Camera", "Running" if ctl.running else "Stopped"),
                ("Webcam FPS", f"{ctl.camera.fps:.0f}" if ctl.running and ctl.camera else "—"),
                ("Processing FPS", f"{ctl.fps.fps:.1f}" if ctl.running else "0.0"),
                ("CPU utilization", f"{stats['cpu_percent']:.0f}%"),
                ("Memory utilization", f"{stats['memory_percent']:.0f}%")]
        for col, (l, v) in zip(st.columns(5), vals):
            col.markdown(card(l, v), unsafe_allow_html=True)

    @st.fragment(run_every=0.15)
    def preview_panel():
        if ctl.running and st.session_state.get('face_on') and not ctl.face_enabled:
            ctl.set_face(True)
        if ctl.running and ctl.last_jpeg:
            import base64
            img = base64.b64encode(ctl.last_jpeg).decode()
            box = f'<div class="preview"><img decoding="sync" src="data:image/jpeg;base64,{img}"></div>'
        else:
            box = '<div class="preview"><span class="muted">Camera is stopped.</span></div>'
        if ctl.face_enabled:
            fe = ctl.face_events
            dbg = f" · {fe.debug}" if fe and fe.calibrated and fe.debug else ""
            msg = f"Facial analysis: {ctl.status['face']}{dbg}"
        else:
            msg = "Facial analysis is off."
        st.markdown(box + f'<div class="note">{html.escape(msg)}</div>', unsafe_allow_html=True)

    @st.fragment(run_every=0.5)
    def state_panel():
        s_, e = ctl.status, html.escape
        on_ = ctl.policy.controls_enabled
        mic = "ON" if ctl.voice.active else "off"
        st.markdown(
            alert_html() +
            '<div class="card">'
            '<div class="tag">Computer control</div>'
            f'<div class="big">{"Enabled" if on_ else "Paused"}</div>'
            '<div class="muted">Index finger moves the cursor. Click, scroll and drag poses follow the gesture library.</div>'
            '<div class="grid">'
            f'<div class="full"><div class="tag">Active window</div><div class="v">{e(s_["window"])}</div></div>'
            f'<div><div class="tag">Gesture</div><div class="v">{e(s_["gesture"])}</div></div>'
            f'<div><div class="tag">Profile</div><div class="v">{e(s_["profile"])}</div></div>'
            f'<div><div class="tag">Fingers (T I M R P)</div><div class="v">{e(s_["fingers"])}</div></div>'
            f'<div><div class="tag">Microphone</div><div class="v">{mic}</div></div>'
            '</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="tag" style="margin-top:8px">Recent actions</div>', unsafe_allow_html=True)
        if ctl.actions.log:
            rows = "".join(f"<div><b>{e(t)}</b> &nbsp; {e(a)}</div>" for t, a in list(reversed(ctl.actions.log))[:5])
            st.markdown(f'<div class="recent">{rows}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="recent">No actions recorded yet.</div>', unsafe_allow_html=True)

    metrics_row()
    left, right = st.columns([1.35, 1])
    with left:
        st.markdown("##### Live camera preview")
        preview_panel()
    with right:
        st.markdown("##### System state")
        state_panel()

    with st.expander("How facial interaction works"):
        st.markdown(FACE_HELP)
        if ctl.face_enabled and ctl.running and st.button("Recalibrate face"):
            ctl.recalibrate_face()
    with st.expander("Gesture reference"):
        g1, g2 = st.columns(2)
        g1.table({"Pose": ["Index only", "Index + middle", "Index + middle + ring", "Thumb only",
                           "Thumb + little", "Index + little", "Fist / open palm"],
                  "Action": ["Cursor", "Left click", "Right click", "Scroll up", "Scroll down",
                             "Drag (cursor follows index finger)", "Neutral"]})
        rows = {"Profile": PROFILE_NAMES}
        for k, name in [("C1", "C1 four fingers"), ("C2", "C2 L shape"),
                        ("C3", "C3 little finger only"), ("C4", "C4 middle+ring+little")]:
            rows[name] = [(CONTEXT_GESTURES[p][k] or "-").replace("_", " ") for p in PROFILE_NAMES]
        g2.table(rows)

# ================================================================== Screen AI
with tab_ai:
    from modules import screen_ai as S
    st.markdown("## Screen AI")
    st.caption("Pick a window, read its text, then summarize, translate or listen to it. "
               "The text language is detected automatically.")
    cfg = st.session_state.setdefault("ai_cfg", S.AIConfig.from_env())
    with st.expander("Advanced settings (AI provider, text language)"):
        forced = st.selectbox("Text language on screen", ["auto"] + list(S.LANG_LABELS),
                              format_func=lambda l: "Automatic (recommended)" if l == "auto" else S.LANG_LABELS[l],
                              help="Leave on Automatic. Choose a language only if the automatic result is poor.")
        cfg.provider = st.selectbox("AI provider", ["Auto", "Gemini", "Ollama"],
                                    index=["Auto", "Gemini", "Ollama"].index(cfg.provider),
                                    help="Auto: Gemini when a key is set, otherwise local Ollama.")
        g1, g2 = st.columns(2)
        cfg.gemini_key = g1.text_input("Gemini API key (kept in this session only)", cfg.gemini_key, type="password")
        cfg.gemini_model = g2.text_input("Gemini model", cfg.gemini_model)
        o1, o2 = st.columns(2)
        cfg.ollama_host = o1.text_input("Ollama host", cfg.ollama_host)
        cfg.ollama_model = o2.text_input("Ollama model", cfg.ollama_model)
        st.caption("Translation tries Google Translate first, then the provider above.")
    if not S.find_tesseract():
        st.error(S.TESS_HELP)

    wins = context.list_windows()
    labels = {w["hwnd"]: context.window_label(w) for w in wins}
    colL, colR = st.columns([1, 1.15])
    with colL:
        st.markdown("##### 1 · Capture a window")
        cap_hwnd = st.selectbox("Application window to capture", list(labels) or [None],
                                format_func=lambda h: labels.get(h, "No other windows found"),
                                label_visibility="collapsed")
        st.caption("The selected window is captured directly, even when the HCI dashboard is in front.")
        if st.button("Capture window and read text", type="primary", disabled=cap_hwnd is None,
                     use_container_width=True):
            with st.spinner("Capturing and reading the window (first run may download language packs)..."):
                try:
                    img, how = S.capture_window(cap_hwnd)
                    text, conf, msg, used = S.ocr_auto(img, None if forced == "auto" else forced)
                    names = ", ".join(S.LANG_LABELS[l] for l in used.split("+")) if "+" not in used else "automatic"
                    st.session_state.update(
                        ocr_text=text, ai_out="",
                        ocr_info=f"Read with {names} · confidence {conf:.0f}% · captured via {how}. {msg}",
                        shot_uri=S.to_data_uri(img))
                    if not text.strip():
                        st.warning("No text was found. Try a bigger window or pick the language under Advanced settings.")
                except Exception as ex:
                    st.error(f"Capture/OCR failed: {ex}")
        if st.session_state.get("shot_uri"):
            st.markdown(f'<div class="shot"><img src="{st.session_state["shot_uri"]}"></div>', unsafe_allow_html=True)
            st.caption(st.session_state.get("ocr_info", ""))
        else:
            st.markdown('<div class="shot" style="padding:28px"><span class="muted">The captured window '
                        'will be shown here.</span></div>', unsafe_allow_html=True)
    with colR:
        st.markdown("##### 2 · Read, summarize or translate")
        text = st.text_area("Extracted screen text", key="ocr_text", height=150,
                            placeholder="Text from the window appears here. You can also type or paste text.")
        have = bool(text.strip())
        r1, r2 = st.columns(2)
        if r1.button("🔊 Read aloud", key="ra_src", disabled=not have, use_container_width=True):
            speaker.speak(text, S.detect_lang(text))
        if r2.button("⏹ Stop speech", key="stop_src", use_container_width=True):
            speaker.stop()
        a1, a2, a3 = st.columns([1, 1.1, 1])
        with a2:
            tgt = st.selectbox("Translate into", list(S.LANG_LABELS), format_func=lambda l: S.LANG_LABELS[l],
                               label_visibility="collapsed")
        if a1.button("Summarize", disabled=not have, use_container_width=True):
            with st.spinner("Summarizing..."):
                out, prov = S.summarise(text, cfg)
            st.session_state.update(ai_out=out, ai_note=f"Summary · {prov}", ai_lang=S.detect_lang(text))
        if a3.button("Translate", disabled=not have, use_container_width=True):
            with st.spinner("Translating..."):
                out, prov = S.translate(text, tgt, cfg)
            st.session_state.update(ai_out=out, ai_note=f"Translation to {S.LANG_LABELS[tgt]} · {prov}", ai_lang=tgt)
        out_now = st.session_state.get("ai_out", "")
        if out_now:
            st.text_area(st.session_state.get("ai_note", "Result"), out_now, height=130)
            q1, q2 = st.columns(2)
            if q1.button("🔊 Read aloud", key="ra_out", use_container_width=True):
                speaker.speak(out_now, st.session_state.get("ai_lang") or S.detect_lang(out_now))
            if q2.button("⏹ Stop speech", key="stop_out", use_container_width=True):
                speaker.stop()
        if getattr(speaker, "last_error", ""):
            st.warning(speaker.last_error)
        st.caption("Automatic source-language detection · English, Kannada, Hindi, Tamil and Telugu")

# ================================================================== MAX Voice
with tab_voice:
    from modules.voice import COMMANDS
    st.markdown("## MAX Voice")
    st.caption("Control the app you are using with your voice. Three quick steps - then just speak.")

    st.markdown('<div class="step">Step 1 · Choose where commands go</div>', unsafe_allow_html=True)
    if "voice_wins" not in st.session_state:
        st.session_state["voice_wins"] = context.list_windows()
    s1, s2 = st.columns([6, 1])
    if s2.button("↻ Refresh", use_container_width=True, help="Reload the list of open windows"):
        st.session_state["voice_wins"] = context.list_windows()
    vwins = st.session_state["voice_wins"]
    vlabels = {None: "Automatic - the last app I used (recommended)"}
    vlabels.update({w["hwnd"]: context.window_label(w) for w in vwins})
    choice = s1.selectbox("Target window", list(vlabels), format_func=lambda h: vlabels.get(h, "(window closed)"),
                          label_visibility="collapsed",
                          help="Voice commands are sent to this window. Automatic follows the last window you used "
                               "outside this dashboard.")
    ctl.target_hwnd = choice
    if choice is None:
        ext = ctl.last_external
        who = context.window_label(ext) if ext else "no app used yet"
        prof = context.profile_for(ext["title"], ext["process"]) if ext else "Default"
    else:
        w = next((x for x in vwins if x["hwnd"] == choice), None)
        who = context.window_label(w) if w else "(window closed)"
        prof = context.profile_for(w["title"], w["process"]) if w else "Default"
    st.caption(f"Commands will go to: {who} · profile: {prof}")

    st.markdown('<div class="step">Step 2 · Allow commands to act</div>', unsafe_allow_html=True)
    on = ctl.policy.controls_enabled
    if st.button("Pause computer control" if on else "Enable computer control", key="v_ctrl",
                 type="secondary" if on else "primary"):
        ctl.set_controls(not on)
        st.rerun()
    st.caption("Voice commands only act while computer control is enabled "
               f"(now: {'enabled' if on else 'paused'}).")

    st.markdown('<div class="step">Step 3 · Start listening</div>', unsafe_allow_html=True)
    b1, b2 = st.columns([1, 1])
    active = ctl.voice.active
    if b1.button("⏹ Stop listening" if active else "🎙 Start listening", key="v_listen", type="primary",
                 use_container_width=True):
        ctl.set_voice(not active)
        st.rerun()
    if b2.button("Push-to-talk · say just one command", use_container_width=True):
        ctl.push_to_talk()
    st.caption("Tip: you can also hold your mouth open for about a second (Facial interaction) to start or stop listening.")

    @st.fragment(run_every=0.7)
    def voice_live():
        e = html.escape
        st.markdown(alert_html(), unsafe_allow_html=True)
        st.markdown('<div class="tag">What I heard</div>', unsafe_allow_html=True)
        if ctl.voice_log:
            rows = []
            for t, heard, res in ctl.voice_log:
                cls = "no" if res == "not a command" else ("blocked" if "blocked" in res else "ok")
                icon = {"no": "–", "blocked": "⏸", "ok": "✓"}[cls]
                rows.append(f'<div><b>{e(t)}</b> &nbsp; “{e(heard)}” &nbsp; <span class="{cls}">{icon} {e(res)}</span></div>')
            st.markdown(f'<div class="heard">{"".join(rows)}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="heard no">Nothing yet - start listening and say a command.</div>',
                        unsafe_allow_html=True)

    voice_live()
    with st.expander("What you can say", expanded=True):
        groups = {"Mouse": ["click", "right click", "scroll up", "scroll down"],
                  "Browser": ["go back", "refresh", "new tab", "close tab", "search <your words>"],
                  "Music & video": ["play", "pause", "next track", "previous track", "mute"],
                  "Slides & files": ["next slide", "previous slide", "save"]}
        cols = st.columns(4)
        for col, (title, items) in zip(cols, groups.items()):
            chips = "".join(f"<span>{html.escape(i)}</span>" for i in items)
            col.markdown(f'<div class="chip-title">{title}</div><div class="chips">{chips}</div>',
                         unsafe_allow_html=True)

# ================================================================== Settings
with tab_settings:
    st.markdown("## Application profiles")
    st.caption("Profiles are selected automatically from the active application. Manual selection is available "
               "when automatic switching is disabled.")
    ctl.auto_profile = st.toggle("Automatic context switching", value=True,
                                 help="Detect the active application and choose its gesture profile.")
    ctl.manual_profile = st.selectbox("Manual profile", PROFILE_NAMES, index=PROFILE_NAMES.index("Default"),
                                      disabled=ctl.auto_profile)
    ext = ctl.last_external
    st.caption(f"Current application: {(ext or {}).get('title') or '—'} · Applied profile: {ctl.profile}")
    st.divider()

    st.markdown("## Camera performance")
    st.caption("Choose the frame-rate request sent to the webcam. The camera and computer determine the actual "
               "processing rate.")
    cA, cB = st.columns(2)
    fps_opts = {"15 FPS": 15, "24 FPS": 24, "30 FPS · recommended": 30, "60 FPS": 60}
    ctl.camera_fps = fps_opts[cA.selectbox("Camera FPS target", list(fps_opts), index=2)]
    ctl.camera_index = int(cB.number_input("Camera index", 0, 10, 0, help="Try 1 if the wrong camera opens."))
    st.caption("Restart the camera after changing these settings. A higher requested FPS does not guarantee "
               "higher accuracy or throughput.")
    st.divider()

    st.markdown("## Facial interaction")
    sens = {"Low (fewer accidental triggers)": 0.75, "Normal": 1.0, "High (easier to trigger)": 1.25}
    ctl.face_sensitivity = sens[st.selectbox("Sensitivity", list(sens), index=1,
                                             help="High makes winks and the open-mouth gesture easier to trigger.")]
    st.caption("Winks click and a held-open mouth turns MAX Voice on or off. Press Recalibrate face (Interaction "
               "modes → How facial interaction works) after changing lighting.")
    st.divider()

    with st.expander("Advanced · play / next / previous do nothing? Open this"):
        st.caption("Normally you do not need to change anything here. It only matters if your music or video "
                   "player ignores the Media profile gestures (C1 play/pause, C2 previous, C3 next, C4 mute) or "
                   "the voice commands play, pause, next track and previous track.")
        method = st.radio("How should play / pause / next / previous reach your player?",
                          ["Windows media keys (works with most players)",
                           "Keyboard keys sent to the player window (use if the first one does nothing)"])
        ctl.actions.media_method = "keys" if method.startswith("Windows") else "window"
        if ctl.actions.media_method == "window":
            k1, k2, k3 = st.columns(3)
            ctl.actions.window_keys["play_pause"] = k1.text_input("Play/pause key", "space")
            ctl.actions.window_keys["next_track"] = k2.text_input("Next track key", "ctrl+right")
            ctl.actions.window_keys["prev_track"] = k3.text_input("Previous track key", "ctrl+left")
            st.caption("Examples: space, shift+n, ctrl+right. The player window is brought to the front first.")
        st.caption("Try it: start a song, enable computer control, then press a button.")
        t1, t2, t3 = st.columns(3)
        for col, (label, act) in zip((t1, t2, t3), [("â¯ Play / pause", "play_pause"), ("â­ Next track", "next_track"),
                                                    ("â® Previous track", "prev_track")]):
            if col.button(label, use_container_width=True):
                if ctl.actions.enabled:
                    ctl.actions.shortcut(act, source="test")
                else:
                    st.warning("Enable computer control first (Interaction modes tab).")

# ================================================================== About & limitations
with tab_about:
    st.markdown("## About & limitations")
    st.markdown("""
**Multimodal Touchless Human-Computer Interaction Engine** is a Windows-focused academic prototype combining
hand gestures, optional facial interaction, application-aware shortcuts, MAX Voice and Screen AI.

**Privacy**
- Camera frames are processed locally and are not stored.
- MAX Voice sends command audio to Google's speech recognizer; Screen AI may send text to Google Translate or Gemini.
- Screen AI captures only the window you select.
- PINs and recovery codes are stored as salted PBKDF2 verifiers in `user_data/access.json`.

**Limitations**
- Gesture and facial thresholds are heuristic and depend on camera, lighting, pose and user.
- Application targeting uses window titles and process names; browser pages are not inspected.
- Keyboard shortcuts vary by application and need that application ready to receive input.
- Speech recognition, Google Translate, Gemini and Indic text-to-speech need internet access.
- CPU and memory readings are system-wide, not per-process.
- The local PIN is a prototype access gate, not an enterprise identity system. Facial interaction is not authentication.
""")

# ================================================================== Account settings
with tab_account:
    st.markdown("## Account settings")
    st.caption(f"Manage local credentials for {user}. Login uses username and PIN, not face authentication.")
    t_user, t_pin, t_rec = st.tabs(["Change username", "Change PIN", "Recovery code"])
    with t_user:
        cur = st.text_input("Current PIN", type="password", key="cu_pin")
        new_u = st.text_input("New username", value=user, key="cu_new")
        if st.button("Update username", type="primary"):
            try:
                st.session_state["user"] = store.change_username(user, cur, new_u)
                st.success("Username updated.")
                st.rerun()
            except AccountError as e:
                st.error(str(e))
    with t_pin:
        cur = st.text_input("Current PIN", type="password", key="cp_cur")
        n1 = st.text_input("New PIN (6-12 digits)", type="password", key="cp_n1")
        n2 = st.text_input("Confirm new PIN", type="password", key="cp_n2")
        if st.button("Update PIN", type="primary"):
            if n1 != n2:
                st.error("The new PINs do not match.")
            else:
                try:
                    store.change_pin(user, cur, n1)
                    st.success("PIN updated.")
                except AccountError as e:
                    st.error(str(e))
    with t_rec:
        st.caption("Generating a new code replaces the old one. It is shown once - store it safely.")
        cur = st.text_input("Current PIN", type="password", key="cr_cur")
        if st.button("Generate new recovery code", type="primary"):
            try:
                st.code(store.new_recovery_code(user, cur))
            except AccountError as e:
                st.error(str(e))
    if st.button("Log out"):
        ctl.set_controls(False)
        st.session_state.pop("user", None)
        st.rerun()

