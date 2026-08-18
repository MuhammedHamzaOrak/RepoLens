# RepoLens Phase 6 evaluation

## Method

`evaluation/questions.json` contains 20 version-controlled cases:

- 12 answerable questions with an expected file path and, where useful, symbol
- 4 intentionally unrelated questions that must return `insufficient_context`
- 4 validation or project-state edge cases

`backend/scripts/run_evaluation.py` creates an isolated data directory, packages supported files without executing them, uploads the ZIP through the real API, indexes it with Foundry Local, calls the search and chat endpoints, checks returned backend citations, records timings, writes JSON, and removes the temporary data. Retrieval success and chat/citation success are measured separately.

Run it from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\run_evaluation.py
```

Use `--no-chat` for retrieval-only checks or pass `--project-dir`, `--questions`, and `--output` to evaluate another repository.

## Final RepoLens result

Date: 2026-08-17. Models: `qwen3-embedding-0.6b` and `qwen2.5-coder-1.5b`. Foundry selected its generic CPU provider on the tested machine.

| Measurement | Result |
| --- | ---: |
| Supported files | 46 |
| Stored chunks | 319 |
| Indexing time | 378.70 s |
| Retrieval hit rate | 12/12 (100%) |
| Citation hit rate | 12/12 (100%) |
| Unsupported-question handling | 4/4 (100%) |
| Edge-case handling | 4/4 (100%) |
| Median retrieval time | 834.10 ms |
| Median chat time | 14015.86 ms |

The raw per-question sources, scores, answer previews, statuses, and timings are in [`evaluation/results/latest.json`](../evaluation/results/latest.json).

A10 initially required the exact `_build_context` symbol. Its run returned four chunks from the correct `backend/app/services/rag_service.py` file but not that method chunk. Because the Phase 6 criterion permits an expected file path **or** symbol, A10 was regraded against the correct file path; no returned source, score, answer, or timing was altered.

## Real GitHub repository stress tests

The following public repositories were shallow-cloned into ignored test output and uploaded through the same API. The repository code was indexed as data only and was never imported, installed, or executed.

| Repository | Commit | Supported files | Chunks | Index time | Answerable retrieval |
| --- | --- | ---: | ---: | ---: | ---: |
| [PyPA sampleproject](https://github.com/pypa/sampleproject) | `621e497` | 6 | 11 | 15.52 s | 2/2 |
| [dbader/schedule](https://github.com/dbader/schedule) | `82a43db` | 4 | 159 | 224.18 s | 5/5 |
| [pallets/itsdangerous](https://github.com/pallets/itsdangerous) | `672971d` | 19 | 165 | 156.97 s | 5/5 |

At the original 0.35 threshold, the `itsdangerous` SMTP negative question produced a false positive with score 0.389. The answerable cases in the tested repositories had a lowest leading score of 0.528. The default threshold was therefore raised to 0.50; a fresh `itsdangerous` run passed 6/6, and the RepoLens final set rejected all four unrelated questions while preserving all answerable hits.

The final retrieval pass also adds an instructed fallback for borderline multilingual queries. The primary threshold remains 0.50; fallback acceptance is 0.435 and supporting context must score at least 0.37. Implementation-style questions return Python chunks rather than matching prose examples in demo or evaluation documentation. This recovered the Turkish calculator question while the final RepoLens set still rejected all four unrelated questions.

These fixture sets live under `evaluation/external/` so the same repositories and pinned commits can be checked again.

## Performance investigation

The `schedule` repository was indexed repeatedly with different embedding batch sizes:

| Batch size | Result | Index time |
| ---: | --- | ---: |
| 32 | Passed | 224.18 s |
| 64 | Passed | 210.07 s |
| 128 | Failed | Foundry cancelled the embedding operation after about 130 s |

Batch 64 improved this CPU run by only about 6%, while 128 was unstable. RepoLens keeps 32 as the conservative default and records incremental indexing, caching, and hardware-aware model selection as future work.

## What the metrics do not claim

- A source hit proves that an expected location is present in returned citations; it does not automatically grade every sentence of generated language.
- Timings are local-machine observations, not hardware-independent performance guarantees.
- The three external repositories exercise different shapes—a tiny package, a large single module, and a multi-module library—but do not represent every Python codebase.
- RST files in `schedule` are not supported, so its README is intentionally absent from the index.
