#!/usr/bin/env bash
set -e

# Directory inside Micromamba environment
SRC_DIR="$CONDA_PREFIX/src"
NAUTY_VERSION="2_9_3"
NAUTY_TAR="nauty${NAUTY_VERSION}.tar.gz"
NAUTY_DIR="$SRC_DIR/nauty${NAUTY_VERSION}"

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

# Download Nauty source if missing
if [ ! -f "$NAUTY_TAR" ]; then
    wget "https://pallini.di.uniroma1.it/$NAUTY_TAR"
fi

# Extract if missing
if [ ! -d "$NAUTY_DIR" ]; then
    tar xzf "$NAUTY_TAR"
fi

cd "$NAUTY_DIR"

# Run configure before make
if [ ! -f "config.status" ]; then
    ./configure
fi

# Build Nauty
make

# Create activation script for Micromamba
ACTIVATE_DIR="$CONDA_PREFIX/etc/conda/activate.d"
mkdir -p "$ACTIVATE_DIR"
cat > "$ACTIVATE_DIR/nauty_path.sh" <<EOL
#!/usr/bin/env bash
export PATH="$NAUTY_DIR:\$PATH"
EOL
chmod +x "$ACTIVATE_DIR/nauty_path.sh"

echo "Nauty is now built and automatically added to PATH on environment activation!"