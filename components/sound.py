"""
components/sound.py
-------------------
In-tab notifications for price-condition triggers: a chime + a tab flash.

When a tracked stock newly satisfies one of its price conditions, we play a
short, attention-grabbing rising chime from the active browser tab AND flash
the browser tab itself (alternating title + a red bell favicon), so the hit
is noticeable even from another tab or with the PC muted. The chime is
synthesised on the fly with the Web Audio API (no audio asset needed) and
runs in the app's main document via ``st.html(unsafe_allow_javascript=True)``,
so it plays under the page's existing user activation — i.e. it works as soon
as the user has interacted with the app at all (pressing Start, toggling the
theme, navigating…), which is effectively always.

Detection is transition-based: a notification fires only when a condition
flips from unsatisfied to satisfied — never on every refresh while it stays
true, and never on the first observation after a condition is (re)configured.
Notifications are always armed; the 🔔 bell on each dashboard card is the
one switch, muting its own stock.
"""

from __future__ import annotations

import json

import streamlit as st

from components.cards import condition_label, condition_satisfied

# ---- session_state keys ----
_PREV_KEY = "_alert_prev"        # "CODE|condition" -> {"sig": str, "sat": bool}
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


# Tab flash: alternate the document title with the alert message and swap the
# favicon to a red bell, so a background DSE tab visibly "rings". Runs in the
# main document; state lives on `window` so it survives Streamlit reruns.
# Stops when the user returns to / clicks the tab, or after __SECS__ seconds.
_FLASH_HTML = """
<span style="display:none">dse-tabflash-__NONCE__</span>
<script>
(function(){
  var d = window.document;
  try {
    if(!window.__dseTabFlash){
      window.__dseTabFlash = { title: d.title, icon: null, timer: null };
      var back = function(){ if(!d.hidden && window.__dseFlashStop){ window.__dseFlashStop(); } };
      d.addEventListener("visibilitychange", back);
      window.addEventListener("focus", function(){ if(window.__dseFlashStop){ window.__dseFlashStop(); } });
      d.addEventListener("click", function(){ if(window.__dseFlashStop){ window.__dseFlashStop(); } });
    }
    var S = window.__dseTabFlash;
    function setIcon(href){
      if(!href){ return; }
      var link = d.querySelector('link[rel~="icon"]');
      if(!link){ link = d.createElement("link"); link.rel = "icon"; d.head.appendChild(link); }
      link.href = href;
    }
    window.__dseFlashStop = function(){
      if(S.timer){ clearInterval(S.timer); S.timer = null; }
      d.title = S.title;
      setIcon(S.icon);
    };
    // red bell favicon, drawn on the fly (no asset needed)
    function bellIcon(){
      var c = d.createElement("canvas"); c.width = 64; c.height = 64;
      var x = c.getContext("2d");
      x.beginPath(); x.arc(32, 32, 30, 0, 2 * Math.PI);
      x.fillStyle = "#ef4444"; x.fill();
      x.font = "38px serif"; x.textAlign = "center"; x.textBaseline = "middle";
      x.fillText("\\uD83D\\uDD14", 32, 35);
      return c.toDataURL("image/png");
    }
    window.__dseFlashStop();               // reset any flash already running
    // (re)capture the CURRENT title/icon — Streamlit changes them per page
    S.title = d.title;
    var iconLink = d.querySelector('link[rel~="icon"]');
    if(iconLink){ S.icon = iconLink.href; }
    var msg = __MSG__, alertIcon = bellIcon();
    var until = Date.now() + __SECS__ * 1000;
    var on = false;
    var swap = function(){
      if(Date.now() > until){ window.__dseFlashStop(); return; }
      on = !on;
      d.title = on ? msg : S.title;
      setIcon(on ? alertIcon : S.icon);
    };
    swap();
    S.timer = setInterval(swap, 900);
  } catch(e) { /* stay quiet */ }
})();
</script>
"""


def flash_tab(message: str, secs: int = 120) -> None:
    """Flash this browser tab (title + red-bell favicon) with ``message``.

    Visible from other tabs / with the sound off. Stops as soon as the user
    returns to or clicks the tab, or after ``secs`` seconds.
    """
    nonce = st.session_state.get(_NONCE_KEY, 0) + 1
    st.session_state[_NONCE_KEY] = nonce
    html = (_FLASH_HTML
            .replace("__MSG__", json.dumps(str(message)))
            .replace("__SECS__", str(int(max(3, secs))))
            .replace("__NONCE__", str(nonce)))
    st.html(html, unsafe_allow_javascript=True)


def _bounds_sig(bounds: dict) -> str:
    """A stable fingerprint of a condition, so reconfiguring it re-seeds."""
    return f'{bounds.get("condition", "range")}|{bounds.get("low")}|{bounds.get("high")}'


def check_and_chime(monitor) -> None:
    """Detect newly-satisfied price conditions, then chime + toast for them.

    Self-seeding and transition-based: every tracked (stock, condition) pair
    keeps its last satisfied state (keyed by the condition's signature) in
    session_state, and a chime fires only on a genuine unsatisfied →
    satisfied flip — each of a stock's several conditions triggers
    independently. The first time a condition is seen — including right
    after it's (re)configured — it seeds silently, so opening the tab on an
    already-satisfied stock, or changing a target, never self-triggers.
    Called from the shared sidebar, so it runs on every page: alerts fire
    wherever the tab is, as long as it's open.

    Stocks whose card 🔔 bell is muted are skipped entirely; for everything
    else a hit toasts, flashes the browser tab AND plays the chime.
    """
    prev = st.session_state.setdefault(_PREV_KEY, {})
    fired = []
    seen = set()
    for code in monitor.get_selected():
        if monitor.is_bell_muted(code):
            continue                         # bell off: no notifications at all
        conditions = monitor.get_price_conditions(code)
        if not conditions:
            continue
        q = monitor.get_quote(code)
        ltp = q.ltp if q is not None else None
        for entry in conditions:
            cond = entry.get("condition", "range")
            key = f"{code}|{cond}"
            seen.add(key)
            sat = condition_satisfied(cond, ltp,
                                      entry.get("low"), entry.get("high"))
            if sat is None:                  # no live price yet — keep last state
                continue
            sig = _bounds_sig(entry)
            rec = prev.get(key)
            prev[key] = {"sig": sig, "sat": sat}
            if rec is None or rec.get("sig") != sig:
                continue                     # first sight / reconfigured: seed
            if sat and not rec.get("sat"):
                fired.append((code, entry))
    # Forget pairs that are no longer tracked, configured, or bell-active.
    for key in list(prev):
        if key not in seen:
            prev.pop(key, None)
    if not fired:
        return
    for code, entry in fired[:5]:
        st.toast(f"**{code}** hit your target — {condition_label(entry)}",
                 icon="🔔")
    if len(fired) == 1:
        code, entry = fired[0]
        flash_tab(f"🔔 {code} hit {condition_label(entry)}")
    else:
        flash_tab(f"🔔 {len(fired)} price targets hit!")
    play_chime(reps=2, vol=0.85)
