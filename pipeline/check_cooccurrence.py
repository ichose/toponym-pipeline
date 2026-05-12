"""
Iteration 2: Co-occurrence guided toponym extraction.

For each page where Iteration 1 found at least one toponym:
  1. Predict candidate toponyms via co-occurrence graph
  2. Fuzzy search for each predicted toponym in the page text
  3. LLM verification: is the candidate a place name in context?
  4. Update page_toponyms and cooccurrence_graph with confirmed new toponyms

Usage:
    python3 iteration2.py --input trial_en/ --iter1 output_en_v2/ --output output_en_iter2/
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import ollama
from rapidfuzz.distance import Levenshtein

CONTEXT_CHARS = 150  # characters of context on each side for LLM verification

VERIFY_PROMPT = """\
Does the bracketed term refer to a specific place name (toponym) used as a noun in the following text?
Answer "yes" only if it is a noun naming a specific place (city, region, kingdom, river, etc.).
Answer "no" if it is an adjective (e.g. Tibetan, Iranian, Syriac), a demonym (e.g. Persians, Ferganians), or not a place name.
Answer only "yes" or "no", no explanation.

Text: {context}

Bracketed term: [{candidate}]"""


def edit_distance_threshold(length: int) -> int:
    if length < 5:
        return 1
    if length <= 8:
        return 2
    return 3


def get_word_ngrams(text: str, n: int) -> list[tuple[int, str]]:
    """Return all n-word spans from text with their start positions."""
    words = list(re.finditer(r'\S+', text))
    ngrams = []
    for i in range(len(words) - n + 1):
        span_words = words[i:i + n]
        start = span_words[0].start()
        ngram = text[start:span_words[-1].end()]
        ngrams.append((start, ngram))
    return ngrams


def strip_punctuation(s: str) -> str:
    """Strip leading/trailing punctuation and whitespace from a candidate string."""
    return re.sub(r'^[\W_]+|[\W_]+$', '', s, flags=re.UNICODE).strip()


def expand_variants(toponym: str) -> list[str]:
    """Split a compound toponym into individual searchable variants.

    Only expands if '(' or ' or ' is present, otherwise returns the original as-is.
    Examples:
      "Mouru (Muru, Merw)"        → ["Mouru", "Muru", "Merw"]
      "An-si (Parthia)"           → ["An-si", "Parthia"]
      "Ñan-si or An-si (Parthia)" → ["Ñan-si", "An-si", "Parthia"]
      "Fergana"                   → ["Fergana"]
    """
    if '(' not in toponym and ' or ' not in toponym:
        return [toponym]
    variants = []
    for part in toponym.split(' or '):
        part = part.strip()
        m = re.match(r'^(.*?)\s*\(([^)]+)\)$', part)
        if m:
            main = m.group(1).strip()
            if main:
                variants.append(main)
            for v in m.group(2).split(','):
                v = v.strip()
                if v:
                    variants.append(v)
        else:
            if part:
                variants.append(part)
    return variants


def fuzzy_search(text: str, toponym: str) -> list[dict]:
    """Find approximate matches of toponym in text using edit distance."""
    threshold = edit_distance_threshold(len(toponym))
    n_words = len(toponym.split())
    ngrams = get_word_ngrams(text, n_words)

    candidates = []
    seen = set()
    for pos, ngram in ngrams:
        dist = Levenshtein.distance(toponym.lower(), ngram.lower())
        if dist <= threshold and ngram.lower() not in seen:
            seen.add(ngram.lower())
            candidates.append({"text": ngram, "position": pos, "distance": dist})

    return sorted(candidates, key=lambda x: x["distance"])


def get_context(text: str, position: int, length: int) -> str:
    """Extract surrounding context around a candidate position."""
    start = max(0, position - CONTEXT_CHARS)
    end = min(len(text), position + length + CONTEXT_CHARS)
    before = text[start:position]
    after = text[position + length:end]
    return f"...{before}[{text[position:position+length]}]{after}..."


def verify_candidate(candidate: str, context: str, model: str) -> bool:
    """Ask LLM whether the candidate is a place name in context."""
    prompt = VERIFY_PROMPT.format(context=context, candidate=candidate)
    response = ollama.generate(model=model, prompt=prompt, options={"temperature": 0})
    answer = response["response"].strip().lower()
    return answer.startswith("yes")


def main():
    parser = argparse.ArgumentParser(description="Iteration 2: co-occurrence guided extraction")
    parser.add_argument("--input", required=True, help="Folder with original OCR page JSON files")
    parser.add_argument("--iter1", required=True, help="Folder with Iteration 1 output")
    parser.add_argument("--output", required=True, help="Output folder for Iteration 2 results")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument("--limit", type=int, default=None, help="Max pages to process")
    args = parser.parse_args()

    input_dir = Path(args.input)
    iter1_dir = Path(args.iter1)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load Iteration 1 results
    page_toponyms: dict[str, list[str]] = json.loads(
        (iter1_dir / "page_toponyms.json").read_text(encoding="utf-8")
    )
    cooccurrence: dict[str, dict[str, int]] = json.loads(
        (iter1_dir / "cooccurrence_graph.json").read_text(encoding="utf-8")
    )

    # Only process pages that had at least one toponym in Iteration 1
    pages_to_process = {
        page_id: toponyms
        for page_id, toponyms in page_toponyms.items()
        if toponyms
    }

    if args.limit:
        pages_to_process = dict(list(pages_to_process.items())[:args.limit])

    print(f"Re-processing {len(pages_to_process)} pages that had Iteration 1 results...")

    # Only newly confirmed toponyms per page (not a copy of iter1)
    updated_page_toponyms: dict[str, list[str]] = {}
    updated_cooccurrence: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t1, neighbors in cooccurrence.items():
        for t2, count in neighbors.items():
            updated_cooccurrence[t1][t2] = count

    log_path = output_dir / "log.jsonl"
    total_recovered = 0

    with open(log_path, "w", encoding="utf-8") as log_file:
        for i, (page_id, found_toponyms) in enumerate(pages_to_process.items()):

            # Load original page text
            page_file = input_dir / f"{page_id}.json"
            if not page_file.exists():
                # Try without custom_id suffix
                matches = list(input_dir.glob(f"*{page_id}*.json"))
                if not matches:
                    continue
                page_file = matches[0]

            page = json.loads(page_file.read_text(encoding="utf-8"))
            text = page.get("body_text", "").strip()
            if not text:
                continue

            # Step 2: co-occurrence prediction
            predicted = set()
            for toponym in found_toponyms:
                neighbors = cooccurrence.get(toponym, {})
                predicted.update(neighbors.keys())
            predicted -= set(found_toponyms)  # exclude already found ones

            if not predicted:
                continue

            # Steps 3+4: fuzzy search + LLM verification
            newly_confirmed = []
            for predicted_toponym in predicted:
                variants = expand_variants(predicted_toponym)
                found = False
                for variant in variants:
                    candidates = fuzzy_search(text, variant)
                    for candidate in candidates:
                        context = get_context(text, candidate["position"], len(candidate["text"]))
                        confirmed = verify_candidate(candidate["text"], context, args.model)
                        if confirmed:
                            newly_confirmed.append(predicted_toponym)  # store original node: not the variant/candidate ?
                            found = True
                            break
                    if found:
                        break

            # Step 5: update DB
            if newly_confirmed:
                # Deduplicate: drop candidates already in iter1 or seen earlier this page
                seen = {strip_punctuation(t).lower() for t in found_toponyms}
                deduped = []
                for t in newly_confirmed:
                    key = t.lower()
                    if key not in seen:
                        seen.add(key)
                        deduped.append(t)
                newly_confirmed = deduped

            if newly_confirmed:
                all_toponyms = found_toponyms + newly_confirmed
                updated_page_toponyms[page_id] = newly_confirmed  # only new ones
                for j, t1 in enumerate(newly_confirmed):
                    for t2 in all_toponyms[j + 1:]:
                        if t1 != t2:
                            updated_cooccurrence[t1][t2] += 1
                            updated_cooccurrence[t2][t1] += 1
                total_recovered += len(newly_confirmed)

            log_entry = {
                "page_id": page_id,
                "iter1_toponyms": found_toponyms,
                "predicted": list(predicted),
                "newly_confirmed": newly_confirmed,
            }
            log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

            status = f"+{len(newly_confirmed)} new" if newly_confirmed else "no change"
            print(f"  [{i+1}/{len(pages_to_process)}] {page_id}: {status} "
                  f"({len(predicted)} predicted, {len(newly_confirmed)} confirmed)")

    # Save updated results
    with open(output_dir / "page_toponyms.json", "w", encoding="utf-8") as f:
        json.dump(updated_page_toponyms, f, ensure_ascii=False, indent=2)

    with open(output_dir / "cooccurrence_graph.json", "w", encoding="utf-8") as f:
        json.dump(updated_cooccurrence, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {total_recovered} new toponyms recovered across {len(pages_to_process)} pages.")
    print(f"Results saved to {output_dir}/")


if __name__ == "__main__":
    main()
