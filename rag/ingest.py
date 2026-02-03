import logging
import os
import uuid
from langchain_community.document_loaders import TextLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_chroma import Chroma
from .utils import Utils


class RagIngest:
    def __init__(self, config_path: str = "config.yaml"):
        self.utils = Utils(config_path)
        self.config = self.utils.config


        self.llm = self.utils.initialize_llm()
        self.embeddings = self.utils.initialize_embeddings()

        # ✅ LangChain Chroma (CORRECT)
        self.vectorstore = Chroma(
            collection_name="rag_documents",
            embedding_function=self.embeddings,
            persist_directory=self.config["vectorstore"]["persist_directory"]
        )

        # Semantic chunking
        self.chunker = SemanticChunker(
            self.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=90
        )

    def add_document(self, path: str, filename: str, phone: str):
        loader = TextLoader(path, encoding="utf-8")
        docs = loader.load()

        chunks = []
        for doc in docs:
            # Validate page_content before chunking
            if not doc.page_content or not isinstance(doc.page_content, str):
                logging.warning(f"Skipping empty or invalid document chunk in {filename}")
                continue

            chunks.extend(
                self.chunker.create_documents(
                    texts=[doc.page_content],
                    metadatas=[doc.metadata]
                )
            )
            
        if not chunks:
            logging.warning(f"No valid chunks to ingest for file {filename}")
            return

        doc_id = str(uuid.uuid4())
        for i, c in enumerate(chunks):
            c.metadata.update({
                "customer": phone,
                "document_id": doc_id,
                "filename": filename,
                "source": path,
                "chunk_number": i + 1,
                "total_chunks": len(chunks)
            })

        logging.info(f"Ingesting {len(chunks)} chunks from {filename}")
        print(f"Ingesting {len(chunks)} chunks from {filename}")
        self.vectorstore.add_documents(chunks)

    def ingest_directory(self, phone):
        directory = os.path.join(self.config["document_loader"]["directory"], str(phone))

        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                full_path = os.path.join(directory, filename)
                self.add_document(full_path, filename, phone)

        logging.info("✅ All documents ingested successfully")
    