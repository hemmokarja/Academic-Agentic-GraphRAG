NEO4J_PASSWORD=your_password
NEO4J_DB=lpwc

CONTAINER_NAME=neo4j
NEO4J_IMAGE=neo4j:5.15

HTTP_PORT=7474
BOLT_PORT=7687

NEO4J_DIR=$(HOME)/neo4j-lpwc
RAW_DATA_DIR=$(NEO4J_DIR)/raw-data
DATA_DIR=$(NEO4J_DIR)/data
IMPORT_DIR=$(NEO4J_DIR)/import

MIRROR_BASE_URL=https://zenodo.org/records/13881433/files
TTL_FILENAME=linkedpaperswithcode_2024-09-05.ttl
OWL_FILENAME=linkedpaperswithcode-ontology.owl

export RAW_DATA_DIR DATA_DIR IMPORT_DIR MIRROR_BASE_URL TTL_FILENAME OWL_FILENAME
export CONTAINER_NAME NEO4J_PASSWORD NEO4J_DB 

.PHONY: setup setup-files parse-files pull import-neo4j run-neo4j create-indexes stop clean

setup: setup-files parse-files pull import-neo4j run-neo4j create-indexes

setup-files:
	@./scripts/setup-files.sh

parse-files:
	@uv run python src/parser/main.py \
		--raw-data-dir $(RAW_DATA_DIR) \
		--import-dir $(IMPORT_DIR) \
		--ttl-filename $(TTL_FILENAME) \
		--owl-filename $(OWL_FILENAME)

pull:
	@docker pull $(NEO4J_IMAGE)

import-neo4j:
	@echo "Stopping Neo4j container if running..."
	@docker stop $(CONTAINER_NAME) 2>/dev/null || true
	@echo "Running neo4j-admin import..."
	@docker run --rm \
		-v $(DATA_DIR):/data \
		-v $(IMPORT_DIR):/var/lib/neo4j/import \
		$(NEO4J_IMAGE) \
		neo4j-admin database import full \
		--nodes=/var/lib/neo4j/import/nodes.csv \
		--relationships=/var/lib/neo4j/import/relationships.csv \
		--overwrite-destination \
		$(NEO4J_DB)
	@echo "Import complete!"

run-neo4j:
	@docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(HTTP_PORT):7474 -p $(BOLT_PORT):7687 \
		-e NEO4J_AUTH=neo4j/$(NEO4J_PASSWORD) \
		-e NEO4J_PLUGINS='["apoc"]' \
		-e NEO4J_dbms_default__database=$(NEO4J_DB) \
		-e NEO4J_dbms_memory_heap_max__size=6G \
		-e NEO4J_dbms_memory_transaction_global__max__size=6G \
		-v $(DATA_DIR):/data \
		-v $(IMPORT_DIR):/var/lib/neo4j/import \
		$(NEO4J_IMAGE)
	@echo "Neo4J container running!"

create-indexes:
	@./scripts/create-indexes.sh

stop:
	@docker rm -f $(CONTAINER_NAME) 2>/dev/null || true
	@echo "Neo4J container stopped and removed"

clean: stop
	@rm -rf $(NEO4J_DIR)
