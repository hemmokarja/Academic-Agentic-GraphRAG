import os
from typing import Optional
from neo4j import GraphDatabase, Driver
import logging

logger = logging.getLogger(__name__)

_neo4j_driver: Optional[Driver] = None


def get_neo4j_driver() -> Driver:
    global _neo4j_driver

    if _neo4j_driver is not None:
        return _neo4j_driver

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri:
        raise ValueError("NEO4J_URI environment variable is required")

    if not password:
        raise ValueError("NEO4J_PASSWORD environment variable is required")
    
    try:
        _neo4j_driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
            max_connection_lifetime=3600,  # 1 hour
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
            encrypted=False
        )
        _neo4j_driver.verify_connectivity()

        logger.info(f"Successfully connected to Neo4j at {uri}")
        return _neo4j_driver
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise


def close_neo4j_driver():
    global _neo4j_driver

    if _neo4j_driver is not None:
        _neo4j_driver.close()
        _neo4j_driver = None
        logger.info("Neo4j driver closed")
