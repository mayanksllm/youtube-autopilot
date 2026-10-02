#!/usr/bin/env bash
# =============================================================================
# run.sh - Local Daemon Runner for Autonomous Viral Reels Engine
# =============================================================================
# Runs the engine on your local machine / laptop as a self-hosted runner.
# Never touches GitHub cloud action quotas.

set -e
cd "$(dirname "$0")"

echo "======================================================================"
echo "  🎬 AUTONOMOUS VIRAL REELS ENGINE (Self-Hosted Local Daemon)"
echo "======================================================================"

# Activate virtual environment if available
if [ -d "venv" ]; then
    echo "📦 Activating Python virtual environment (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "📦 Activating Python virtual environment (.venv)..."
    source .venv/bin/activate
fi

# Ensure dependencies are installed
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  [Warning] ffmpeg not found in PATH. The engine will attempt to use imageio-ffmpeg automatically."
fi

# Execute engine
python autonomous_viral_reels_engine.py "$@"
