import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
KB_DIR = BASE_DIR / "knowledge_base"
INDEX_DIR = BASE_DIR / "rag" / "index"


def parse_markdown(file_path: Path) -> Dict[str, Any]:
    text = file_path.read_text(encoding="utf-8")
    meta = {}
    body = text

    # Parse YAML front matter if present
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1].strip()
            body = parts[2].strip()
            for line in raw_meta.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")

    title = meta.get("title", file_path.stem.replace("-", " ").title())
    return {"meta": meta, "title": title, "body": body, "rel_path": file_path.relative_to(KB_DIR).as_posix()}


def chunk_document(doc: Dict[str, Any], chunk_size: int = 800, overlap: int = 150) -> List[Dict[str, Any]]:
    title = doc["title"]
    source = doc["rel_path"]
    body = doc["body"]

    chunks = []
    # Split by ## headings
    sections = body.split("\n## ")
    main_heading = "Overview"

    for i, sec in enumerate(sections):
        if i == 0:
            heading = main_heading
            content = sec.strip()
        else:
            lines = sec.split("\n", 1)
            heading = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""

        if not content:
            continue

        paragraphs = content.split("\n\n")
        cur_text = ""

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue

            if len(cur_text) + len(p) + 2 > chunk_size and cur_text:
                prefix = f"{title} — {heading}\n"
                chunks.append({
                    "id": f"{source}#{len(chunks)}",
                    "source": source,
                    "title": title,
                    "heading": heading,
                    "text": prefix + cur_text,
                    "char_count": len(prefix + cur_text),
                })
                # Overlap
                cur_text = cur_text[-overlap:] + " " + p if overlap < len(cur_text) else p
            else:
                cur_text = (cur_text + "\n\n" + p).strip()

        if cur_text:
            prefix = f"{title} — {heading}\n"
            chunks.append({
                "id": f"{source}#{len(chunks)}",
                "source": source,
                "title": title,
                "heading": heading,
                "text": prefix + cur_text,
                "char_count": len(prefix + cur_text),
            })

    return chunks


def build_index(dry_run: bool = False):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    md_files = [
        f for f in KB_DIR.rglob("*.md")
        if not f.name.startswith("_")
    ]
    logger.info(f"Found {len(md_files)} knowledge base documents.")

    all_chunks = []
    hasher = hashlib.sha256()

    for f in md_files:
        hasher.update(f.read_bytes())
        doc = parse_markdown(f)
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)

    logger.info(f"Generated {len(all_chunks)} chunks across {len(md_files)} documents.")

    if dry_run:
        print(f"DRY RUN: Document count = {len(md_files)}, Chunk count = {len(all_chunks)}")
        sizes = [c["char_count"] for c in all_chunks]
        print(f"Chunk sizes: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes)}")
        return

    from services.llm_client import llm_client
    if not llm_client.configured:
        logger.warning("Gemini API key is not set; generating dummy embeddings for offline index testing.")
        # Create deterministic pseudo-embeddings based on text hash for offline testing
        rng = np.random.default_rng(42)
        vectors = rng.standard_normal((len(all_chunks), 768)).astype("float32")
    else:
        texts = [c["text"] for c in all_chunks]
        logger.info("Embedding chunks with gemini-embedding-001...")
        embeds = llm_client.embed(texts, task_type="RETRIEVAL_DOCUMENT", dims=768)
        vectors = np.array(embeds, dtype="float32")

    # L2 normalise
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms

    # Save numpy fallback
    np.save(INDEX_DIR / "vectors.npy", vectors)

    # Save FAISS index
    try:
        import faiss
        index = faiss.IndexFlatIP(768)
        index.add(vectors)
        faiss.write_index(index, str(INDEX_DIR / "faiss.index"))
        logger.info("Saved faiss.index")
    except Exception as e:
        logger.warning(f"Could not build FAISS index ({e}); NumPy vectors.npy will be used as fallback.")

    with open(INDEX_DIR / "chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(md_files),
        "chunk_count": len(all_chunks),
        "dims": 768,
        "embedding_model": "gemini-embedding-001",
        "kb_hash": hasher.hexdigest(),
    }
    with open(INDEX_DIR / "index_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info(f"Built index in {INDEX_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print chunk statistics without embedding")
    args = parser.parse_args()
    build_index(dry_run=args.dry_run)
