# Folder Overview: `/ocr`

## Summary

This folder contains 74,785 JSON files — OCR output from a large-scale digitization project processing historical Chinese documents (primarily from the Dunhuang and Gaochang collections).

---

## File Types

### 1. Normal Page OCR Files (~72,591 files)

- **Naming pattern:** `<document-id>_page<NNNN>.json`
- **Example:** `E-222_02-01-001--V-1_page0008.json`
- Each file represents one scanned page of a document and contains:
  - `custom_id` — unique page identifier
  - `page` — page number
  - `language` — detected language (`unknown`, `en`, `fr`, `ru`)
  - `orientation` — page orientation (e.g. `normal`)
  - `body_text` — the OCR-extracted text (mainly Classical Chinese)
  - `captions`, `footnotes`, `headers` — structured text regions
  - `parse_error` — boolean flag for parsing failures

### 2. Retry Error Files (~2,194 files)

- **Naming pattern:** `<document-id>_page<NNNN>_retry.error.json`
- These represent pages where the OCR API call was retried but ultimately failed
- Common error: `"Output blocked by content filtering policy"` from the upstream API

---

## Documents

- 245 unique documents (versioned, e.g. `--V-1`, `--V-2`, etc.)
- Document ID prefixes suggest different collection series: `E-`, `I-`, `II-`, `III-`, `VIII-`, `X-`, `Y-`
- Page counts range from a few pages to nearly 1,000 (largest: `II-3-B-75--V-1` with 979 pages)

---

## Content

- Predominantly Classical Chinese text (70,397 pages labeled `unknown` language — typical for classical Chinese OCR)
- Some pages in English (2,041), French (149), Russian (4) — likely introductions or annotations in scholarly editions
- The content includes historical documents from Dunhuang (敦煌遺書) and Gaochang (高昌磚集) — important archaeological text corpora

---

## In Short

This is a large OCR output dataset for digitized historical East Asian manuscripts and scholarly books, likely produced by an AI OCR pipeline (given the batch API format with `custom_id` fields and content filtering errors). Each file is a single page's structured text extraction result.

---

# Week 1 Plan (2026-04-21): Iteration 1 Prototype

Goal: get the full Iteration 1 pipeline working end-to-end on a small subset. No co-occurrence logic yet — just validate the data flow.

## Day 1 — Setup

- Install Ollama and pull `qwen3:8b` (used `qwen2.5: 7b` because it's smaller and faster on 16GB RAM)
- Pick a small subset from the OCR folder: ~2–3 short English documents + 1 short Chinese document (~50 pages total)
- Verify you can query the model from Python

## Day 2–3 — Write the Iteration 1 script

A simple Python script that:
1. Reads a page JSON file
2. Sends `body_text` to Qwen3:8b with a zero-shot prompt (extract all place names)
3. Parses the response into a list of toponyms
4. Saves output: `{page_id → [toponyms]}` and `{toponym → [page_ids]}`

## Day 4–5 — Run and manually check

- Run the script on the ~50-page subset
- Manually inspect ~20–30 pages of output
- Note what toponyms are being missed — this is the core observation that motivates the co-occurrence method

## Trial Findings (2026-04-21, 50 pages of E-222_02-01-001--V-1)

### Correct extractions
- **吐魯番** (Turfan) and **高昌** (Gaochang) correctly extracted across multiple pages
- **交河城** (Jiaohe City), **雅爾崖** (Yarkhoto) also correctly identified
- OCR spelling variation already visible: **吐魯蕃雅爾崖** vs **吐魯番雅爾崖** vs **叶魯番雅爾古墳** — same place, different spellings across pages

### Issues identified

**1. Non-determinism (fixed)**
- Without `temperature=0`, the model gave different outputs for the same page on different runs
- Fixed by setting `temperature=0` in all Ollama calls

**2. False positives on tombstone TOC pages (pages 11, 18)**
- Pages listing tomb epitaphs (墓表) in the format `PersonName + 墓表` caused the model to extract personal names as toponyms
- Partially fixed by adding explicit exclusions to the prompt: "Do NOT include personal names, dates, official titles, or tomb epitaph titles"

**3. Ambiguity: 高昌 as place vs. era name**
- 高昌 refers to both the Gaochang region (toponym ✓) and the Gaochang Kingdom era (temporal marker ✗)
- Zero-shot extraction cannot reliably distinguish the two without surrounding context
- Noted as a domain-specific challenge for historical Chinese NER

**4. Tombstone epitaph format (page 25)**
- Classical Chinese tomb epitaphs mix real toponyms (吐魯番, 雅爾崖) with calendar dates (章和七年, 乙亥), personal names, and tomb titles in a dense, formulaic format
- Model extracts dates and names as false positives in this format
- This is the dominant text type in E-222 (高昌磚集 = brick epitaph collection), so Iteration 1 precision is inherently limited for this document
- Co-occurrence mechanism in later iterations should help: real toponyms recur across pages, dates do not

**5. Generic directional terms**
- 西北 (Northwest) extracted from "二西北科學考查圖" — borderline case
- In Silk Road studies 西北 functions as a regional label, but excluded as too generic for now

### Language detection note
- The `language` field in the OCR JSON is unreliable (most pages tagged `unknown` even when text is Chinese or English)
- Language detection is done from `body_text` using `lingua`, ignoring the JSON field

---

## Out of scope this week

- Fuzzy matching and candidate generation
- Co-occurrence prediction (Iteration 2+)
- vLLM or GPU server
- Processing the full corpus

## Stack

- Local inference: Ollama + `qwen3:8b` (fits in 16 GB, M1 Pro)
- Later (GPU server): vLLM + Qwen3-72B — prompts developed this week should transfer cleanly
