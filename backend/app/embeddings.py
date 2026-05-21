from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import os
import pickle
import threading
import hashlib

MODEL_NAME = "all-MiniLM-L6-v2"
BASE_INDEX_DIR = "vector_store"

os.makedirs(BASE_INDEX_DIR, exist_ok=True)


class EmbeddingStore:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.model = SentenceTransformer(MODEL_NAME)
        self.dimension = 384

        user_dir = os.path.join(BASE_INDEX_DIR, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)

        self.faiss_path = os.path.join(user_dir, "faiss_index.bin")
        self.metadata_path = os.path.join(user_dir, "metadata.pkl")
        self._lock = threading.Lock()

        if os.path.exists(self.faiss_path) and os.path.exists(self.metadata_path):
            self.index = faiss.read_index(self.faiss_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []

        # Build hash set from existing metadata
        self._chunk_hashes: set[str] = {
            m.get("hash", "") for m in self.metadata if m.get("hash")
        }

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def add_texts(self, texts, metadatas=None, doc_id: int = None):
        """Add texts to FAISS index, skipping duplicates."""
        with self._lock:
            new_texts = []
            new_metadatas = []

            for i, text in enumerate(texts):
                chunk_hash = self._hash_text(text)

                if chunk_hash in self._chunk_hashes:
                    print(f"⚠️  Skipping duplicate chunk (hash: {chunk_hash[:8]}...)")
                    continue

                self._chunk_hashes.add(chunk_hash)
                new_texts.append(text)

                meta = metadatas[i] if metadatas else {"text": text}
                meta["hash"] = chunk_hash
                meta["doc_id"] = doc_id  # Track which document this chunk belongs to
                new_metadatas.append(meta)

            if not new_texts:
                print("ℹ️  All chunks already indexed — nothing new to add.")
                return

            print(f"✅ Adding {len(new_texts)} new chunks (skipped {len(texts) - len(new_texts)} duplicates)")

            embeddings = self.model.encode(new_texts, show_progress_bar=False)
            embeddings = np.array(embeddings).astype('float32')
            faiss.normalize_L2(embeddings)

            self.index.add(embeddings)
            self.metadata.extend(new_metadatas)
            self.save()

    def search(self, query, k=4, doc_ids: list[int] = None):
        """
        Search for similar texts.
        If doc_ids is provided, only return results from those documents.
        """
        with self._lock:
            if self.index.ntotal == 0:
                return []

            query_embedding = self.model.encode([query], show_progress_bar=False)
            query_embedding = np.array(query_embedding).astype('float32')
            faiss.normalize_L2(query_embedding)

            # Fetch more results than needed so we can filter by doc_id
            fetch_k = min(self.index.ntotal, k * 4 if doc_ids else k)
            distances, indices = self.index.search(query_embedding, fetch_k)

            results = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx >= len(self.metadata):
                    continue
                meta = self.metadata[idx]

                # Filter by doc_id if specified
                if doc_ids and meta.get("doc_id") not in doc_ids:
                    continue

                results.append({
                    "text": meta.get("text", ""),
                    "metadata": meta,
                    "distance": float(distance)
                })

                if len(results) >= k:
                    break

            return results

    def delete_document_chunks(self, doc_id: int):
        """
        Remove all chunks belonging to a specific document.
        Rebuilds the FAISS index from scratch excluding that doc's chunks.
        """
        with self._lock:
            remaining_meta = [m for m in self.metadata if m.get("doc_id") != doc_id]

            if len(remaining_meta) == self.metadata:
                return  # Nothing to remove

            print(f"🗑️  Removing chunks for doc_id={doc_id}, rebuilding index...")

            # Rebuild index from remaining chunks
            self.index = faiss.IndexFlatIP(self.dimension)
            self._chunk_hashes = set()

            if remaining_meta:
                texts = [m.get("text", "") for m in remaining_meta]
                embeddings = self.model.encode(texts, show_progress_bar=False)
                embeddings = np.array(embeddings).astype('float32')
                faiss.normalize_L2(embeddings)
                self.index.add(embeddings)
                self._chunk_hashes = {m.get("hash", "") for m in remaining_meta if m.get("hash")}

            self.metadata = remaining_meta
            self.save()
            print(f"✅ Index rebuilt with {len(remaining_meta)} chunks remaining")

    def save(self):
        faiss.write_index(self.index, self.faiss_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)

    def clear(self):
        with self._lock:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
            self._chunk_hashes = set()
            self.save()


_store_cache: dict[int, EmbeddingStore] = {}
_store_lock = threading.Lock()


def get_user_store(user_id: int) -> EmbeddingStore:
    with _store_lock:
        if user_id not in _store_cache:
            _store_cache[user_id] = EmbeddingStore(user_id)
        return _store_cache[user_id]

def rehydrate_all_stores():
    """
    On server startup, reload all existing user FAISS indices from disk
    so users don't get 'No documents found' after a server restart.
    """
    if not os.path.exists(BASE_INDEX_DIR):
        return

    rehydrated = 0
    for folder in os.listdir(BASE_INDEX_DIR):
        if not folder.startswith("user_"):
            continue
        try:
            user_id = int(folder.replace("user_", ""))
            user_dir = os.path.join(BASE_INDEX_DIR, folder)
            faiss_path = os.path.join(user_dir, "faiss_index.bin")
            metadata_path = os.path.join(user_dir, "metadata.pkl")

            # Only rehydrate if both files exist and index has data
            if not os.path.exists(faiss_path) or not os.path.exists(metadata_path):
                continue

            with _store_lock:
                if user_id not in _store_cache:
                    store = EmbeddingStore(user_id)
                    if store.index.ntotal > 0:
                        _store_cache[user_id] = store
                        rehydrated += 1
                        print(f"✅ Rehydrated store for user_{user_id}: {store.index.ntotal} chunks")

        except (ValueError, Exception) as e:
            print(f"⚠️  Failed to rehydrate {folder}: {e}")

    print(f"🔄 Rehydration complete: {rehydrated} user store(s) loaded from disk")

embedding_store = EmbeddingStore(user_id=0)