import csv
import logging

logger = logging.getLogger(__name__)


def _collect_all_properties(nodes):
    """Collect all unique property names across all nodes."""
    properties = set()
    for node in nodes.values():
        node_properties = set(node["properties"].keys())
        if node_properties:
            properties.update(node_properties)
    return sorted(list(properties))


def _infer_neo4j_type(values):
    """Infer Neo4j type suffix (:int, :float, :boolean, :string, :string[])."""
    values = [v for v in values if v is not None]
    if not values:
        return "string"  # fallback default
    
    # if all values are lists
    if all(isinstance(v, (list, tuple)) for v in values):
        # infer element type from first non-empty list
        elems = [e for v in values for e in v if e is not None]
        if not elems:
            return "string[]"
        elem_type = _infer_neo4j_type(elems)
        # _infer_neo4j_type returns without [], so we add it
        return f"{elem_type}[]"
    
    # if all values are bools
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    
    # if all values are ints
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "int"
    
    # if all values are floats or mix of int/float
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "float"
    
    # default fallback
    return "string"


def _infer_property_types(nodes):
    """Infer Neo4j-compatible property type suffixes based on data."""
    property_to_dtype = {}
    for prop in _collect_all_properties(nodes):
        values = [n["properties"].get(prop) for n in nodes.values()]
        property_to_dtype[prop] = _infer_neo4j_type(values)
    return property_to_dtype


def write_nodes(nodes, filepath="nodes.csv", array_delimiter="|"):
    properties = _collect_all_properties(nodes)
    property_to_dtype = _infer_property_types(nodes)
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # create headers with Neo4j type annotations
        prop_headers = [f"{prop}:{property_to_dtype[prop]}" for prop in properties]
        headers = ["nodeId:ID", ":LABEL"] + prop_headers
        writer.writerow(headers)

        for node_id, node in nodes.items():
            row = [str(node_id), node["label"]]
            
            for p in properties:
                value = node["properties"].get(p)

                if isinstance(value, (list, tuple)):
                    # join list into pipe-separated string (Neo4j default)
                    row.append(array_delimiter.join(map(str, value)))
                else:
                    row.append(value)

            writer.writerow(row)

    logger.info(f"Written {len(nodes)} node records to {filepath}")


def write_relationships(relationships, filepath="relationships.csv"):
    """Write relationships in Neo4j import format."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([":START_ID", ":TYPE", ":END_ID"])
        for source, rel_type, target in relationships:
            writer.writerow([str(source), rel_type, str(target)])

    logger.info(f"Written {len(relationships)} relationships to {filepath}")
