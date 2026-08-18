# RepoLens five-minute demo

## Before the demo

1. Start the backend and frontend using the README commands.
2. Confirm `/api/health` returns success.
3. Use a small ZIP so CPU indexing finishes within the allotted time. Make sure it contains at least one Python function/class and one Markdown file.
4. Keep a previously indexed fallback project available in case the model must download or the demo machine is slower than expected.

## 0:00–1:15 — Upload and indexing

- Open `http://127.0.0.1:5173`.
- Select the ZIP and click **Projeyi yükle**.
- Point out the selected-project status, file count, chunk count, and automatic status polling.
- Explain that uploaded files are treated as untrusted data and never executed.

## 1:15–2:15 — Architecture question

Ask:

> How does this project retrieve source code before calling the chat model?

Show that the response is generated locally and that source cards accompany the answer.

## 2:15–3:15 — Function-location question

Ask a question tied to the demo fixture, for example:

> Where is `register_user` implemented?

Point out the file path, symbol, line range, and relevance-ordered citations.

## 3:15–4:00 — Unsupported question

Ask:

> Where is spacecraft orbital thrust calibration implemented?

Expected result: `insufficient_context`, no fabricated source, and no chat-model call.

## 4:00–4:40 — Inspect a citation

- Click the strongest source card.
- Show the stored snippet and exact metadata in the source modal.
- Explain that citation objects come from SQLite metadata owned by the backend, not text invented by the model.

## 4:40–5:00 — Close

- Reiterate that archives, embeddings, database records, and inference stay local after models are cached.
- State the MVP boundary: Python/Markdown, small repositories, full re-indexing, and localhost use.
- Mention the next priorities: incremental indexing, more parsers, import graph signals, multi-project search, and packaging.
