"""Evaluate retrieval (and optionally answers) against a hand-written golden set.

Each case says which document and page should be retrieved for a question:

    {"question": "...", "filename": "report.pdf", "pages": [4, 5], "answer_contains": ["12%"]}

Metrics:
  hit@k  - share of questions where a chunk from the expected file/page is in the top k
  MRR    - mean reciprocal rank of the first correct chunk (rewards ranking it higher)
  answer - (with --answers) share of answers containing every expected phrase

Run against the documents already indexed by the app:

    cd backend
    uv run python ../eval/run_eval.py ../eval/golden.json [--answers]

Re-run after changing chunk size, overlap, top_k or the embedding model to compare settings.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from openai import OpenAI  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.llm.client import OpenAIChat  # noqa: E402
from app.llm.prompts import answer_messages  # noqa: E402
from app.retrieval.embedder import OpenAIEmbedder  # noqa: E402
from app.retrieval.retriever import Retriever  # noqa: E402
from app.retrieval.vector_store import RetrievedChunk, VectorStore  # noqa: E402


def is_match(chunk: RetrievedChunk, case: dict) -> bool:
    if chunk.filename != case["filename"]:
        return False
    pages = case.get("pages")
    return not pages or any(chunk.page_start <= p <= chunk.page_end for p in pages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path)
    parser.add_argument("--answers", action="store_true", help="also generate and check answers")
    args = parser.parse_args()

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    store = VectorStore(settings.chroma_dir)
    # No relevance floor here: we want to see where the right chunk ranks even when scores are low.
    retriever = Retriever(OpenAIEmbedder(client, settings.embedding_model), store, settings.top_k, 0.0)
    llm = OpenAIChat(client, settings.chat_model)

    cases = json.loads(args.golden.read_text(encoding="utf-8"))
    hits, reciprocal_ranks, answer_passes = 0, [], 0

    for case in cases:
        chunks = retriever.retrieve(case["question"])
        rank = next((i for i, c in enumerate(chunks, 1) if is_match(c, case)), None)
        hits += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        status = f"rank {rank}" if rank else "MISS"

        if args.answers and case.get("answer_contains"):
            answer = llm.complete(answer_messages([], case["question"], chunks))
            ok = all(p.lower() in answer.lower() for p in case["answer_contains"])
            answer_passes += ok
            status += f", answer {'ok' if ok else 'FAIL'}"
        print(f"[{status:>20}] {case['question']}")

    n = len(cases)
    print(f"\n{n} questions | top_k={settings.top_k} chunk={settings.chunk_size_tokens} "
          f"overlap={settings.chunk_overlap_tokens} embed={settings.embedding_model}")
    print(f"hit@{settings.top_k}: {hits / n:.2%}   MRR: {sum(reciprocal_ranks) / n:.3f}")
    if args.answers:
        checked = sum(1 for c in cases if c.get("answer_contains"))
        print(f"answer check: {answer_passes}/{checked}")


if __name__ == "__main__":
    main()
