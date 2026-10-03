# 🚀 Autonomous Viral Reels Engine (Quality Upgrade Suite)

![YouTube Master Autopilot](https://github.com/mayanksllm/youtube-autopilot/actions/workflows/daily_autopilot.yml/badge.svg)

An industrial-grade, 100% autonomous YouTube Shorts and Instagram Reels production engine. Engineered with an automated **Multi-Tier AI Failover Cascade** across scripting, image generation, voice synthesis, thumbnail creation, and community engagement.

---

## 🌟 Quality Upgrade Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. VARIETY & COOLDOWN ENGINE (yt_variety.py)                                │
│   • Persistent store: variety_store.json (tracks production history)        │
│   • Cooldowns: Visual Style: 15 videos | Hook: 4 | Camera: 3 | Caption: 4   │
│                Music Mood: 4 | Voice: 3 | Topic Category: 3                 │
│   • Freshness Gate: is_fresh() uses similarity checks (Jaccard + Sequence)  │
│     on topics, titles, and scene prompts with a configurable threshold.     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. MULTI-SOURCE TREND RESEARCH & CONTRARIAN ANGLES (trend_aggregator.py)     │
│   • YouTube Data API: regionCode=IN / Category 27 mostPopular videos        │
│   • Google Trends RSS: India (geo=IN) & US real-time trending queries       │
│   • Reddit Breakouts: r/todayilearned, r/damnthatsinteresting, r/science    │
│     (with automatic fallback from keyless JSON to RSS / topic vaults)       │
│   • Contrarian Angle: LLM synthesizes an original paradox angle; never      │
│     summarizes or copies the raw trend.                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. TWO-PASS SCRIPTWRITER + ADVERSARIAL CRITIC (script_critic.py)             │
│   • Pass 1 (Writer): Crafts 6-scene viral narrative with loop hook          │
│   • Pass 2 (Critic): Evaluates Hook (1-10), Pacing (1-10), Retention (1-10) │
│   • Auto-Rewrite Gate: If composite score < 7.0, triggers focused rewrite   │
│   • Model Cascade: Gemini 3.8/3.6/3.5-flash → Groq → OpenRouter → Fallback  │
├─────────────────────────────────────────────────────────────────────────────┤
│ 4. VISUAL STYLE DNA, PARALLAX MOTION & VISION GATE (visual_quality_gate.py) │
│   • Visual DNA: Single style reference prompt injected into all scenes      │
│   • Motion: Ken Burns 2.5D dynamic parallax zoom & pan                      │
│   • Captions: Dynamic animated word-by-word active text highlighting        │
│   • Post-Processing: Cinematic 35mm film grain & color grading in FFmpeg    │
│   • Quality Gate: Validates image size, luminance (10-248), entropy, and    │
│     Gemini Vision inspection (regenerates blurry or artifacted images)      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 5. 3-VARIANT THUMBNAIL GENERATOR & CTR SCORING (thumbnail_generator.py)     │
│   • Generates 3 visual variants: Close-Up Yellow, Neon Cyan, Golden Amber   │
│   • Strict Rule: <= 3 words bold, high-contrast overlay text                │
│   • Vision CTR Ranking: AI Vision model selects the highest-CTR winner      │
│   • Uploads via thumbnails().set() with graceful local fallback             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 6. COMMUNITY MANAGER & AUTO-REPLIES (community_manager.py)                  │
│   • Pinned Question: Posts top-level engagement question on upload          │
│   • Auto-Replies: Channel-only (allThreadsRelatedToChannelId)               │
│   • Smart Filters: Skips spam, promo links, and negative/toxic comments     │
│   • Anti-Repetition: Generates unique, non-repeating empathetic replies;   │
│     logs replied IDs in variety_store.json to never reply twice             │
├─────────────────────────────────────────────────────────────────────────────┤
│ 7. QUOTA MANAGEMENT & GRACEFUL DEGRADATION (autopilot_config.py)            │
│   • Daily budget: 10,000 units (resets at 00:00 Pacific Time)               │
│   • Cost tracking: videos.insert (1600), thumbnails.set (50), comments (50) │
│   • Safety Gate: Stops gracefully with code 0 when quota is below safety    │
│     margin (1750 units) instead of failing GitHub Actions builds            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📌 Important YouTube API Notes

### 1. Comment Pinning in YouTube Studio
> [!NOTE]
> The YouTube Data API v3 does **not** support setting a comment as pinned via API.
> The pipeline posts your engagement question as a normal top-level comment on your video via `commentThreads().insert`.
> **To pin it:** Open **YouTube Studio** or the **YouTube mobile app**, find your uploaded Short, click the **3 dots** beside the top comment, and select **"Pin"** (1 click).

### 2. Custom Thumbnail Permissions & Verification
> [!IMPORTANT]
> The YouTube Data API endpoint `thumbnails().set` requires an **account verified via phone number** in YouTube Studio (Feature Eligibility -> Intermediate Features).
> - If your channel is verified, the winning thumbnail is automatically set on YouTube.
> - If your channel is not yet phone-verified, YouTube returns HTTP 403 `thumbnailUploadDisabled`.
> - **Zero-Crash Resilience:** The engine catches this error gracefully, logs a helpful reminder, and preserves the winning thumbnail locally in `assets/thumbnails/` so your workflow never fails.

### 3. API Quota Budgeting
> [!TIP]
> Google gives every YouTube Data API project **10,000 free quota units per day**, resetting at **00:00 Pacific Time (12:30 PM / 1:30 PM IST)**.
> - Video upload: `~1600` units
> - Thumbnail upload: `50` units
> - Top-level comment: `50` units
> - Auto-reply: `50` units
> - Comment listing: `1` unit
>
> The built-in `QuotaManager` monitors consumption across runs and stops gracefully when remaining units are below 1750, ensuring zero failed workflow runs.

---

## 🌐 Consolidated GitHub Actions Workflow

All legacy, overlapping workflows have been consolidated into **one master workflow**:
- [`.github/workflows/daily_autopilot.yml`](.github/workflows/daily_autopilot.yml)

### Schedule (Peak Indian Discovery Windows):
- `02:00 UTC` (7:30 AM IST) — Morning discovery surge.
- `11:00 UTC` (4:30 PM IST) — Evening Indian commute & leisure window.

### Manual Trigger (`workflow_dispatch`):
You can manually run the pipeline anytime from GitHub Actions tab:
- **pipeline**: `autonomous_viral_reels` (default) or `daily_autopilot`
- **dry_run**: `true` (test without uploading) or `false` (publish live)

---

## 🧪 Testing Locally Before Pushing

Run these commands in PowerShell or Bash to verify the quality upgrades locally:

```bash
# 1. Test Variety Engine & Cooldowns
python -c "from yt_variety import variety_engine; print(variety_engine.pick_production_bundle())"

# 2. Test Multi-Source Trend Aggregator
python -c "from trend_aggregator import trend_aggregator; print(trend_aggregator.get_fresh_trend_topic('psychology_thrillers'))"

# 3. Test Script Critic Quality Gate
python -c "import script_critic; print('Critic engine ready')"

# 4. Test Visual Quality Gate
python -c "import visual_quality_gate; print('Visual quality gate ready')"

# 5. Test 3-Variant Thumbnail Generator (Dry-Run)
python -c "from thumbnail_generator import thumbnail_generator; print(thumbnail_generator.produce_3_variants('The Ambergris Mystery', 'psychology_thrillers'))"

# 6. Test Community Manager & Spam Filter
python -c "from community_manager import community_manager; print('Constructive:', community_manager.is_constructive_comment('Amazing video!'), 'Spam:', community_manager.is_constructive_comment('Subscribe here http://spam.com'))"

# 7. Run Full Pipeline Dry-Run (Renders complete video locally, tests all gates without uploading)
python autonomous_viral_reels_engine.py --dry-run
```

---

## 🔒 Security & Git Hygiene

- `client_secret*.json`, `token*.json`, `.env`, and secret keys are protected by `.gitignore` and **must never be committed to git**.
- The git commit history on branch `quality-upgrade` has been verified clean of all credentials and tokens.
- In production / GitHub Actions, credentials are fed securely via repository secrets:
  - `YOUTUBE_TOKEN_JSON`
  - `CLIENT_SECRETS_JSON`
  - `YOUTUBE_CLIENT_SECRET_BASE64`
  - `YOUTUBE_REFRESH_TOKEN`
  - `GEMINI_API_KEY`
  - `GROQ_API_KEY`
