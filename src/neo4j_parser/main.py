import argparse
import logging
import os

from neo4j_parser import export
from neo4j_parser.parser import RDFNeo4jParser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="LPWC RDF to Neo4j parser")
    arg_parser.add_argument(
        "--raw-data-dir",
        type=str,
        default="~/neo4j-lpwc/raw-data",
        help="Directory containing LPWC RDF files",
    )
    arg_parser.add_argument(
        "--import-dir",
        type=str,
        default="~/neo4j-lpwc/import",
        help="Directory nodes and relationships CSV files for Neo4J import",
    )
    arg_parser.add_argument(
        "--ttl-filename",
        type=str,
        default="linkedpaperswithcode_2024-09-05.ttl",
        help="Name of the TTL file containing subject-predicate-object triplets",
    )
    arg_parser.add_argument(
        "--owl-filename",
        type=str,
        default="linkedpaperswithcode-ontology.owl",
        help="Name of the OWL file containing RDF ontology",
    )
    arg_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Force overwrite existing files",
    )
    args = arg_parser.parse_args()

    import_dir = os.path.expanduser(args.import_dir)
    nodes_filepath = os.path.join(import_dir, "nodes.csv")
    relationships_filepath = os.path.join(import_dir, "relationships.csv")

    if (
        not args.overwrite
        and os.path.exists(nodes_filepath)
        and os.path.exists(relationships_filepath)
    ):
        logger.info(
            f"Nodes and relationships CSV files already exist in {import_dir}, "
            "skipping generation."
        )
        exit(0)

    import_dir = os.path.expanduser(args.import_dir)
    nodes_filepath = os.path.join(import_dir, "nodes.csv")
    relationships_filepath = os.path.join(import_dir, "relationships.csv")

    raw_data_dir = os.path.expanduser(args.raw_data_dir)
    ttl_filepath = os.path.join(raw_data_dir, args.ttl_filename)
    owl_filepath = os.path.join(raw_data_dir, args.owl_filename)

    parser = RDFNeo4jParser(
        ttl_filepath, owl_filepath, enrich_authors=True, enrich_papers=True
    )
    nodes, relationships = parser.parse()

    export.write_nodes(nodes, nodes_filepath)
    export.write_relationships(relationships, relationships_filepath)

    logger.info("Finished parsing and writing data!")
