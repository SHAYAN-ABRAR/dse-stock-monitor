"""
components/sound.py
-------------------
In-tab notification chime for price-condition triggers.

When a tracked stock newly satisfies its price condition, we play a short,
attention-grabbing rising chime from the active browser tab. The chime is
synthesised on the fly with the Web Audio API (no audio asset needed) and
runs in the app's main document via ``st.html(unsafe_allow_javascript=True)``,
so it plays under the page's existing user activation — i.e. it works as soon
as the user has interacted with the app at all (pressing Start, toggling the
theme, navigating…), which is effectively always.

Detection is transition-based: the sound fires only when a condition flips
from unsatisfied to satisfied — never on every refresh while it stays true,
and never on the first observation after a condition is (re)configured.
"""

from __future__ import annotations

import streamlit as st

from components.cards import band_button_label, condition_satisfied

# ---- session_state keys ----
SOUND_KEY = "alert_sound"        # user mute toggle (default on)
_PREV_KEY = "_alert_prev"        # code -> {"sig": str, "sat": bool}
_NONCE_KEY = "_chime_nonce"      # bumped each play so the markup re-executes

# Web Audio chime, played in the main document. __REPS__/__VOL__/__NONCE__ are
# substituted in; the nonce changes the markup every play so Streamlit
# re-renders it and the script runs again (identical markup would be a no-op).
_CHIME_HTML = """
<span style="display:none">dse-chime-__NONCE__</span>
<script>
(function(){
  try {
    var AC = window.AudioContext || window.webkitAudioContext;
    if(!AC){ return; }
    // Reuse one AudioContext for the tab — browsers cap how many you can open.
    if(!window.__dseAudioCtx){ window.__dseAudioCtx = new AC(); }
    var ctx = window.__dseAudioCtx;
    function chime(){
      var notes = [880.0, 1174.66, 1567.98];   // A5 · D6 · G6 — bright, rising
      var step = 0.16, gap = 0.60, reps = __REPS__, vol = __VOL__;
      var t0 = ctx.currentTime + 0.03;
      for(var r = 0; r < reps; r++){
        for(var i = 0; i < notes.length; i++){
          var t = t0 + r * gap + i * step;
          var osc = ctx.createOscillator(), g = ctx.createGain();
          osc.type = "triangle";
          osc.frequency.setValueAtTime(notes[i], t);
          g.gain.setValueAtTime(0.0001, t);
          g.gain.exponentialRampToValueAtTime(vol, t + 0.015);
          g.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);
          osc.connect(g); g.connect(ctx.destination);
          osc.start(t); osc.stop(t + 0.45);
        }
      }
    }
    // Resume first if the context is suspended (it unlocks after any gesture).
    if(ctx.state === "suspended"){ ctx.resume().then(chime).catch(function(){}); }
    else { chime(); }
  } catch(e) { /* autoplay blocked or audio unavailable — stay silent */ }
})();
</script>
"""


def play_chime(*, reps: int = 2, vol: float = 0.85) -> None:
    """Emit the notification chime once in the current browser tab."""
    nonce = st.session_state.get(_NONCE_KEY, 0) + 1
    st.session_state[_NONCE_KEY] = nonce
    html = (_CHIME_HTML
            .replace("__REPS__", str(int(max(1, reps))))
            .replace("__VOL__", f"{float(vol):.3f}")
            .replace("__NONCE__", str(nonce)))
    st.html(html, unsafe_allow_javascript=True)


def _bounds_sig(bounds: dict) -> str:
    """A stable fingerprint of a condition, so reconfiguring it re-seeds."""
    return f'{bounds.get("condition", "range")}|{bounds.get("low")}|{bounds.get("high")}'


def check_and_chime(monitor) -> None:
    """Detect newly-satisfied price conditions, then chime + toast for them.

    Self-seeding and transition-based: each tracked stock's last satisfied
    state (keyed by its condition signature) is held in session_state, and a
    chime fires only on a genuine unsatisfied → satisfied flip. The first time
    a condition is seen — including right after it's (re)configured — it seeds
    silently, so opening the tab on an already-satisfied stock, or changing a
    target, never self-triggers. Called from the shared sidebar, so it runs on
    every page: alerts fire wherever the tab is, as long as it's open.
    """
    prev = st.session_state.setdefault(_PREV_KEY, {})
    enabled = st.session_state.get(SOUND_KEY, True)
    fired = []
    seen = set()
    for code in monitor.get_selected():
        bounds = monitor.get_price_bounds(code)
        if not bounds:
            continue
        seen.add(code)
        cond = bounds.get("condition", "range")
        lo, hi = bounds.get("low"), bounds.get("high")
        q = monitor.get_quote(code)
        ltp = q.ltp if q is not None else None
        sat = condition_satisfied(cond, ltp, lo, hi)
        if sat is None:                      # no live price yet — keep last state
            continue
        sig = _bounds_sig(bounds)
        rec = prev.get(code)
        prev[code] = {"sig": sig, "sat": sat}
        if rec is None or rec.get("sig") != sig:
            continue                         # first sight / reconfigured: seed
        if sat and not rec.get("sat"):
            fired.append((code, bounds))
    # Forget stocks that are no longer tracked or no longer have a condition.
    for code in list(prev):
        if code not in seen:
            prev.pop(code, None)
    if not (fired and enabled):
        return
    for code, bounds in fired[:5]:
        st.toast(f"**{code}** hit your target — {band_button_label(bounds)}",
                 icon="🔔")
    play_chime(reps=2, vol=0.85)
