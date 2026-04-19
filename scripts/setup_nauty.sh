#!/usr/bin/env bash
set -e

if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: no active conda/micromamba environment detected."
    echo "  micromamba activate k4free"
    exit 1
fi

NAUTY_VERSION="2_9_3"
SRC_DIR="$CONDA_PREFIX/src"
NAUTY_TAR="nauty${NAUTY_VERSION}.tar.gz"
NAUTY_DIR="$SRC_DIR/nauty${NAUTY_VERSION}"

# ── Build nauty ───────────────────────────────────────────────────────────────

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

if [ ! -f "$NAUTY_TAR" ]; then
    echo "Downloading nauty ${NAUTY_VERSION}..."
    wget "https://pallini.di.uniroma1.it/$NAUTY_TAR"
fi

if [ ! -d "$NAUTY_DIR" ]; then
    tar xzf "$NAUTY_TAR"
fi

cd "$NAUTY_DIR"

if [ ! -f "config.status" ]; then
    ./configure
fi

make
echo "nauty built at $NAUTY_DIR"

# Register nauty binaries on environment activation
ACTIVATE_DIR="$CONDA_PREFIX/etc/conda/activate.d"
mkdir -p "$ACTIVATE_DIR"
cat > "$ACTIVATE_DIR/nauty_path.sh" <<EOL
#!/usr/bin/env bash
export PATH="$NAUTY_DIR:\$PATH"
EOL
chmod +x "$ACTIVATE_DIR/nauty_path.sh"
export PATH="$NAUTY_DIR:$PATH"

# ── Install pynauty ───────────────────────────────────────────────────────────
# We install pynauty here rather than in environment.yml so we can guarantee
# the C compiler chain is working (nauty just built successfully above) and
# set the macOS SDK root before pip tries to compile C extensions.

if [[ "$(uname)" == "Darwin" ]]; then
    SDK=$(xcrun --show-sdk-path 2>/dev/null || true)
    if [ -n "$SDK" ]; then
        export SDKROOT="$SDK"
        echo "macOS SDK: $SDKROOT"
    else
        echo "WARNING: xcrun not found — Xcode Command Line Tools are not installed."
        echo "  pynauty requires them to compile on macOS. Run:"
        echo "    xcode-select --install"
        echo "  then re-run this script."
        echo "  The project works without pynauty (falls back to WL-hash dedup)."
        exit 0
    fi
fi

echo "Installing pynauty..."
pip install pynauty==2.8.8.1

echo ""
echo "Done. nauty binaries and pynauty are ready."
echo "nauty PATH entry will activate automatically with the environment."
