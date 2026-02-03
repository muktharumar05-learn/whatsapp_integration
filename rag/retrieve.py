from langchain_experimental.text_splitter import SemanticChunker
import logging
from .utils import Utils
import chromadb
from sentence_transformers import CrossEncoder


class RagRetriever:
    def __init__(self, config_path: str = "config.yaml"):
        self.utils = Utils(config_path)
        self.config = self.utils.config
        self.embeddings = self.utils.initialize_embeddings()

        if self.embeddings is None:
            raise ValueError("Embeddings must not be None for retrieval")

        self.chroma_client = chromadb.PersistentClient(
            path=self.config["vectorstore"]["persist_directory"]
        )

        self.collection = self.chroma_client.get_collection("rag_documents")

        self.semantic_text_splitter = SemanticChunker(
            self.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=90
        )

        # Load HuggingFace reranker model (cross-encoder)
        self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    def query(self, query_text: str, customer: str,top_k: int = 5, min_score: float = 0.0):
        print(f"Querying for customer: {customer} with text: {query_text}")
        if not isinstance(query_text, (str, list)):
            raise TypeError(f"Query text must be str or list of str, got {type(query_text)}")
        if isinstance(query_text, list):
            for i, item in enumerate(query_text):
                if not isinstance(item, str):
                    raise TypeError(f"Query list item {i} must be str, got {type(item)}")
        query_embedding = [self.embeddings.embed_query(query_text)]
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k * 2,  # retrieve more for reranking
            where={"customer": customer},
            include=["documents", "metadatas", "distances"]
        )
        retrieved_docs = []
        for doc, metadata, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            retrieved_docs.append({
                "document": doc,
                "metadata": metadata,
                "distance": float(dist),
                "similarity": 1 / (1 + dist)
            })
            print(f"Retrieved document: {doc[:10]}...", f"Similarity: {1 / (1 + dist)}", f"Metadata: {metadata}", sep="\n")
            
        logging.info(f"Retrieved {len(retrieved_docs)} documents before reranking. scores: {[doc['similarity'] for doc in retrieved_docs]}")

        # Rerank top_k documents using HuggingFace reranker with score filtering
        reranked_docs = self.rerank_top_k_docs(query_text, retrieved_docs, top_k=top_k, min_score=min_score)

        return reranked_docs

    def rerank_top_k_docs(self, query: str, docs: list[dict], top_k: int = 5, min_score: float = 0.0):
        # Prepare pairs for reranker: (query, doc_text)
        pairs = [(query, doc["document"]) for doc in docs[:top_k]]

        # Get scores from reranker model (numpy array)
        scores = self.reranker.predict(pairs)

        # Pair each doc with its score
        scored_docs = list(zip(docs[:top_k], scores))

        # Filter by minimum score threshold
        filtered_docs = scored_docs

        # Sort filtered docs by score descending
        filtered_docs.sort(key=lambda x: x[1], reverse=True)

        # Return just the docs sorted by rerank score and filtered by threshold
        reranked_docs = [doc for doc, score in filtered_docs]
        
        if not reranked_docs:
            logging.info("No documents passed rerank filtering, returning empty string.")
            return ""
    
        return reranked_docs