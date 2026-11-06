import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from services.llm_client import llm_client, LLMError

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "rag" / "index"

LANG_MESSAGES = {
    "en": {
        "name": "English",
        "no_answer": "I don't have reliable information on that in my knowledge base. Please check with your local agriculture officer or Krishi Vigyan Kendra.",
        "fallback": "The AI service is unavailable right now. Here are the most relevant passages:",
    },
    "te": {
        "name": "Telugu (తెలుగు)",
        "no_answer": "నా సమాచార భాండారంలో దీనిపై నమ్మదగిన సమాచారం లేదు. దయచేసి మీ స్థానిక వ్యవసాయ అధికారిని లేదా కృషి విజ్ఞాన కేంద్రాన్ని సంప్రదించండి.",
        "fallback": "AI సేవ ప్రస్తుతం అందుబాటులో లేదు. సంబంధిత సమాచారం ఇదిగో:",
    },
    "ta": {
        "name": "Tamil (தமிழ்)",
        "no_answer": "இதைப் பற்றிய நம்பகமான தகவல் என் அறிவுத் தளத்தில் இல்லை. உங்கள் உள்ளூர் வேளாண் அலுவலரையோ கிருஷி விஞ்ஞான் கேந்திராவையோ அணுகவும்.",
        "fallback": "AI சேவை தற்போது கிடைக்கவில்லை. தொடர்புடைய பகுதிகள் இதோ:",
    },
    "hi": {
        "name": "Hindi (हिन्दी)",
        "no_answer": "मेरे ज्ञान आधार में इस बारे में विश्वसनीय जानकारी नहीं है। कृपया अपने स्थानीय कृषि अधिकारी या कृषि विज्ञान केंद्र से संपर्क करें।",
        "fallback": "AI सेवा अभी उपलब्ध नहीं है। सबसे प्रासंगिक जानकारी यह है:",
    },
}


class RAGService:
    def __init__(self, index_dir: Path = INDEX_DIR):
        self.index_dir = index_dir
        self.chunks: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self.faiss_index = None
        self.meta: Dict[str, Any] = {}
        self.loaded = False
        self.load_index()

    def load_index(self) -> bool:
        chunks_file = self.index_dir / "chunks.json"
        meta_file = self.index_dir / "index_meta.json"
        vec_file = self.index_dir / "vectors.npy"
        faiss_file = self.index_dir / "faiss.index"

        if not chunks_file.exists():
            logger.warning("RAG chunks not found. Run python rag/build_index.py to create index.")
            self.loaded = False
            return False

        try:
            with open(chunks_file, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)

            if vec_file.exists():
                self.vectors = np.load(vec_file)

            if faiss_file.exists():
                try:
                    import faiss
                    self.faiss_index = faiss.read_index(str(faiss_file))
                except Exception as e:
                    logger.warning(f"Could not load FAISS index: {e}, falling back to NumPy vectors.")

            self.loaded = True
            return True
        except Exception as e:
            logger.error(f"Error loading RAG index: {e}")
            self.loaded = False
            return False

    def search(
        self,
        query: str,
        k: int = 4,
        crop: Optional[str] = None,
        fertilizer: Optional[str] = None,
        min_score: float = 0.35,
    ) -> List[Dict[str, Any]]:
        if not self.loaded or not self.chunks:
            return []

        q_vec = None
        if llm_client.configured:
            try:
                raw_embeds = llm_client.embed([query], task_type="RETRIEVAL_QUERY", dims=768)
                q_vec = np.array(raw_embeds[0], dtype="float32")
                norm = np.linalg.norm(q_vec)
                if norm > 0:
                    q_vec = q_vec / norm
            except Exception as e:
                logger.warning(f"Query embedding failed: {e}, falling back to keyword matching.")

        hits = []
        if q_vec is not None and self.vectors is not None:
            sims = np.dot(self.vectors, q_vec)
            for idx, score in enumerate(sims):
                chunk = self.chunks[idx]
                boosted = float(score)
                # Boost if source matches crop or fertilizer
                src_lower = chunk.get("source", "").lower()
                if crop and crop.lower() in src_lower:
                    boosted += 0.05
                if fertilizer and fertilizer.lower() in src_lower:
                    boosted += 0.05

                if boosted >= min_score:
                    hits.append({
                        "chunk": chunk,
                        "source": chunk.get("source"),
                        "heading": chunk.get("heading"),
                        "score": round(boosted, 3),
                    })
            hits.sort(key=lambda x: x["score"], reverse=True)
            hits = hits[:k]
        else:
            # Keyword fallback
            q_words = [w.lower() for w in query.split() if len(w) >= 4]
            for chunk in self.chunks:
                text_lower = chunk["text"].lower()
                match_count = sum(1 for w in q_words if w in text_lower)
                src_lower = chunk.get("source", "").lower()
                if crop and crop.lower() in src_lower:
                    match_count += 1
                if fertilizer and fertilizer.lower() in src_lower:
                    match_count += 1

                if match_count > 0:
                    hits.append({
                        "chunk": chunk,
                        "source": chunk.get("source"),
                        "heading": chunk.get("heading"),
                        "score": round(min(0.99, match_count * 0.2), 3),
                    })
            hits.sort(key=lambda x: x["score"], reverse=True)
            hits = hits[:k]

        return hits

    def answer(
        self,
        question: str,
        prediction_context: Dict[str, Any],
        language: str = "en",
        k: int = 4,
    ) -> Dict[str, Any]:
        lang_info = LANG_MESSAGES.get(language, LANG_MESSAGES["en"])
        crop = prediction_context.get("crop")
        fertilizer = prediction_context.get("fertilizer")

        hits = self.search(question, k=k, crop=crop, fertilizer=fertilizer)

        if not hits:
            return {
                "answer": lang_info["no_answer"],
                "sources": [],
                "fallback": False,
                "model": llm_client.model if llm_client.configured else None,
            }

        # Build prompt
        passages_text = "\n\n".join(
            f"[{i}] ({h['chunk']['source']} — {h['chunk']['heading']}):\n{h['chunk']['text']}"
            for i, h in enumerate(hits, 1)
        )

        context_summary = (
            f"Crop: {crop}, Soil: {prediction_context.get('soil')}, "
            f"Fertilizer Recommended: {fertilizer} (Confidence: {prediction_context.get('confidence')}), "
            f"NPK input: N={prediction_context.get('nitrogen')}, P={prediction_context.get('phosphorous')}, K={prediction_context.get('potassium')}"
        )

        system_prompt = (
            f"You are an agricultural extension assistant for Smart Fertilizer Advisor.\n"
            f"Answer ONLY from the numbered agronomic passages below and the farmer's context.\n"
            f"If the passages do not contain enough facts to answer the question, state: \"{lang_info['no_answer']}\".\n"
            f"Rules:\n"
            f"1. Do not invent doses, crop stages, or product names not in the passages or context.\n"
            f"2. Keep answers concise (< 150 words), practical, and specific to the farmer's crop and fertilizer.\n"
            f"3. Include numbers and units when mentioning dosage or timing.\n"
            f"4. Always cite supporting passages using bracket notation like [1], [2].\n"
            f"5. Reply in {lang_info['name']}."
        )

        user_prompt = (
            f"FARMER CONTEXT:\n{context_summary}\n\n"
            f"AGRONOMY PASSAGES:\n{passages_text}\n\n"
            f"FARMER QUESTION:\n{question}"
        )

        sources = [{"source": h["source"], "heading": h["heading"], "score": h["score"]} for h in hits]

        try:
            answer_text = llm_client.generate(user_prompt, system=system_prompt)
            return {
                "answer": answer_text.strip(),
                "sources": sources,
                "fallback": False,
                "model": llm_client.model,
            }
        except LLMError as e:
            logger.warning(f"LLM generation failed: {e}. Returning retrieval fallback.")
            fallback_text = lang_info["fallback"] + "\n\n" + "\n\n".join(
                f"[{i}] {h['chunk']['title']} — {h['chunk']['heading']}:\n{h['chunk']['text'][:350]}..."
                for i, h in enumerate(hits, 1)
            )
            return {
                "answer": fallback_text,
                "sources": sources,
                "fallback": True,
                "model": None,
            }


rag_service = RAGService()

