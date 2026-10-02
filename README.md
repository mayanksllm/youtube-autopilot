# 🚀 Autonomous Viral Reels Engine (Zero-Cost Failover Cascade)

![Daily YouTube Autopilot](https://github.com/mayanksllm/youtube-autopilot/actions/workflows/daily_reels.yml/badge.svg)

An industrial-grade, 100% autonomous YouTube Shorts and Instagram Reels production pipeline. Built with an automated **Multi-Tier AI Failover Cascade** across scriptwriting, image generation, and voice synthesis. If any API is rate-limited (HTTP 429), expires, or fails, the engine seamlessly cascades down to keyless, zero-cost tiers without crashing.

---

## ⚡ Multi-Tier Failover Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. SCRIPT GENERATION CASCADE (Chain of 5 Providers)                    │
│   • Tier 1: Google Gemini 2.5 Flash API (Free Tier key)                │
│   • Tier 2: Groq Cloud API (llama-3.3-70b-versatile, free high-speed)  │
│   • Tier 3: DeepSeek Free API / OpenRouter Free Tier                   │
│   • Tier 4: Cohere API (command-r free tier)                           │
│   • Tier 5: Pollinations AI Text (100% Keyless Emergency Tier)         │
│   • Strict Schema: title, voiceover_clean (Hindi), pinned_comment,      │
│     and 6 distinct scene visual prompts.                               │
├────────────────────────────────────────────────────────────────────────┤
│ 2. VISUAL GENERATION CASCADE (Chain of 4 Free Engines)                 │
│   • Tier 1: Pollinations AI FLUX (1080x1920, 9:16 vertical, keyless)   │
│   • Tier 2: Hugging Face Serverless Inference (FLUX.1-schnell)         │
│   • Tier 3: Together AI Free Tier (SDXL 1.0)                           │
│   • Tier 4: Local Dynamic B-Roll Vault (assets/fallback_vault/)        │
│   • Quality Gate: File size > 30KB & luminance >= 10.0 (no black cuts) │
├────────────────────────────────────────────────────────────────────────┤
│ 3. VOICE SYNTHESIS CASCADE (Chain of 3 Providers)                      │
│   • Tier 1: edge-tts voice 'hi-IN-MadhurNeural' (rate: +10%)           │
│   • Tier 2: edge-tts voice 'hi-IN-SwaraNeural' (rate: +10%)            │
│   • Tier 3: Local gTTS (Google Translate Hindi TTS fallback)           │
├────────────────────────────────────────────────────────────────────────┤
│ 4. REMOTION-GRADE VIDEO COMPOSITOR & AUDIO MASTERING                   │
│   • Dynamic 2.5D Camera Dolly-in Zoom & Pan                            │
│   • Center-aligned 48pt uppercase yellow active-word captions          │
│   • Broadcast Audio Mix: Voiceover 0dB, Impact SFX -16dB, Music -22dB  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Cloud Execution: Public Repository Mode

In a **public GitHub repository**, GitHub Actions provides **unlimited minutes for standard Linux runners**:
- The workflow [`.github/workflows/daily_reels.yml`](.github/workflows/daily_reels.yml) executes twice daily on schedule:
  - `02:00 UTC` (7:30 AM IST) — Morning discovery surge.
  - `11:00 UTC` (4:30 PM IST) — Evening Indian leisure & commute window.
- All secrets are injected through repository **Settings → Secrets and variables → Actions**.
- Production history is automatically tracked in [`history_log.json`](history_log.json) and committed back to the repository on each run with `[skip ci]`.

---

## 💻 Alternative: Self-Hosted Local Background Daemon

If you prefer to run production locally on your personal computer or laptop so that jobs **never consume GitHub cloud quotas or actions**:

### On Linux / macOS / Git Bash:
```bash
chmod +x run.sh
./run.sh
```
To run as a recurring background daemon (e.g., via cron or systemd):
```bash
# Add to crontab (crontab -e) to run at 8:00 AM and 5:00 PM daily:
0 8,17 * * * cd /path/to/youtube_automation && ./run.sh >> autopilot.log 2>&1
```

### On Windows:
```cmd
run_autopilot.bat
```
Or register a Windows Scheduled Task using the provided PowerShell script:
```powershell
powershell -ExecutionPolicy Bypass -File .\set_task_settings.ps1
```

---

## 🔑 Environment Setup (`.env.example`)

Copy [`.env.example`](.env.example) to `.env` and fill in whichever keys you have. Remember: **all keys are optional** — the cascade handles missing keys gracefully:

```ini
# Optional Free Scripting Keys
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
COHERE_API_KEY=your_cohere_api_key

# Optional Free Visual Keys
HF_TOKEN=your_huggingface_token
TOGETHER_API_KEY=your_together_api_key

# YouTube Upload Credentials (Optional for dry-runs)
CLIENT_SECRETS_JSON={"installed":{...}}
YOUTUBE_TOKEN_JSON={"token":...}
```

---

## 📁 Repository Structure
- `autonomous_viral_reels_engine.py` — Main master pipeline with multi-tier failover
- `autonomous_viral_reels_engine.json` — Exact pipeline specification
- `run.sh` / `run_autopilot.bat` — Local self-hosted daemon runners
- `.github/workflows/daily_reels.yml` — Automated cloud production workflow
- `history_log.json` — 30-upload lookback memory to prevent topic repetition
- `assets/fallback_vault/` — Verified high-res royalty-free fallback visuals
