"""
prismrag-patch — free OSS RAG library with full API core parity.

Quick start::

    from prismrag_patch import PrismRAG

    rag = PrismRAG(mapping={"categories": [...], "rules": [...]})
    rag.ingest(records=[{"word": "diabetes", "text": "diabetes management"}])
    print(rag.search("insulin medication", top_k=5))
"""
from prismrag_patch.client import PrismRAG
from prismrag_patch.core import PrismRAGPatch
from prismrag_patch.license import LicenseError, validate_license
from prismrag_patch.models import MappingConfig
from prismrag_patch.store import MemoryStore, PostgresStore

__all__ = [
    "PrismRAG",
    "PrismRAGPatch",
    "MemoryStore",
    "PostgresStore",
    "MappingConfig",
    "LicenseError",
    "validate_license",
]
__version__ = "0.2.1"
