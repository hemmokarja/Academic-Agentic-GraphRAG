import csv
import logging

logger = logging.getLogger(__name__)


def _collect_all_properties(nodes):
    properties = set()
    for node in nodes.values():
        node_properties = set(node["properties"].keys())
        if len(node_properties) > 0:
            properties.update(node_properties)
    return sorted(list(properties))


def write_nodes(nodes, filepath="nodes.csv"):
    properties = _collect_all_properties(nodes)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        headers = ["nodeId:ID", ":LABEL"] + properties
        writer.writerow(headers)

        for node_id, node in nodes.items():
            propery_values = [node["properties"].get(p) for p in properties]
            row = [str(node_id), node["label"]] + propery_values
            writer.writerow(row)

    logger.info(f"Written {len(nodes)} records to {filepath}")


def write_relationships(relationships, filepath="relationships.csv"):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([":START_ID", ":TYPE", ":END_ID"])

        for source, rel_type, target in relationships:
            writer.writerow([str(source), rel_type, str(target)])

    logger.info(f"Written {len(relationships)} records to {filepath}")
