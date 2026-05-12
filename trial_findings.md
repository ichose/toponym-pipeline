# Trial Findings: Iteration 1 Zero-shot Extraction

## III-5-C-22--V-1 (Sino-Iranica, English)

| Page | Finding |
|------|---------|
| 7 | ✗ Iran and Chicago missed — title page format (book cover). "Iran" embedded in compound word "SINO-IRANICA" not decomposed. Good motivating example for Iteration 2 |
| 11 | ✗ Generic/regional terms not extracted (Asia, West, East, Central Asia, Eastern Asia) — consider including specific multi-word regional terms (e.g. Central Asia, Chinese Turkestan) but excluding bare directional terms (Asia, East, West) |
| 11 | ✗ "France" missed — appears in "gave his life for France" (WWI reference). Model likely treated it as idiomatic/metaphorical rather than a place name. Recall failure |
| 13 | Philological discussion about name variants — three cases: (1) ✓ should extract: Merw/Mouru/Muru (same city, modern Merv), Mu-lu 木鹿, An-si/Parthia; (2) ✗ should NOT extract: asterisked reconstructions (*Muk-luk, *Bux-rux) — hypothetical phonetic forms, never real place names; (3) ✗ Avesta — religious text, not a place. Model cannot distinguish toponyms being used vs. toponyms being discussed |
| 14 | ✗ China and Persia missed — buried in a long methodological/linguistic passage, low toponym density caused the model to miss them |
| 15 | ✗ "Chinese" extracted — adjective/demonym, not a place name. Country names and adjectival forms (Chinese, Iranian, Persian) should be excluded |
| 16 | ✗ "Han" extracted — dynasty name, not a toponym. ✗ "Central-Asiatic", "American" extracted — adjectives, not place names. Confirms systematic issue: model conflates adjectives and dynasty names with toponyms |
| 17 | ✗ "China" missed — appears once in dense scholarly argumentation. Confirms pattern: model fails to extract toponyms when toponym density is very low |
| 20 | ✗ Vienna, Baku, India, Central Asia all missed — page is dense pharmacological/bibliographical text with toponyms scattered sparsely. Same low-density recall failure pattern |

---

## Conclusion

### What to exclude from extraction (prompt fix needed)

1. **Adjectives and demonyms** — Chinese, Iranian, Persian, Central-Asiatic, American etc. are not place names and should be explicitly excluded in the prompt
2. **Dynasty names** — Han, Tang, Song etc. are temporal markers, not toponyms
3. **Generic orientation terms** — East, West, Orient, Asia alone are too vague to be useful
4. **Nation names** (design decision) — China, Persia, India, France are technically toponyms but excluded by design: they are too generic, add noise to the co-occurrence graph as high-frequency hubs, and are not the specific Silk Road site-level toponyms this research targets (e.g. Merw, Turfan, Sogdiana, Yarkhoto). Critically, if nation names leak into the co-occurrence graph from Iteration 1 (due to imperfect model compliance), they propagate into Iteration 2 predictions and get confirmed — amplifying the noise across both iterations. A clean Iteration 1 is essential.

### Recurring recall failure patterns

1. **Low toponym density pages** — when toponyms are sparse in dense scholarly/argumentative text, the model returns nothing
2. **Title and cover pages** — bibliographic format causes the model to be overly conservative

### Prompt update (applied to extract_toponyms.py)

**Removed from include list:**
- "countries" — nation names excluded by design (see below)

**Added to exclude list:**
- Country/nation names (China, Persia, France, India) — too generic, dominate co-occurrence graph as noisy high-frequency hubs, not the site-level toponyms this research targets
- Adjectives and demonyms (Chinese, Iranian, Persian) — not place names
- Dynasty names (Han, Tang, Song) — temporal markers, not geographical
- Generic orientation terms (East, West, Orient, Asia, Central Asia) — too vague
- Hypothetical reconstructed forms marked with * (e.g. *Muk-luk) — scholarly phonetic guesses, never attested as real place names; mixing them with real toponyms would be misleading. Attested variants (Merw, Mouru, Muru) should still be extracted
- Religious texts (Avesta) — not a place

**Kept in include list:**
- Ancient kingdoms (Sogdiana, Parthia, Bactria, Gaochang) — these refer to real geographical territories on the Silk Road, not just political entities. They are exactly the site-level toponyms this research targets

---

### Additional findings (from V1 vs V2 comparison)

| Page | Finding |
|------|---------|
| 25 | ✗ V1 hallucinated Gaochang, Dunhuang, Loulan — none of these appear in the actual text. Confirms that even with temperature=0 the model can invent toponyms not present in the source. V2 is more correct here |
| 25 | ✗ V2 still extracts Hu and Giaṅ — ethnic/tribal group names, not place names. Need to add ethnic/tribal names to the exclusion list |

---

### What works well
- Specific historical site names extracted consistently when toponym density is high (Fergana, Sogdiana, Bactria, Merw, Turfan)
- OCR spelling variation already visible across pages — motivates fuzzy matching in Iteration 2
- Co-occurrence graph meaningful after 50 pages: Iran ↔ Fergana ↔ Sogdiana ↔ Bactria

---

## Iteration 2 Design

### Goal
Recover toponyms missed by Iteration 1 by using co-occurrence predictions as hints, fuzzy search to locate candidates, and LLM verification to confirm them in context.

### Input
- `page_toponyms.json` — Iteration 1 results
- `cooccurrence_graph.json` — co-occurrence DB built from all 425 English pages
- Original page JSON files

### Pipeline (per page)

**Step 1 — Select pages to reprocess**
Only reprocess pages where Iteration 1 found at least one toponym. Pages with no extractions have no entry point into the co-occurrence graph.

**Step 2 — Co-occurrence prediction**
For each toponym already found on the page, look up all its neighbors in the co-occurrence graph. Use all neighbors (no weight filtering at this stage — weighting is a later refinement). This gives a predicted list of toponyms likely to appear on the page.

**Step 3 — Fuzzy search**
For each predicted toponym not already found on the page, search the raw `body_text` for approximate matches using edit distance with a length-based threshold:
- strings < 5 chars: edit distance ≤ 1
- strings 5–8 chars: edit distance ≤ 2
- strings > 8 chars: edit distance ≤ 3

**Step 4 — LLM verification**
For each fuzzy match candidate, present the candidate string with ~100–200 characters of surrounding context (roughly one sentence on each side) to the LLM and ask: *"is this string a place name in this context?"* This filters out false matches — e.g. "IRANICA" fuzzy-matches "Iran" but is a book title, not a place; the LLM should reject it given the context.

**Step 5 — Update DB**
Add confirmed new toponyms to `page_toponyms.json` and update `cooccurrence_graph.json` with new co-occurrence pairs.

### Deferred refinements
- Weight co-occurrence neighbors by frequency (prioritize top-weighted hints)
- Cross-book and cross-language co-occurrence

---

## Test Outcomes

### Iteration 1

Run on 425 English pages from III-5-C-22--V-1 with V2 prompt + qwen2.5:7b.

| Metric | V1 (original prompt) | V2 (refined prompt) |
|--------|---------------------|---------------------|
| Total extractions | 274 | 118 |
| Unique toponyms | ~200+ | 679 (after full run) |
| Hallucinations | Confirmed (Gaochang, Dunhuang, Loulan on p.25) | Reduced |
| False positives | Adjectives, dynasty names, ethnic names | Adjectives and ethnic names still leak through |
| Low-density recall | Consistently fails | Consistently fails |

Key findings:
- Even at temperature=0, 7B model invents toponyms not present in the source text (V1 hallucinated Gaochang/Dunhuang/Loulan on page 25)
- V2 prompt better at precision but recall drops — country names and low-density pages still missed
- Diminishing returns on prompt tuning with 7B model; GPT/Gemini perform substantially better on the same pages

---

### Iteration 2

Run on 50 pages (pages with ≥1 Iteration 1 toponym) using the full 425-page co-occurrence graph. After code fixes (deduplication, punctuation stripping, updated verification prompt): **68 new toponyms recovered across 33 pages**.

**Quality review by category:**

| Category | Examples | Verdict |
|----------|----------|---------|
| Valid recoveries | Turkestan (p.28), Egypt (p.46), Parthia (p.38), Kiaṅ-si (p.22), Nan-hai (p.26), Po-se (p.26), Peking (p.55), T'ai-yüan (p.62), Pāmir (p.87), Kashmir (p.65), Silla (p.101), Kirmān (p.81) | ~25 correct |
| Adjectives/demonyms | Sasanian (p.35), Malayan (p.16), Ferganians (p.38) | False positive — 7B LLM limitation |
| Nation names | China, Persia, India (multiple pages) | Excluded by design — leaked from Iteration 1 graph |
| Subset of iter1 toponym | "Tibet" when "Central Tibet" already in iter1; "Silla" when "Silla Kingdom" already in iter1 | Redundant — dedup only checks exact match, not substring |
| Generic terms | "Asia", "northern China", "Central Asia" | Too vague |
| Hypothetical form | "*hu" (p.27) — fuzzy match of "Hu" found asterisked reconstruction in text | False positive — should reject * prefix |

**Issues found and status:**

1. **Punctuation attached to candidates** — `"Persia,"`, `"Tibet.³"`, `"Šan-si\nProvince"` — **fixed**: `strip_punctuation()` applied before storing
2. **Duplicate confirmations within a page** — same toponym confirmed multiple times — **fixed**: deduplication added
3. **LLM verification too permissive** — adjectives, demonyms, dynasty names confirmed despite updated prompt — **7B model limitation**, expect improvement with Qwen3-72B
4. **Nation names in co-occurrence graph** — leaked from Iteration 1 imperfect exclusions → amplified by Iteration 2 predictions — **root fix: cleaner Iteration 1 with larger model**
5. **Bracketed forms stored as single node** — e.g. `"An-si (Parthia)"` in iter1 graph means fuzzy search looks for 3-word ngram; `"Parthia"` appearing alone on another page won't be found — **to fix**: expand bracketed forms into separate nodes at graph-build time, or split predicted toponyms before fuzzy search
6. **Subset/superset redundancy** — `"Tibet"` recovered when `"Central Tibet"` already known; `"Silla"` when `"Silla Kingdom"` already known — dedup only checks exact string match, not semantic containment — **to fix**: check if candidate is a substring/superset of any iter1 toponym before confirming
7. **Hypothetical forms (`*`) not pre-filtered** — fuzzy match finds `"*hu"` from predicted `"Hu"` — **to fix**: skip any candidate whose text starts with `*` before calling LLM
8. **Footnotes not included** — toponyms in footnotes (e.g. `Kashmir` in footnote 1, `Asia Minor` in footnote 5) are missed — **deferred design decision**

**Overall assessment:**
The pipeline direction is correct — co-occurrence prediction + fuzzy search does recover real missed toponyms. The main bottleneck is Iteration 1 quality: noise that leaks into the co-occurrence graph cascades and amplifies in Iteration 2. Re-running with Qwen3-72B on the server is the highest-priority next step.

---

### Iteration 1 V3 — Context-based filter loop (professor feedback)

**Pipeline change:** Based on professor feedback, the prompt-based exclusion rules ("Do NOT include adjectives, dynasty names...") were removed. Instead, a post-extraction filter loop was added: for each LLM-extracted candidate, the script locates it in the page text, extracts ±150 characters of surrounding context, and asks the LLM "Is the bracketed term used as a place name in this text?" (yes/no). Only confirmed candidates enter the DB. Hallucinations (candidates not found in source text) are automatically rejected.

Run on 425 English pages from III-5-C-22--V-1 with V3 prompt + filter loop + qwen2.5:7b.

| Metric | V2 (refined prompt) | V3 (context filter loop) |
|--------|---------------------|--------------------------|
| Pages with toponyms | 194 | 344 |
| Total extractions | 1103 | 2080 |
| Unique toponyms | 697 | 1038 |
| Confirmed by filter | — | 2080 |
| Rejected by filter | — | 1129 |

**Gains vs V2 (546 new unique toponyms):** Many legitimate toponyms newly captured (Abu Dulaf, Aleppo, Amur, Astrakhan, Baku, Arabia felix, Aegean Islands, etc.) due to the broader extraction prompt. Pages with toponyms increased from 194 to 344.

**Losses vs V2:** 205 unique toponyms from V2 not present in V3, split into two groups:
- **Rejected by filter (incorrectly):** Real toponyms like `Damascus`, `Congo`, `Calabria`, `Chinese Turkestan` were wrongly rejected by the 7B verification LLM in context — false negatives introduced by the filter
- **Not extracted at all (93):** Real Silk Road toponyms like `Bulayiq`, `Lob-nor region`, `Bost`, `Ai-lao` not picked up by the broader prompt either — same low-density recall failure as before

**New false positive patterns observed:**
1. **Dense botanical/pharmacological pages (p.19)** — plant names (`hemp`, `cardamom`, `fig`, `grape`) extracted and confirmed by the 7B verification LLM. The page is a Persian botanical classification text; the LLM fails to distinguish plant names from place names in this register.
2. **Zoroastrian deity names (p.20)** — names like `Vād`, `Dīn-pavan-Dīn`, `Āçtād`, `Zamyād` (Persian angel names associated with plants) confirmed as toponyms. Both extraction and verification LLM fail on this text type.

**What the filter correctly rejects:** Adjectives/demonyms (`Sasanian`, `Iranian`, `Arabians`, `Javians`), botanical Latin names (`Canarium commune`), context-dependent rejections (e.g. `Iran` on p.12 rejected because it appeared inside "Sino-Iranian").

**Root cause of remaining errors:** The 7B model is insufficiently reliable for the verification step. Both directions of error — confirming non-toponyms and rejecting real toponyms — are attributable to the 7B model's limited judgment. The pipeline architecture (broad extraction + context-based filter) is correct; the bottleneck is model capacity.

**Expected improvement with Qwen3-72B:** Both false positive patterns (botanical pages, deity names) and false negatives (real toponyms rejected) should improve substantially with the larger model.
