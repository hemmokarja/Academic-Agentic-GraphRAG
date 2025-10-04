#!/bin/bash
set -euo pipefail

RAW_DATA_DIR=${RAW_DATA_DIR:-"$HOME/neo4j-lpwc/raw-data"}
DATA_DIR=${DATA_DIR:-"$HOME/neo4j-lpwc/data"}
IMPORT_DIR=${IMPORT_DIR:-"$HOME/neo4j-lpwc/import"}
MIRROR_BASE_URL=${MIRROR_BASE_URL:-"https://zenodo.org/records/13881433/files"}
TTL_FILENAME=${TTL_FILENAME:-"linkedpaperswithcode_2024-09-05.ttl"}
OWL_FILENAME=${OWL_FILENAME:-"linkedpaperswithcode-ontology.owl"}

mkdir -p "$RAW_DATA_DIR" "$DATA_DIR" "$IMPORT_DIR"
chmod 777 "$DATA_DIR" "$IMPORT_DIR"

cd "$RAW_DATA_DIR"

FILES=(
    "$TTL_FILENAME"
    "$OWL_FILENAME"
)
for FILE in "${FILES[@]}"; do
    if [ -f "$FILE" ]; then
        echo "$FILE already exists, skipping download."
    else
        URL="$MIRROR_BASE_URL/$FILE?download=1"
        echo "Downloading $FILE from $URL..."
        curl -LO "$URL"
    fi
done

echo "All files available in $RAW_DATA_DIR"
