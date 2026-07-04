# Baking Companion — Hardware

> Status: **DECIDED (2026-07-03).** Old Android phone is the single device. Python
> backend in Termux serves a local web UI the phone's browser opens. Kitchen footprint
> = just the phone on its stand. Secondary camera deferred (cheap Wi-Fi/USB-C webcam,
> not the Pi).

## Decision summary

**Phone-only hybrid.** FastAPI (Python) runs in **Termux on the phone**, serving a UI at
`http://localhost:PORT`. The phone's **Chrome** opens it (kiosk/PWA). The **browser**
handles mic, speaker, camera, and the custom UI; **Python** handles FSM / router /
memory / timers / cloud LLM. They talk over a **localhost WebSocket**. This merges the
Termux and PWA options onto one device — the "server" is Termux on the same phone, so
there is no separate machine and no LAN dependency.

Key wins:
- **Custom UI** = your own HTML/CSS/JS (auto-listen toggle, per-bake cards, live camera
  preview, side-by-side comparison). Served by the Python backend.
- **Web Speech API** in the browser gives STT (`webkitSpeechRecognition`, continuous
  mode) + TTS (`speechSynthesis`); `getUserMedia` gives camera with live preview. This
  **dissolves the Termux record-to-file wake-word problem** — the browser streams
  continuous STT and we watch the transcript for a trigger word.
- Served over `http://localhost` = **secure context**, so camera/mic/Web Speech work
  with **no HTTPS/cert hassle**.

Caveats (livable, deferred):
- Browser listening pauses when **screen off / tab backgrounded** — fine for a
  plugged-in, screen-on kiosk; true always-on needs a small native helper later
  (optional, not core).
- Web Speech STT is **Google-cloud-backed** (needs internet; Tier-0 voice not fully
  offline). Swap to on-device Vosk/whisper later if desired. 6 GB RAM leaves room.

## Available

- Raspberry Pi 3 (quad A53, 1 GB RAM) and ASUS Tinker Board (2 GB) — weak SBCs.
- Logitech USB webcam (may upgrade).
- Laptop with RTX 5070 Ti — capable, but user does NOT want it as a required touchpoint
  (open-source usability) and judges 3–7B local reasoning insufficient vs Claude/Gemini.
- USB + Bluetooth speakers.
- **Old phone: Motorola One Fusion** — Snapdragon 710, **6 GB RAM**. Fully functional
  except the power button. Has camera, mic, speaker, screen, Wi-Fi, battery, storage,
  Google Photos backup. Far more capable and integrated than the Pi. **Chosen device.**
- No small display purchased.

## The pivot: phone as the single primary device

The phone collapses most touchpoints into one integrated, energy-efficient device —
and for open-source users, "install on any old Android phone" beats "buy + wire a Pi,
mic, screen, speaker." It can even run the Tier-0 brain locally (Python) and only
reach the cloud for Tier-1 reasoning → **one device + an API key**.

### Software path options (avoid Android Studio)

- **Path A — Termux + termux-api (Python-native).** Full Linux + Python on-device.
  `termux-camera-photo`, `termux-microphone-record`, `termux-tts-speak`,
  `termux-notification`, sensors, `termux-wake-lock`. No Android Studio, no APK build.
  Best fit for a Python-first data scientist; lets us build the whole graph/FSM brain
  on the phone immediately.
  - Caveat: `termux-microphone-record` records to a file (not a live PCM stream), so
    **continuous wake-word is awkward** — chunked record + VAD, or push-to-talk to start.
- **Path B — thin native wrapper** just for wake-word + audio + camera, handing off to
  the Python brain. Best hands-free UX; costs some Kotlin + build tooling.
- **Path C — PWA (browser as thin client).** Zero-install URL; Web Speech API gives
  STT + TTS (Chrome/Android, cloud-backed, free). Brain runs on a server (laptop/mini-PC/
  cloud). Great for distribution, but **weakest on always-on hands-free** (backgrounded
  tabs suspend) and adds a hosted-brain touchpoint for others.

**Tentative recommendation:** start on **Path A (Termux)** — build the graph core in
pure Python on the phone, push-to-talk or chunked-listen at first, cloud for Tier-1.
Add robust wake-word later; that is the one place a small native helper or the Pi could
re-enter.

### Hands-free tension

Always-on wake word with screen off is the hard bit on Android without a native
foreground service. Options: chunked-record wake word in Termux (works-ish, battery),
a BT button for push-to-talk (not fully hands-free), or a minimal native helper (Path B).
Decide how hard-core wake-word must be at MVP.

## Secondary Wi-Fi camera — DEFERRED

The phone screen faces the user while capture wants a top/angled view, so a second
angle is useful eventually. **Decision: defer, and do NOT use the Pi for it** — parking
the Pi + charger in the kitchen isn't worth it. When added, prefer a **cheap Wi-Fi or
USB-C-connected webcam**. For now the phone alone covers capture, and staying close
enough keeps its mic usable.

**Pi 3 / Tinker Board:** kept in reserve as an optional always-on wake-word helper or
dev box — not in the kitchen.

## Notes

- Phone stays plugged in on the stand for multi-day bakes (screen on); battery is a
  portability bonus.
- Far-field mic may be weak if the phone sits across the kitchen — a BT/USB mic or
  speaker near the user can help (you have BT speakers).
- Google Photos backup is a safety net, NOT the primary store — our app owns the
  tagged media + metadata.
- iOS would be worse (no Termux); Android is the right platform and you have it.
