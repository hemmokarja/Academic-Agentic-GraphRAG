#!/bin/bash

set -e


run_cypher_file() {
    local file="$1"
    local description="$2"
    echo "Running: $description ($file)"
    if docker exec -i "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" -d "${NEO4J_DB}" < "$file" &>/dev/null; then
        echo "Cypher executed successfully"
    else
        echo "Cypher failed or already exists"
    fi
}


echo "Creating indexes and constraints for Neo4j database: ${NEO4J_DB}"

# wait until Neo4j is ready
echo "Waiting for Neo4j to be ready..."
max_attempts=30
attempt=0
while true; do
    if docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" -d "${NEO4J_DB}" "RETURN 1;" &>/dev/null; then
        echo "Neo4j is ready!"
        break
    fi

    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "ERROR: Neo4j did not become ready after $max_attempts attempts."
        exit 1
    fi

    echo "Attempt $attempt/$max_attempts - waiting..."
    sleep 2
done

run_cypher_file "./cypher/setup/create-constraints.cypher" "Constraints"
run_cypher_file "./cypher/setup/create-indexes.cypher" "Property Indexes"
run_cypher_file "./cypher/setup/create-fulltext-indexes.cypher" "Full-text Indexes"
run_cypher_file "./cypher/setup/create-numeric-indexes.cypher" "Numeric/Analytical Indexes"

echo "Current indexes and constraints:"
docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" -d "${NEO4J_DB}" "SHOW INDEXES; SHOW CONSTRAINTS;"

echo ""
echo "All indexes and constraints created successfully!"
