from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import pickle

MODEL_NAME = "all-MiniLM-L6-v2"
FAISS_INDEX_PATH = "faiss_index.bin"
METADATA_PATH = "metadata.pkl"

class EmbeddingStore:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)
        self.dimension = 384  # Dimension for all-MiniLM-L6-v2
        
        # Load or create FAISS index
        if os.path.exists(FAISS_INDEX_PATH):
            self.index = faiss.read_index(FAISS_INDEX_PATH)
            with open(METADATA_PATH, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
    
    def add_texts(self, texts, metadatas=None):
        """Add texts to FAISS index"""
        embeddings = self.model.encode(texts)
        embeddings = np.array(embeddings).astype('float32')
        
        self.index.add(embeddings)
        
        if metadatas:
            self.metadata.extend(metadatas)
        else:
            self.metadata.extend([{"text": text} for text in texts])
        
        self.save()
    
    def search(self, query, k=3):
        """Search for similar texts"""
        if self.index.ntotal == 0:
            return []
        
        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')
        
        distances, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
        
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx < len(self.metadata):
                results.append({
                    "text": self.metadata[idx].get("text", ""),
                    "metadata": self.metadata[idx],
                    "distance": float(distance)
                })
        
        return results
    
    def save(self):
        """Save FAISS index and metadata"""
        faiss.write_index(self.index, FAISS_INDEX_PATH)
        with open(METADATA_PATH, 'wb') as f:
            pickle.dump(self.metadata, f)

embedding_store = EmbeddingStore()