# Toponym Pipeline

A two-iteration pipeline for extracting place names (toponyms) from OCR-processed historical Silk Road documents, using a local LLM and co-occurrence-guided recovery.

---

## Dataset

The `ocr/` folder contains ~74,785 JSON files — OCR output from a large-scale digitization project processing historical Chinese documents, primarily from the **Dunhuang** (敦煌遺書) and **Gaochang** (高昌磚集) collections.

Each page file (`<document-id>_page<NNNN>.json`) contains:
- `custom_id` — unique page identifier
- `body_text` — OCR-extracted text (mainly Classical Chinese; some English, French, Russian)
- `captions`, `footnotes`, `headers` — structured text regions
- `language`, `orientation`, `parse_error` — metadata fields

Files matching `*_retry.error.json` (~2,194 files) represent pages where the OCR API ultimately failed and are skipped.

The corpus spans 245 unique documents across collection series `E-`, `I-`, `II-`, `III-`, `VIII-`, `X-`, `Y-`, with page counts ranging from a few pages to ~979 pages per document.

---

## Pipeline

### Iteration 1 — Zero-shot extraction (`extract_toponyms.py`)

Runs a local LLM (via Ollama) over each page and extracts toponyms in two steps:

1. **Language detection** — `lingua` detects the language of `body_text`; pages with fewer than 15 characters or undetectable language are skipped.
2. **Zero-shot extraction** — the LLM is prompted to return a JSON array of all place names (cities, historical sites, ancient kingdoms, regions, rivers, deserts, etc.).
3. **Context-based filter** — each extracted candidate is located in the source text; ~150 characters of surrounding context are passed to the LLM for a yes/no verification: *"Is the bracketed term used as a place name in this text?"* Candidates not found in the source text (hallucinations) are automatically rejected.

**Output** (written to `--output` folder):
- `page_toponyms.json` — `{ page_id: [confirmed toponyms] }`
- `cooccurrence_graph.json` — `{ toponym: { toponym: co-occurrence count } }`
- `log.jsonl` — per-page log with confirmed and rejected candidates

**Usage:**
```
python3 extract_toponyms.py --input <ocr-folder> --output <output-folder> [--model qwen2.5:7b] [--limit N]
```

---

### Iteration 2 — Co-occurrence guided recovery (`check_cooccurrence.py`)

Re-processes pages where Iteration 1 found at least one toponym, using the co-occurrence graph as a hint to recover missed toponyms:

1. **Co-occurrence prediction** — for each toponym already found on a page, look up all its neighbors in the co-occurrence graph to produce a predicted set of toponyms likely to appear on that page.
2. **Fuzzy search** — for each predicted toponym not already found, search `body_text` for approximate matches using Levenshtein edit distance with a length-based threshold:
   - < 5 chars: distance ≤ 1
   - 5–8 chars: distance ≤ 2
   - > 8 chars: distance ≤ 3

   Compound or bracketed forms (e.g. `"An-si (Parthia)"`, `"Merw or Muru"`) are expanded into individual variants before searching.
3. **LLM verification** — fuzzy match candidates are verified with surrounding context, same as Iteration 1.
4. **DB update** — confirmed new toponyms are added to `page_toponyms.json` and the co-occurrence graph is updated with new co-occurrence pairs.

**Output** (written to `--output` folder):
- `page_toponyms.json` — newly confirmed toponyms per page (delta only, not a copy of Iteration 1)
- `cooccurrence_graph.json` — updated co-occurrence graph
- `log.jsonl` — per-page log with predicted and newly confirmed toponyms

**Usage:**
```
python3 check_cooccurrence.py --input <ocr-folder> --iter1 <iter1-output-folder> --output <output-folder> [--model qwen2.5:7b] [--limit N]
```

---

## Stack

- **Local inference:** [Ollama](https://ollama.com) + `qwen2.5:7b` (fits in 16 GB RAM, tested on M1 Pro)
- **Language detection:** [`lingua-language-detector`](https://github.com/pemistahl/lingua-py)
- **Fuzzy matching:** [`rapidfuzz`](https://github.com/maxbachmann/RapidFuzz)

## Dependencies

```
pip install ollama lingua-language-detector rapidfuzz
```

Ollama must be running locally with the target model pulled:
```
ollama pull qwen2.5:7b
```
