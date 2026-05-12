"""
Iteration 1: Zero-shot toponym extraction from OCR page JSON files.

Usage:
    python3 extract_toponyms.py --input trial/ --output output/ --limit 10
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import ollama
from lingua import Language, LanguageDetectorBuilder

SUPPORTED_LANGUAGES = [
    Language.ENGLISH,
    Language.FRENCH,
    Language.RUSSIAN,
    Language.CHINESE,
    Language.JAPANESE,
    Language.GERMAN,
]

detector = LanguageDetectorBuilder.from_languages(*SUPPORTED_LANGUAGES).build()

PROMPT = """\
Extract all place names (toponyms) from the text below.
Toponyms include: cities, historical sites, ancient kingdoms, regions, mountain ranges, rivers, and deserts.

If no toponyms are found, return an empty array [].
Return ONLY a JSON array of strings, one toponym per item, no explanation.

Text:
{text}"""

VERIFY_PROMPT = """\
Is the bracketed term used as a place name in the following text?
Answer only "yes" or "no", no explanation.

Text: {context}
Term: [{candidate}]"""

CONTEXT_CHARS = 150


def detect_language(text: str) -> Language | None:
    if not text or len(text.strip()) < 15:
        return None
    return detector.detect_language_of(text)


def build_prompt(text: str, language: Language) -> str:
    return PROMPT.format(text=text)


def parse_toponyms(response: str) -> list[str]:
    match = re.search(r"\[.*?\]", response, re.DOTALL)
    if not match:
        return []
    try:
        toponyms = json.loads(match.group())
        return [t.strip() for t in toponyms if isinstance(t, str) and t.strip()]
    except json.JSONDecodeError:
        return []


def find_in_text(text: str, candidate: str) -> int | None:
    """Return start position of candidate in text (case-insensitive), or None if not found."""
    match = re.search(re.escape(candidate), text, re.IGNORECASE)
    return match.start() if match else None


def get_context(text: str, position: int, length: int) -> str:
    start = max(0, position - CONTEXT_CHARS)
    end = min(len(text), position + length + CONTEXT_CHARS)
    return f"...{text[start:position]}[{text[position:position+length]}]{text[position+length:end]}..."


def verify_toponym(candidate: str, context: str, model: str) -> bool:
    prompt = VERIFY_PROMPT.format(context=context, candidate=candidate)
    response = ollama.generate(model=model, prompt=prompt, options={"temperature": 0})
    return response["response"].strip().lower().startswith("yes")


def filter_with_context(candidates: list[str], text: str, model: str) -> tuple[list[str], list[str]]:
    """Verify each candidate against its context. Returns (confirmed, rejected)."""
    confirmed, rejected = [], []
    for candidate in candidates:
        pos = find_in_text(text, candidate)
        if pos is None:
            rejected.append(candidate)  # not in source text — hallucination
            continue
        context = get_context(text, pos, len(candidate))
        if verify_toponym(candidate, context, model):
            confirmed.append(candidate)
        else:
            rejected.append(candidate)
    return confirmed, rejected


def process_page(page: dict, model: str) -> tuple[list[str], list[str], Language | None]:
    """Run toponym extraction on a single page. Returns (confirmed, rejected, detected_language)."""
    text = page.get("body_text", "").strip()

    if not text or text == "(empty)":
        return [], [], None

    language = detect_language(text)
    if language is None:
        return [], [], None

    prompt = build_prompt(text, language)
    response = ollama.generate(model=model, prompt=prompt, options={"temperature": 0})
    raw = parse_toponyms(response["response"])
    confirmed, rejected = filter_with_context(raw, text, model)

    return confirmed, rejected, language


def main():
    parser = argparse.ArgumentParser(description="Zero-shot toponym extraction (Iteration 1)")
    parser.add_argument("--input", required=True, help="Folder with OCR page JSON files")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--limit", type=int, default=None, help="Max number of pages to process")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect page files, skip retry error files
    page_files = sorted(
        f for f in input_dir.glob("*_page*.json")
        if "retry.error" not in f.name
    )

    if args.limit:
        page_files = page_files[: args.limit]

    print(f"Processing {len(page_files)} pages with model '{args.model}'...")

    # Output data structures
    page_toponyms: dict[str, list[str]] = {}                          # page_id → [toponyms]
    cooccurrence: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # toponym → {toponym → count}
    log_path = output_dir / "log.jsonl"

    with open(log_path, "w", encoding="utf-8") as log_file:
        for i, page_file in enumerate(page_files):
            with open(page_file, encoding="utf-8") as f:
                page = json.load(f)

            page_id = page.get("custom_id", page_file.stem)

            try:
                toponyms, rejected, language = process_page(page, args.model)
            except Exception as e:
                print(f"  [{i+1}/{len(page_files)}] ERROR {page_id}: {e}", file=sys.stderr)
                continue

            lang_name = language.name if language else "skipped"
            page_toponyms[page_id] = toponyms

            # Update co-occurrence graph: link every pair of toponyms on this page
            for j, t1 in enumerate(toponyms):
                for t2 in toponyms[j + 1:]:
                    if t1 != t2:
                        cooccurrence[t1][t2] += 1
                        cooccurrence[t2][t1] += 1

            # Write one log entry per page
            log_entry = {
                "page_id": page_id,
                "language": lang_name,
                "toponym_count": len(toponyms),
                "toponyms": toponyms,
                "rejected": rejected,
            }
            log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            status = f"{len(toponyms)} toponyms" if toponyms else "none / skipped"
            print(f"  [{i+1}/{len(page_files)}] {page_id} ({lang_name}): {status}")

    # Save summary files
    with open(output_dir / "page_toponyms.json", "w", encoding="utf-8") as f:
        json.dump(page_toponyms, f, ensure_ascii=False, indent=2)

    with open(output_dir / "cooccurrence_graph.json", "w", encoding="utf-8") as f:
        json.dump(cooccurrence, f, ensure_ascii=False, indent=2)

    total_toponyms = sum(len(v) for v in page_toponyms.values())
    unique_toponyms = len(cooccurrence)
    print(f"\nDone. {total_toponyms} total extractions, {unique_toponyms} unique toponyms.")
    print(f"Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
