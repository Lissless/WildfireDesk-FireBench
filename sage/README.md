# Sage

Sage is a civic helpdesk for wildfire recovery. It answers questions using curated civic and recovery documents (retrieval-augmented generation, or RAG), and can add local news through Ivy. You can use it in a browser or from the command line.

## Setup

Run these from the repository root, after the first-time setup in the [root README](../README.md):

```bash
source .venv/bin/activate
pip install -r sage/requirements.txt
cd sage
cp .env.example .env     # then fill in LLMPROXY_API_KEY and LLMPROXY_ENDPOINT
```

Everything below assumes you are in the `sage/` folder.

## Run the web app

```bash
python app.py
```

Open http://localhost:5000. To use another port, run `PORT=5001 python app.py`.

Before the page is served, the app uploads the resource documents to the LLM proxy. Expect startup to take a few minutes. See [Startup uploads](#startup-uploads).

## Run the command-line chatbot

```bash
python wildfire_desk.py
```

Type a question at the prompt and type `quit` to exit. Each session writes a `log-<timestamp>.txt` file to this folder.

## Folder map

| Path | What it is |
| --- | --- |
| `app.py` | Flask web app. Routes: `/` (page), `/intro` (opening message), `/chat` (answers). |
| `wildfire_desk.py` | The `Sage` class: prompting, RAG, citations, and follow-up questions. Also the command-line entry point. |
| `ivy_crawl.py` | Ivy: finds local news for the selected state and community. |
| `templates/`, `static/` | The web page, its stylesheet, and its images. Flask expects these names. |
| `resources/sage-instructions/` | Sage's instruction files: tone, interaction, formatting, drafting, guardrails, introduction, and privacy. Sage fails to start if any are missing. |
| `resources/democracy-chatbot-resources/` | RAG documents on organizing, meetings, roles, and management. Uploaded to the proxy at startup. |
| `resources/wildfire-resources/` | RAG documents on wildfire recovery, such as FEMA, insurance, and mitigation guides. Uploaded at startup. |
| `resources/ivy/state-local-news-outlets/` | One file per state listing local news outlets. Read by Ivy. |
| `resources/ivy/web-crawl-data/` | Cached crawl results from Ivy. Generated while the app runs. Mostly git-ignored. |
| `data-prep/` | Scripts and source files used to build the resource files, plus `healthy-democracy-states/`: per-state lists of civic organizations built from the Healthy Democracy links page. Nothing in the app reads these. To rebuild, run `python categorize.py` or `python local-news.py` from inside `data-prep/`. Each writes to a new `states_output/` folder. |

## Startup uploads

At startup, the app uploads every file in the two RAG folders to the LLM proxy, one at a time. Each success line shows the file name:

```
Upload Status: success, Filename: COCO-2024-Mitigation-Guide.pdf
```

- **Count:** 41 files today (32 in the democracy folder, 9 in the wildfire folder).
- **Why it's slow:** the app waits 3 seconds after each file (`upload_to_sage()` in `wildfire_desk.py`), so the uploads alone take about two minutes. The proxy also has to process each file.
- **Why it repeats:** nothing records which files were already uploaded, so every start sends them all again. The proxy keeps one copy of each file, so re-uploading wastes time but doesn't create duplicates. A new upload takes about 20 seconds to become searchable.
- **Failures are reported:** a failed file prints a `WARNING: upload failed for <name>` line as it happens. The other files keep uploading. When loading finishes, the console lists every file that failed. The app still starts, so answers can be missing that material. Check the console before you rely on the answers.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `LLMProxy configuration error: Missing LLMPROXY_ENDPOINT or LLMPROXY_API_KEY` | `sage/.env` is missing, or you ran the command from a different folder |
| `RuntimeError: Failed to set up Sage` | An instruction file in `resources/sage-instructions/` is missing. Upload failures do not cause this error. |
| `WARNING: upload failed for <name>` | The proxy rejected that document. The text after the name gives the reason. |
| `HTTP 401` or `HTTP 403` in answers | The API key is wrong, expired, or pasted with extra characters |
| `Address already in use` | Port 5000 is taken. Use `PORT=5001 python app.py`. |

## Known issues

- Startup uploads repeat on every run. See above.
- **The page is not built for phones.** On a phone-width screen, the settings panel takes most of the width and squeezes the chat into a narrow column. Checked on 2026-10-31 at 375×812.
- **The wildfire documents were missing from the live store and have been re-uploaded.** Before 2026-10-31, session `sage_rag2` held only the organizing documents. On 2026-10-31 all 9 PDFs in `resources/wildfire-resources/` were uploaded again, and each one was confirmed searchable with a targeted question. If wildfire answers ever stop citing these guides, re-check the store first.
- **What the proxy does, checked on 2026-10-31:**
  - Uploaded documents stay in the store between app restarts.
  - Re-uploading the same file does not create a duplicate.
  - An upload returns `success` within about 1.5 seconds, but the document only becomes searchable after about 20 seconds.
  - `retrieve` returns a list of `{doc_id, doc_summary, chunks}`, and an empty list for an unknown session. If the request itself fails, Sage now prints a warning and answers without documents instead of crashing.
- **`sage_rag_k = 5` counts passages, not documents.** Each answer gets the 5 best-matching passages, which usually come from 2 or 3 documents. For example, "How can a community reduce its wildfire risk?" gets 5 passages from the CWPP leaders guide and the Northeast/Midwest preparedness guide. Lowering `sage_rag_t` (0.4) does not change that result. Raise `sage_rag_k` if answers need more sources.
