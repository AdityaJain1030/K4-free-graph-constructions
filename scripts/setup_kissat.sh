#!/usr/bin/env bash
# Build the KISSAT SAT solver into the active conda/micromamba environment,
# registering its binary directory on PATH via an activation hook.
#
# Mirrors scripts/setup_nauty.sh — same install pattern (sources into
# $CONDA_PREFIX/src/, build artefact stays in-tree, PATH wired through
# $CONDA_PREFIX/etc/conda/activate.d/).
set -e

if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: no active conda/micromamba environment detected."
    echo "  micromamba activate k4free"
    exit 1
fi

KISSAT_VERSION="rel-4.0.4"
SRC_DIR="$CONDA_PREFIX/src"
KISSAT_DIR="$SRC_DIR/kissat"

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

# ── Fetch source ──────────────────────────────────────────────────────────────

if [ ! -d "$KISSAT_DIR" ]; then
    echo "Cloning kissat ($KISSAT_VERSION)..."
    git clone --depth=1 --branch "$KISSAT_VERSION" \
        https://github.com/arminbiere/kissat.git "$KISSAT_DIR" \
        || git clone --depth=1 https://github.com/arminbiere/kissat.git "$KISSAT_DIR"
fi

cd "$KISSAT_DIR"

# ── Build ─────────────────────────────────────────────────────────────────────

if [ ! -f "build/kissat" ]; then
    ./configure
    make -j"$(nproc 2>/dev/null || echo 4)"
fi

echo "kissat built at $KISSAT_DIR/build/kissat"
"$KISSAT_DIR/build/kissat" --version

# ── Register on PATH via activation hook ──────────────────────────────────────

ACTIVATE_DIR="$CONDA_PREFIX/etc/conda/activate.d"
mkdir -p "$ACTIVATE_DIR"
cat > "$ACTIVATE_DIR/kissat_path.sh" <<EOL
#!/usr/bin/env bash
export PATH="$KISSAT_DIR/build:\$PATH"
EOL
chmod +x "$ACTIVATE_DIR/kissat_path.sh"
export PATH="$KISSAT_DIR/build:$PATH"

echo ""
echo "Done. kissat binary on PATH via env activation hook"
echo "  ($ACTIVATE_DIR/kissat_path.sh)."
echo "Re-activate the env (or 'source' the hook) for the change to take effect"
echo "in this shell."
