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

# Register nauty binaries on environment activation. The `geng` and `labelg`
# binaries from this build are the entire nauty dependency — `geng` drives
# brute-force enumeration (search/brute_force.py), `labelg` produces canonical
# labellings for graph_db ids (utils/nauty.canonical_id).
ACTIVATE_DIR="$CONDA_PREFIX/etc/conda/activate.d"
mkdir -p "$ACTIVATE_DIR"
cat > "$ACTIVATE_DIR/nauty_path.sh" <<EOL
#!/usr/bin/env bash
export PATH="$NAUTY_DIR:\$PATH"
EOL
chmod +x "$ACTIVATE_DIR/nauty_path.sh"
export PATH="$NAUTY_DIR:$PATH"

echo ""
echo "Done. nauty binaries (geng, labelg, …) are on PATH via the env"
echo "activation hook. No Python extensions to build — canonical_id shells"
echo "out to labelg directly."
