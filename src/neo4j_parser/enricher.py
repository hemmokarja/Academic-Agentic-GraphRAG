import ssl
import urllib
import logging

from SPARQLWrapper import JSON, POST, SPARQLWrapper
from tqdm import tqdm

logger = logging.getLogger(__name__)


def _to_bathces(lst, batch_size):
    batches = []
    for i in range(0, len(lst), batch_size):
        batches.append(lst[i: i + batch_size])
    return batches


def _to_sparql_string(author_uris):
    strings = [f"<{u}>" for u in author_uris]
    return "\n".join(strings)


class SemOpenAlexEnricher:
    """
    A utility for enriching author and paper data using the SemOpenAlex SPARQL endpoint.

    Fetches metadata such as author names, publication years, and citation links in
    batches.

    Note:
        Falls back to an unverified SSL context if the SemOpenAlex SSL certificate has
        expired or cannot be verified. This is a temporary workaround implemented due
        to certificate issues observed during development.
    """
    def __init__(self):
        self.sparql = SPARQLWrapper("https://semopenalex.org/sparql")
        self.sparql.setMethod(POST)
        self.sparql.setReturnFormat(JSON)
        self._ssl_warning_logged = False

    def _query_with_unverified_fallback(self):
        try:
            results = self.sparql.query().convert()
        except Exception as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                if not self._ssl_warning_logged:
                    logger.warning(
                        "SSL verification failed for SemOpenAlex — retrying with "
                        "unverified SSL context."
                    )
                    self._ssl_warning_logged = True

                unverified = ssl._create_unverified_context()
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=unverified)
                )
                urllib.request.install_opener(opener)
                results = self.sparql.query().convert()
            else:
                raise
        return results

    def _query_author_metadata(self, author_uris):
        """Query full name for a batch of authors."""
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

        self.sparql.setQuery(query)
        results = self._query_with_unverified_fallback()

        result_dict = {}
        for result in results["results"]["bindings"]:
            author_uri = result["author"]["value"]
            name = result["name"]["value"]
            result_dict[author_uri] = {"name": name}

        return result_dict
    
    def _query_paper_metadata(self, paper_uris):
        """Query publication year and citing papers for a batch of source papers."""
        paper_uris_string = _to_sparql_string(paper_uris)
        query = f"""
        PREFIX schema: <http://schema.org/>
        PREFIX openalex: <https://semopenalex.org/ontology/>
        PREFIX cito: <http://purl.org/spar/cito/>
        PREFIX fabio: <http://purl.org/spar/fabio/>

        SELECT ?paper ?year ?citedBy
        WHERE {{
            VALUES ?paper {{
            {paper_uris_string}
            }}
            OPTIONAL {{ ?paper schema:datePublished ?year . }}
            OPTIONAL {{ ?paper fabio:hasPublicationYear ?year . }}
            OPTIONAL {{ ?citedBy cito:cites ?paper . }}
        }}
        """

        self.sparql.setQuery(query)
        results = self._query_with_unverified_fallback()

        result_dict = {}
        for r in results["results"]["bindings"]:
            paper_uri = r["paper"]["value"]
            if paper_uri not in result_dict:
                result_dict[paper_uri] = {"year": None, "citedBy": []}
            if "year" in r:
                result_dict[paper_uri]["year"] = r["year"]["value"]
            if "citedBy" in r:
                result_dict[paper_uri]["citedBy"].append(r["citedBy"]["value"])

        return result_dict

    def _get_uri_to_meta(self, query_fn, uris, batch_size):
        uri_to_meta = {}
        for uri_batch in tqdm(_to_bathces(uris, batch_size)):
            batch_uri_to_meta = query_fn(uri_batch)
            uri_to_meta.update(batch_uri_to_meta)
        return uri_to_meta

    def fetch_author_metadata(self, author_uris, batch_size=30_000):
        return self._get_uri_to_meta(
            self._query_author_metadata, author_uris, batch_size
        )

    def fetch_paper_metadata(self, paper_uris, batch_size=10_000):
        return self._get_uri_to_meta(
            self._query_paper_metadata, paper_uris, batch_size
        )
