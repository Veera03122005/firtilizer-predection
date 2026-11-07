import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, embed_model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        self.embed_model = embed_model or os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize google-genai Client: {e}")

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.client)

    def generate(self, prompt: str, system: Optional[str] = None, timeout: int = 15, temperature: float = 0.2) -> str:
        if not self.configured:
            raise LLMError("Gemini API key is not configured.")

        # Retry once on error
        for attempt in range(2):
            try:
                config = {"temperature": temperature}
                if system:
                    config["system_instruction"] = system

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                if response and response.text:
                    return response.text
                raise LLMError("Empty response from Gemini API.")
            except Exception as e:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                logger.error(f"Gemini generate failed: {e}")
                raise LLMError(str(e))

    def embed(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT", dims: int = 768) -> List[List[float]]:
        if not self.configured:
            raise LLMError("Gemini API key is not configured for embeddings.")

        try:
            results = []
            # Batch in up to 50 texts to stay well within limits
            for i in range(0, len(texts), 50):
                batch = texts[i:i + 50]
                for attempt in range(5):
                    try:
                        resp = self.client.models.embed_content(
                            model=self.embed_model,
                            contents=batch,
                            config={"output_dimensionality": dims},
                        )
                        for embedding in resp.embeddings:
                            results.append(embedding.values)
                        break
                    except Exception as err:
                        if "429" in str(err) or "RESOURCE_EXHAUSTED" in str(err):
                            logger.info(f"Rate limited on embed batch {i}, waiting 15s before retry...")
                            time.sleep(15.0)
                            continue
                        raise err
            return results
        except Exception as e:
            logger.error(f"Gemini embed failed: {e}")
            raise LLMError(str(e))


llm_client = LLMClient()

