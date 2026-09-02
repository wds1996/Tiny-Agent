from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from tiny_agent.capstone import CorpusDocument, extract_pdf_text, write_corpus_jsonl

HERE = Path(__file__).resolve().parent
STAGE_ROOT = HERE.parent
MANIFEST = STAGE_ROOT / "data" / "open_papers.json"
GENERATED = STAGE_ROOT / "generated"
PDF_DIR = GENERATED / "pdfs"
OUTPUT = GENERATED / "corpus.jsonl"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"reuse {destination.name}")
        return
    request = Request(
        url,
        headers={"User-Agent": "Tiny-Agent-OpenScholar/0.1 educational corpus bootstrap"},
    )
    with urlopen(request, timeout=60) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"download did not look like a PDF: {url}")
    destination.write_bytes(data)
    print(f"downloaded {destination.name} ({len(data):,} bytes)")


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    documents: list[CorpusDocument] = []
    for item in manifest:
        paper_id = str(item["id"])
        pdf_path = PDF_DIR / f"{paper_id}.pdf"
        download(str(item["pdf_url"]), pdf_path)
        print(f"extracting {paper_id} ...")
        text = extract_pdf_text(pdf_path)
        documents.append(
            CorpusDocument(
                id=paper_id,
                title=str(item["title"]),
                text=text,
                source_url=str(item["source_url"]),
                year=int(item["year"]),
                metadata={"arxiv_id": item["arxiv_id"], "generated_from": "open_papers.json"},
            )
        )
    write_corpus_jsonl(OUTPUT, documents)
    print(f"\nWrote {len(documents)} documents to {OUTPUT}")
    print("Generated PDFs/corpus are local artifacts and are not committed to Git.")


if __name__ == "__main__":
    main()
