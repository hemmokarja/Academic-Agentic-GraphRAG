# Agentic GraphRAG Engine for ML/AI Research

An autonomous research assistant that reasons over 1.6M scientific entities through multi-step planning and graph traversal. Built on Linked Papers With Code and enriched with SemOpenAlex metadata, this system uses agentic workflows to explore ML research through the relationships between papers, authors, citations, datasets, and methods.

⚠️ **Note: Project currently under active development**

## 🎯 Overview

This is a learning project demonstrating AI engineering skills through the implementation of an intelligent agent capable of multi-step reasoning over a large-scale knowledge graph of ML/AI research. Unlike traditional RAG systems that operate on flat document collections, this system leverages the inherent graph structure of academic publications - papers, authors, citations, datasets, and methods - to answer complex queries that require graph traversal and relational reasoning.

## 💡 What Can You Ask?

**Simple (single-tool queries)**:
- "Who are the authors of the BERT paper?"
- "What papers cite Attention Is All You Need?"

**Complex (multi-step agentic reasoning)**:
- "What other papers have the authors of BERT published?"
- "Trace the lineage from ResNet to modern vision transformers?"
- "Who are the most prolific collaborators in self-supervised learning?"

The agent autonomously breaks these down into graph traversal strategies.

## 🕸️ What is GraphRAG?

GraphRAG (Graph Retrieval-Augmented Generation) extends traditional RAG by representing knowledge as a graph rather than isolated documents. While conventional RAG retrieves relevant text chunks based on similarity search, GraphRAG leverages explicit relationships between entities to:

- **Traverse multi-hop connections**: Follow citation chains, co-authorship networks, and method relationships
- **Discover hidden patterns**: Identify research lineages, influential papers, and emerging trends
- **Answer relational queries**: Questions like "Who are the key collaborators in transformer research?" or "What other papers have the authors of BERT published?"
- **Provide contextual understanding**: Retrieve not just similar content, but semantically connected information through graph structure

GraphRAG shines when:
- Queries require understanding relationships between entities
- Information is connected through multi-hop paths in the graph
- The knowledge domain has inherent graph structure (research networks, citation graphs, knowledge bases)
- Context from connected nodes enhances answer quality

## 🤖 Why Agentic?

While vanilla GraphRAG systems allow LLMs to select and execute graph queries, they typically operate in a **single-shot** manner: plan once, execute once, answer. This system goes further with **autonomous multi-step reasoning**:

- **Decomposes complex questions** that require chaining multiple graph operations
- **Iterative exploration**: Observes results and decides if more information is needed
- **Adapts strategy** based on intermediate findings (e.g., "These authors aren't relevant, let me try a different path")
- **Self-reflects** on answer completeness before responding
- **Executes parallel tool calls** for efficiency when appropriate

**Example**: Ask "Trace the lineage from ResNet to modern vision transformers" 

*Single-shot GraphRAG* might execute one broad citation query and summarize results.

*Agentic GraphRAG autonomously*:
1. Searches for the ResNet paper
2. Traverses forward citations to find descendant architectures
3. Identifies when attention mechanisms entered vision (e.g., SAGAN, Non-local Neural Networks)
4. Follows the citation chain to Vision Transformer (ViT)
5. Maps the key architectural innovations at each step
6. Synthesizes a narrative of the evolution

## 🏗️ Architecture

- **Neo4j**: Graph database running in a Docker container
- **LangGraph**: Orchestrates communication between the agent and language models
- **Custom ReAct Agent**: Built from scratch with:
  - Multi-step reasoning loops with thought/action/observation cycles
  - Iterative refinement based on partial results
  - Dynamic query planning that adapts to graph structure
- **Graph Tools**: Purpose-built search and traversal functions with Pydantic validation
- **Streamlit UI**: Interactive chat interface for querying the knowledge graph
- **Custom RDF Parser**: Processes Linked Papers With Code RDF dumps into Neo4j-compatible graph structure
- **SemOpenAlex Enricher**: Augments the graph with additional author, paper, and citation metadata via SPARQL queries

### Data Sources

**Linked Papers With Code (LPWC)**

[LPWC](https://github.com/metaphacts/linkedpaperswithcode) is an RDF knowledge graph that comprehensively models the machine learning research field, containing information about almost 500,000 ML publications including tasks addressed, datasets utilized, methods implemented, and evaluations performed. This rich structured representation provides the foundation for graph-based reasoning over ML research.

**SemOpenAlex**

[SemOpenAlex](https://semopenalex.org/resource/semopenalex:UniversalSearch) is an extensive RDF knowledge graph containing over 26 billion triples about scientific publications and their associated entities, including authors, institutions, journals, and concepts. This project uses SemOpenAlex's SPARQL endpoint to enrich papers with additional metadata and citation relationships.

### Graph Statistics

- **~500K** ML and AI papers
- **~400K** authors
- **~1.6M** total nodes (Papers, Authors, Datasets, Models, Methods, Evaluations, etc.)
- **~6.8M** relationships (citations, authorships, evaluations, implementations, etc.)

## 🛠️ Agent Tools

The agent has access to specialized tools for exploring the knowledge graph:

- `search_nodes` - Full-text search across all nodes with relevance scoring
- `author_papers` - Find all papers authored by a specific author
- `paper_authors` - Find all authors of a specific paper
- `paper_citations_out` - Find papers cited by (referenced in) a given paper
- `paper_citations_in` - Find papers that cite a given paper
- `author_coauthors` - Find an author's collaborators through co-authorship
- `paper_citation_chain` - Traverse citation chains to explore research lineage or impact

**Note**: Current tools focus on Papers and Authors. Additional tools for exploring Datasets, Models, Methods, and other node types are under active development.

## ⚙️ Prerequisites

- Docker
- `uv` package manager
- Make (for Makefile)
- Neo4j Desktop (recommended but not required)
- OpenAI API key

**System Requirements**: Parsing LPWC RDF files is resource-intensive. A machine with **>25GB RAM** is recommended.

## 🚀 Get Started

### Installation

This project uses `uv` for dependency management. Install dependencies with:

```bash
uv sync
```

### Initial Setup

```bash
make setup
```

This command performs the complete pipeline:
1. Downloads Linked Papers With Code RDF files
2. Parses RDF data into graph structure
3. Enriches the graph with SemOpenAlex metadata
4. Exports nodes and relationships to Neo4j-compatible CSV files
5. Executes Neo4j admin import to load the graph
6. Creates necessary database constraints and indexes
7. Starts the Neo4j Docker container

**Note**: Please, verify that the paths and settings in the `Makefile` are correct for your setup.

### Start Chatting

```bash
export OPENAI_API_KEY=your_api_key_here
make chat
```

This launches the Streamlit UI where you can interact with the agent and query the knowledge graph.

### Stop the System

```bash
make stop
```

Stops and removes the Neo4j Docker container. Database data is preserved on the disk of your local machine.

### Clean Everything

```bash
make clean
```

Stops the container and removes all downloaded files, parsed data, and configurations created during `make setup`.

## 🔗 Connecting to Neo4J Desktop

Use this procedure to establish a **Remote Connection** in Neo4j Desktop to manually inspect your running database.

1.  Open **Neo4j Desktop** and go to **Remote Connections**
2.  Click **New Connection**
3.  Enter the following values

| Field | Value |
| :--- | :--- |
| **Bolt URI** | `bolt://localhost:7687` |
| **Username** | `neo4j` |
| **Password** | *`your_password`* |
| **Connection Name** | `lpwc-docker` |

**Note:** This is not required for running the app, but can be used to explore the underlying knowledge graph via a graphical user interface.

## ⚠️ Known Limitations

- **Data Completeness**: Neither LPWC nor SemOpenAlex are perfect. Some authors, papers, or citation relationships may be missing or incomplete.
- **Data Freshness**: LPWC is updated infrequently. The latest RDF dump (as of this project) is from **2024-09-06**. Research published after this date will not be present in the knowledge graph.
- **LLM Provider**: Currently supports OpenAI models only. Anthropic support may be added in the future.

## 🎓 Learning Outcomes

This project demonstrates:
- Implementing ReAct-style agentic loops with tool selection and reasoning
- Implementing GraphRAG architectures
- Working with Neo4j, Docker, and modern Python tooling
- Building production-quality data pipelines with validation and error handling
- Integrating graph databases into AI applications
- Parsing and transforming large-scale RDF datasets

## 📝 License

This project is licensed under the MIT License.
