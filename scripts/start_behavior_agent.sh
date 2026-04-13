#!/bin/bash
# ============================================
# PANDORA Behavior Agent — Launcher
# ============================================
# Installs dependencies and starts the noise monitor.
#
# Usage:
#   ./start_behavior_agent.sh                          # Default: localhost:8000
#   ./start_behavior_agent.sh http://192.168.1.10:8000 # Custom server
#   ./start_behavior_agent.sh --test                   # Dry-run mode
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOKEN_FILE="$PROJECT_DIR/.behavior_agent_token"
AGENT_SCRIPT="$SCRIPT_DIR/behavior_agent.py"
SERVER_URL="${1:-https://pandora-academy.onrender.com}"

echo "═══════════════════════════════════════════════"
echo "  🔊 PANDORA Behavior Agent"
echo "═══════════════════════════════════════════════"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ python3 not found. Please install Python 3.8+"
    exit 1
fi

# Install dependencies
echo "📦 Checking dependencies..."
python3 -m pip install --quiet sounddevice numpy scipy requests 2>/dev/null || {
    echo "⚠️  pip install failed. Trying with --user..."
    python3 -m pip install --user --quiet sounddevice numpy scipy requests
}
echo "✅ Dependencies OK"

# Check token
if [ ! -f "$TOKEN_FILE" ]; then
    echo "❌ Token file not found: $TOKEN_FILE"
    echo "   Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\" > $TOKEN_FILE"
    exit 1
fi

TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
if [ -z "$TOKEN" ]; then
    echo "❌ Token file is empty: $TOKEN_FILE"
    exit 1
fi
echo "🔑 Token loaded (${#TOKEN} chars)"

# Handle arguments
if [ "$1" = "--test" ]; then
    echo ""
    echo "🧪 Running in DRY-RUN mode (no reports sent)"
    echo "═══════════════════════════════════════════════"
    echo ""
    python3 "$AGENT_SCRIPT" --test --token "$TOKEN"
else
    echo "📡 Server: $SERVER_URL"
    echo "═══════════════════════════════════════════════"
    echo ""
    python3 "$AGENT_SCRIPT" --server "$SERVER_URL" --token "$TOKEN"
fi
