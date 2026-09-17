"""
MiroFish-Offline Storage Layer

Local graph storage replacing Zep Cloud:
- Neo4j CE for graph persistence
- Local embeddings (nomic-embed-text) via Ollama or llama.cpp
- LLM-based NER/RE extraction
- Hybrid search (vector + keyword)
"""

from .graph_storage import GraphStorage
from .neo4j_storage import Neo4jStorage
from .embedding_service import EmbeddingService, EmbeddingError
from .ner_extractor import NERExtractor
from .search_service import SearchService

__all__ = [
    "GraphStorage",
    "Neo4jStorage",
    "EmbeddingService",
    "EmbeddingError",
    "NERExtractor",
    "SearchService",
]
