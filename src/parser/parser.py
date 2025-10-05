import logging

from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL
from SPARQLWrapper import SPARQLWrapper, JSON, POST

logger = logging.getLogger(__name__)

AUTHOR_URI = "http://purl.org/dc/terms/creator"
SEMOPENALEX_SPARQL_ENDPOINT = "https://semopenalex.org/sparql"


def _to_pascal_case(s):
    # converts strings "Like This" into "LikeThis", used for node labels
    words = s.split()
    if len(words) == 1:
        return s
    return "".join(word.capitalize() for word in words)


def _to_upper_snake_case(s):
    # converts strings "like this" into "LIKE_THIS", used for relationships
    return "_".join(word.upper() for word in s.split())


def _to_camel_case(s):
    # converts strings "like this" into "likeThis", used for properties
    words = s.split()
    if len(words) == 1:
        return s
    return words[0].lower() + ''.join(w.capitalize() for w in words[1:])


def _to_bathces(lst, batch_size):
    batches = []
    for i in range(0, len(lst), batch_size):
        batches.append(lst[i: i + batch_size])
    return batches


def _to_sparql_string(author_uris):
    strings = [f"<{u}>" for u in author_uris]
    return "\n".join(strings)


def _query_names(sparql, author_uris):
    author_uris_string = _to_sparql_string(author_uris)
    query = f"""
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    SELECT ?author ?name
    WHERE {{
        VALUES ?author {{
        {author_uris_string}
        }}
        ?author foaf:name ?name .
    }}
    """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    result_dict = {}
    for result in results["results"]["bindings"]:
        author_uri = result["author"]["value"]
        name = result["name"]["value"]
        result_dict[author_uri] = name

    return result_dict


def _fetch_author_names(author_nodes, batch_size):
    author_uris = [n["properties"]["uri"] for n in author_nodes]
    author_uri_batches = _to_bathces(author_uris, batch_size)

    sparql = SPARQLWrapper(SEMOPENALEX_SPARQL_ENDPOINT)
    sparql.setMethod(POST)

    uri_to_name = {}
    for uri_batch in author_uri_batches:
        batch_uri_to_name = _query_names(sparql, uri_batch)
        uri_to_name.update(batch_uri_to_name)

    return uri_to_name


class RDFNeo4jParser:
    def __init__(
        self, ttl_filepath: str, owl_filepath: str, enrich_authors: bool = True
    ):
        self.ttl_filepath = ttl_filepath
        self.owl_filepath = owl_filepath
        self.enrich_authors = enrich_authors  # fetch names from SemOpenAlex SPARQL endpoint

        self.g = Graph()

        # mappings from URI -> human-readable labels
        self.class_labels = {}  # class URI -> Label
        self.property_labels = {}  # predicate URI -> Label

        # nodes and relationships
        self.nodes = {}  # URI -> dict of properties + label
        self.relationships = []  # list of tuples: (subject_URI, predicate_label, object_URI)

        # entities that are proper nodes
        self.node_uris = set()  # URIs that should become Neo4j nodes

        # for property labels that are not caught in `extract_ontology_labels`
        self.augmented_property_map = {
            "hasArXivId": "hasArXivId",
            "owl#sameAs": "sameAs",
            "rdf-schema#domain": "domain",
            "rdf-schema#comment": "comment",
            "rdf-schema#label": "label",
            "rdf-schema#range": "range",
            "source": "source"
        }

        # ignore ontology artifacts, not actual node labels
        self.ignore_labels = {
            "owl#Class", "owl#ObjectProperty", "owl#DatatypeProperty", "owl#Ontology"
        }

    def _parse_files(self):
        """Parse TTL and OWL files into a single RDF graph."""
        self.g.parse(self.ttl_filepath, format="ttl")
        self.g.parse(self.owl_filepath, format="xml")
        logger.info("RDF graph parsed")

    def _extract_ontology_labels(self):
        """
        Extract human-readable labels for classes and predicates from the OWL ontology.
        For predicates without rdfs:label, fallback to last URI segment.
        """
        # Classes
        for s, p, o in self.g.triples((None, RDF.type, OWL.Class)):
            label = None
            
            # first check if we find a label
            for _, _, lbl in self.g.triples((s, RDFS.label, None)):
                if isinstance(lbl, Literal):
                    label = str(lbl)
                    break

            # otherwise fallback to last part of URI
            if label is None:
                label = str(s).split("/")[-1]  # fallback

            self.class_labels[s] = label

        # ObjectProperties and DatatypeProperties
        for s, p, o in self.g.triples((None, RDF.type, None)):
            if o in [OWL.ObjectProperty, OWL.DatatypeProperty]:
                label = None

                # first check if we find a label
                for _, _, lbl in self.g.triples((s, RDFS.label, None)):
                    if isinstance(lbl, Literal):
                        label = str(lbl)
                        break

                # otherwise fallback to last part of URI
                if label is None:    
                    label = str(s).split("/")[-1]

                self.property_labels[s] = label

                # OWL file stores the labels with https uri, but TTL file has some
                # uris with http, we want to store both mappings
                uri_str = str(s)
                if uri_str.startswith("https://"):
                    uri_str_http = "http://" + uri_str[8:]
                    self.property_labels[URIRef(uri_str_http)] = label

        logger.info("Ontology labels extracted")

    def _identify_nodes(self):
        """Find all RDF subjects that should become Neo4j nodes."""

        # any subject that has rdf:type -> becomes a node (generally, entities that
        # should become nodes are represented in triplets with a type predicate)
        for s, p, o in self.g.triples((None, RDF.type, None)):
            if isinstance(s, URIRef):
                self.node_uris.add(s)

        # optionally, subjects that are objects of other node-like predicates
        # RDF triples don’t require that every resource appears as a subject somewhere,
        # some resources may only appear as the object of another triple, e.g.,:
        # <https://paper1> <hasRepository> <https://repo1>
        # if <https://repo1> appears only as an object in the TTL data, 
        # and we only looked at subjects, repo1 would never become a node in Neo4j
        for s, p, o in self.g.triples((None, None, None)):
            if isinstance(o, URIRef) and o not in self.node_uris:
                # Could be a node or literal – keep for now if it has rdf:type
                if (o, RDF.type, None) in self.g:
                    self.node_uris.add(o)

        # authors are represented in RDF triplets as SemOpenAlex reference URIs always
        # as objects, their predicate is custom `dcterms:creator` so they're not
        # captured in the earlier blocks, and therefore require custom handling
        for s, p, o in self.g.triples((None, URIRef(AUTHOR_URI), None)):
            if isinstance(o, URIRef):
                self.node_uris.add(o)

        logger.info("Nodes identified")

    def _build_nodes_and_relationships(self):
        """Classify all triples as node properties or relationships."""
        for s, p, o in self.g.triples((None, None, None)):
            
            # skip anything that isn't a proper node
            if s not in self.node_uris:
                continue

            # ensure node entry exists
            if s not in self.nodes:
                self.nodes[s] = {"label": None, "properties": {}}

            # node labels
            if p == RDF.type:
                if o in self.class_labels:
                    label = self.class_labels[o]
                    label = _to_pascal_case(label)
                    self.nodes[s]["label"] = label
                else:
                    o_ = str(o).split("/")[-1]
                    if o_ not in self.ignore_labels:
                        label = _to_pascal_case(o_)
                        self.nodes[s]["label"] = label
                    # else: ignore OWL/ontology artifacts

            # custom handling for author triplets
            elif p == URIRef(AUTHOR_URI) and isinstance(o, URIRef):
                if o not in self.nodes:
                    self.nodes[o] = {"label": "Author", "properties": {"uri": str(o)}}
                self.relationships.append((s, "HAS_AUTHOR", o))

            # other predicates
            else:
                if p in self.property_labels:
                    pred_label = self.property_labels[p]
                else:
                    p_ = str(p).split("/")[-1]
                    if p_ in self.augmented_property_map:
                        pred_label = self.augmented_property_map[p_]
                    else:
                        logger.warning(f"Unknown predicate {p}")
                        pred_label = p_

                # property
                # if we encounter a property key repeteadly, we make a list of
                # the values
                if isinstance(o, Literal):
                    property_key = _to_camel_case(pred_label)
                    value = str(o).replace("\n", " ").strip()

                    if property_key in self.nodes[s]["properties"]:
                        current = self.nodes[s]["properties"][property_key]
                        if isinstance(current, list):
                            current.append(value)
                        else:
                            self.nodes[s]["properties"][property_key] = [current, value]
                    else:
                        self.nodes[s]["properties"][property_key] = value

                # object is another node, so create a relationship
                # (remaining unknown objects are stored as properties for good measure)
                elif isinstance(o, URIRef):
                    # only make relationship if the object is a node
                    if o in self.node_uris:
                        rel_label = _to_upper_snake_case(pred_label)
                        self.relationships.append((s, rel_label, o))
                    else:
                        # optional: treat unknown URIRefs as literal-like property
                        property_key = _to_camel_case(pred_label)
                        self.nodes[s]["properties"][property_key] = str(o)

        logger.info("Nodes and relationships built")

    def _enrich_author_nodes(self, batch_size=30_000):
        author_nodes = [n for n in self.nodes.values() if n["label"] == "Author"]
        uri_to_name = _fetch_author_names(author_nodes, batch_size)
        for node in author_nodes:
            uri = node["properties"]["uri"]
            if uri in uri_to_name:
                node["properties"]["name"] = uri_to_name[uri]
        
        logger.info("Enriched author nodes with names")

    def parse(self):
        logger.info("Starting to process RDF files into nodes and relationships...")
        self._parse_files()
        self._extract_ontology_labels()
        self._identify_nodes()
        self._build_nodes_and_relationships()

        if self.enrich_authors:
            self._enrich_author_nodes()

        logger.info(
            f"Finished processing! Collected {len(self.nodes)} nodes and "
            f"{len(self.relationships)} relationships."
        )
        return self.nodes, self.relationships
