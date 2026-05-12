# Research Plan: Iterative Toponym Extraction from Historical Multilingual Corpora Using Corpus-Internal Co-occurrence Prediction

## 1. Background and Motivation

The Toyo Bunko (Oriental Library) holds approximately 70,000 pages of scholarly materials related to Silk Road expeditions, written in six languages: English, German, French, Russian, Chinese, and Japanese. These materials document explorations conducted by national expeditions from multiple countries during the late 19th and early 20th centuries. A digitization and OCR project using Claude's API is planned to convert these materials into machine-readable text.

The long-term research goal is to build a knowledge base that enables comparative analysis of how different national expeditions described the same places, artifacts, and events — revealing cultural, political, and epistemological differences across traditions. However, this comparative analysis requires a foundational step: the construction of a multilingual toponym (place name) database linking place name variants across languages.

This research addresses the challenge of that foundational step: **how to extract toponyms from historical multilingual materials with limited labeled data, no pre-existing complete entity database, and without relying on entity linking to external knowledge graphs**.

---

## 2. Research Problem

Standard named entity recognition (NER) approaches face several difficulties when applied to this corpus:

- **Low recall of LLMs in open-ended extraction**: LLMs tend to miss toponyms when the surrounding context is insufficient for confident judgment, even when the LLM has implicit knowledge of the toponym.
- **Incomplete seed dictionary**: An existing toponym list covers only a subset of the place names in the corpus and lacks multilingual coverage.
- **Unavailability of external knowledge graphs**: Approaches relying on entity linking to resources such as Wikidata or GeoNames presuppose that linking has already succeeded — a circular dependency that cannot be resolved at this stage.
- **OCR noise and orthographic variation**: Historical documents processed by OCR contain character-level errors and spelling variants that prevent simple string matching from reliably locating known toponyms.
- **Historical and transliteration variation**: The same place may be written differently across languages, time periods, and authors (e.g., *Loulan*, *Lou-lan*, *楼蘭*, *Лоулань*).

---

## 3. Core Research Question

**To what extent can corpus-internal co-occurrence patterns be used to predict toponyms likely to appear in a given passage, and how much does incorporating these predictions as few-shot hints into LLM prompts improve toponym recall — without relying on model retraining or external knowledge graphs?**

---

## 4. Proposed Method

### 4.1 Overview

The proposed method is an iterative bootstrapping framework for toponym extraction. It improves recall across iterations by using co-occurrence patterns learned from the corpus itself to generate toponym predictions, which are then embedded as few-shot hints in LLM prompts.

The key insight is that **the few-shot hints are not generic task examples, but document-specific predictions** derived from what the corpus has revealed so far. This distinguishes the approach from standard few-shot NER, which uses fixed demonstration examples, and from knowledge-graph-augmented NER, which requires prior entity linking.

### 4.2 Iterative Process

**Iteration 1 — Zero-shot extraction:**
Each page is processed by an LLM with a zero-shot prompt instructing it to extract toponyms. Extracted toponyms are stored in a growing toponym database (DB), along with their co-occurrence relationships (pairs or groups of toponyms appearing in the same passage or page).

**Iteration n — Co-occurrence-guided extraction:**
For each page not yet fully processed:

1. **Co-occurrence prediction**: Based on toponyms already confirmed in the DB that co-occur with toponyms found in this page, predict which additional toponyms are likely to appear.
2. **Candidate generation**: Use string search with fuzzy matching to locate candidate strings in the page text that correspond to predicted toponyms (including OCR variants).
3. **Ambiguity resolution by LLM**: Present the candidate strings to the LLM with their surrounding context. The LLM judges whether each candidate is a toponym in context, resolving ambiguity including OCR-induced variation.
4. **DB update**: Confirmed new toponyms and their co-occurrences are added to the DB, enriching the co-occurrence graph for subsequent iterations.

**Convergence**: The process terminates when no new toponyms are discovered in an iteration (i.e., the co-occurrence graph produces no new candidates that the LLM confirms).

### 4.3 Role of Each Component

| Component | Role |
|---|---|
| LLM (zero-shot) | Initial open-ended toponym extraction |
| Co-occurrence DB | Accumulates corpus-internal co-occurrence patterns across iterations |
| Co-occurrence prediction | Predicts toponyms likely to appear in a passage based on known co-occurrences |
| Fuzzy string search | Generates candidates for predicted toponyms, tolerating OCR variation |
| LLM (verification) | Resolves ambiguity; judges whether a candidate is a toponym in context |

### 4.4 Scope and Limitations

This method is designed to recover toponyms that **were missed due to insufficient local context**, not to discover toponyms that are entirely outside the LLM's knowledge. Toponyms that the LLM cannot recognize under any contextual conditions — due to extreme rarity, severe OCR corruption, or absence from training data — remain outside the recoverable set. This boundary will be analyzed as part of the research findings.

---

## 5. Technical Challenges

**Challenge 1: OCR variation and fuzzy matching**
Simple string search fails to locate toponyms distorted by OCR errors. Fuzzy matching (e.g., edit distance, character n-gram similarity) is needed to generate candidates. The threshold must be calibrated to balance recall (tolerant) and precision (strict). LLM-based verification is used to filter false positives.

**Challenge 2: Ambiguity resolution**
A candidate string located by fuzzy matching may or may not be a toponym in its specific context. LLM judgment is used to resolve this, leveraging contextual information that string matching cannot access.

**Challenge 3: Convergence behavior**
The iteration may converge prematurely if the co-occurrence graph becomes sparse — not because all toponyms have been found, but because no confirmed toponym co-occurs with unconfirmed ones. This represents a structural limitation of the method that will be characterized in the analysis.

**Challenge 4: Co-occurrence scope**
In this study, co-occurrence is defined within a single book or language. Extension to cross-book and cross-language co-occurrence is left as future work.

**Challenge 5: Chunk design and page boundary effects**
The granularity at which text is presented to the LLM significantly affects extraction quality. Chunks that are too long risk reduced attention to toponyms in the middle or latter portions of the text (the "lost in the middle" problem), while chunks that are too short deprive the LLM of the contextual signals needed to recognize toponyms confidently.

For this corpus, the page is adopted as the natural processing unit, since it aligns with the OCR output and avoids the implementation complexity of cross-page segment detection. However, this choice introduces a potential accuracy loss at page boundaries: expedition narratives frequently continue across pages, and a toponym appearing near the end of one page may lack the contextual support that would appear on the following page.

This limitation is partially mitigated by the iterative co-occurrence mechanism. Even if a toponym is missed at a page boundary in an early iteration, the co-occurrence DB accumulated from other pages may predict its presence in a later iteration and prompt targeted re-examination. Whether the co-occurrence mechanism effectively compensates for page-boundary context loss is treated as an empirical question and evaluated as a secondary analysis axis in this study.

---

## 6. Relationship to Prior Work

This work is positioned at the intersection of several research lines:

- **Bootstrapping NER**: Classical bootstrapping methods (e.g., Yarowsky 1995; Zhang et al. 2020) use seed patterns to iteratively expand entity recognition, but require model retraining at each step. The proposed method replaces retraining with prompt-based LLM inference, making it training-free.
- **Self-improving zero-shot NER** (Xie et al. 2024): Uses self-consistency on unlabeled corpora to build pseudo-labeled demonstrations for in-context learning. The proposed method differs in using corpus-internal co-occurrence prediction rather than self-annotated examples.
- **Few-shot NER with external knowledge** (e.g., KGPC): Uses domain knowledge graphs to generate augmented training examples. The proposed method requires no external knowledge graph, making it applicable to low-resource historical domains where entity linking has not yet been established.

The core novelty is the use of **corpus-internal co-occurrence as a dynamic, document-specific prediction mechanism for few-shot hint generation** — a combination not found in prior literature.

---

## 7. Application Context

The method is applied to Toyo Bunko Silk Road materials with the following characteristics:

- **Languages**: English, German, French, Russian, Chinese, Japanese
- **Domain**: Historical expedition records, late 19th–early 20th century
- **Seed data**: A partial toponym list (incomplete, limited multilingual coverage)
- **Evaluation**: Comparison against the existing toponym list to measure recall improvement across iterations; qualitative analysis of unrecovered toponyms

---

## 8. Model Selection and Inference Infrastructure

### 8.1 Hardware Environment

Two GPU configurations are available for this research:

- **Configuration A**: NVIDIA RTX 6000 Ada × 2 (48 GB GDDR6 each, 96 GB total)
- **Configuration B**: NVIDIA RTX PRO 6000 Blackwell × 1 (96 GB GDDR7)

Configuration B is preferred for single-GPU inference of large models due to higher memory bandwidth (1,792 GB/s vs. 864 GB/s combined for Ada) and Blackwell architecture optimizations.

### 8.2 Primary Model Candidate

**Qwen3 72B** (Alibaba, Apache 2.0) is the primary candidate for the following reasons:

- Explicit multilingual support across 29+ languages, including all six target languages (English, German, French, Russian, Chinese, Japanese)
- Strong performance on multilingual NER and text understanding tasks
- Fits within 96 GB VRAM under Q4 or Q8 quantization
- Permissive license compatible with research and potential open data release

Estimated inference speed on Configuration B with vLLM (Q4 quantization): approximately 30–50 tokens/second for single requests, yielding roughly 100–145 hours of processing time for 70,000 pages.

### 8.3 Inference Engine: vLLM over Ollama

**vLLM** is adopted as the primary inference engine rather than Ollama for the following reasons:

- Approximately 2× higher throughput for single-request inference on the same hardware
- PagedAttention memory management enables efficient KV cache utilization, particularly important for long-context page processing
- OpenAI-compatible API simplifies integration with the Python processing pipeline
- Better support for AWQ/GPTQ quantization formats, which preserve more quality than GGUF at equivalent memory usage

Ollama remains useful for rapid prototyping and model evaluation during development.

**Recommended launch command (Configuration B):**
```bash
vllm serve Qwen/Qwen3-72B-Instruct \
  --quantization awq \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.9
```

### 8.4 Fallback: Speed-Quality Tradeoff

If processing speed proves to be a bottleneck with Qwen3 72B, **Qwen3-30B-A3B** (MoE variant) is the primary fallback candidate. This model uses a Mixture-of-Experts architecture with only ~3B active parameters per token, achieving 3–4× higher throughput than the 72B dense model while maintaining performance comparable to Qwen2.5-72B on most benchmarks.

The decision between 72B and 30B-A3B will be made empirically after pilot experiments on sample pages from each of the six languages, evaluating the quality-speed tradeoff in the context of toponym extraction accuracy.

### 8.5 Context Length Comparison

The table below summarizes the context lengths of the primary candidate models:

| Model | Native context | With YaRN / extension |
|---|---|---|
| Qwen3 72B (2504) | 32,768 | 131,072 |
| Qwen3 30B-A3B (2504) | 32,768 | 131,072 |
| Qwen3 30B-A3B-Instruct-2507 | ~256,000 | ~1,000,000 |
| Gemma 3 27B | 128,000 | — |
| gpt-oss 120B | 131,072 | — |
| Mistral Large 3 | 128,000 | — |

For single-page processing with few-shot hints, all candidate models provide sufficient context. A typical prompt in this research consists of approximately 1,000 tokens of page text, 500 tokens of co-occurrence hint list, and 200 tokens of system instructions, totaling roughly 1,700–2,000 tokens — well within the native context of any candidate model.

Context length becomes a practical concern only if the co-occurrence hint list grows to thousands of toponyms in later iterations. In that case, dynamic RAG-style selection of the most relevant co-occurrence hints will be required to keep prompts within efficient operating range, regardless of the model's maximum context length.

One practical note on Qwen3 30B-A3B via Ollama: as of August 2025, `ollama run qwen3:30b-a3b` automatically pulls the 2507 thinking variant (`qwen3:30b-a3b-thinking-2507-q4_K_M`). Since thinking mode is unnecessary and wasteful for toponym extraction, non-thinking mode must be explicitly enabled when using this model:

```bash
# In Ollama
/set nothink

# In vLLM (Instruct-2507 variant)
vllm serve Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.9
```

### 8.6 Language Coverage Limitations

No single open-weight model currently provides uniformly strong coverage across all six target languages for historical text. In particular, Russian historical documents from the late 19th–early 20th century represent the most uncertain coverage across all candidate models. This limitation will be explicitly characterized in the evaluation by reporting per-language recall rates, and treated as a research finding rather than a failure of the method.

---

## 9. Expected Contributions


1. **Methodological**: A training-free, iterative toponym extraction framework that uses corpus-internal co-occurrence prediction as few-shot hints, applicable to historical low-resource multilingual corpora without external knowledge graphs.

2. **Empirical**: Analysis of the convergence behavior of the method, characterizing how recall improves across iterations and where the method reaches its limits. Secondary analysis examines whether the iterative co-occurrence mechanism compensates for context loss at page boundaries.

3. **Resource**: A multilingual toponym database for the Toyo Bunko Silk Road collection, serving as a foundation for subsequent comparative analysis of national expedition narratives.

---

## 10. Future Work

- Extension of co-occurrence scope to cross-book and cross-language patterns within the collection
- Investigation of finer-grained chunking strategies (e.g., paragraph or sentence level) and their effect on extraction quality, including handling of cross-chunk context
- Integration with cross-lingual entity linking using the extracted toponym database
- Comparative analysis of how different national expeditions described the same places (the long-term humanistic goal)
- Evaluation on standard NER benchmarks to assess generalizability beyond the historical domain
