# shared

Code that both Sage and CivicBench import.

| Path | What it is |
| --- | --- |
| `llmproxy/` | The LLM proxy client. `LLMProxy` sends `generate`, `retrieve`, and `upload_file` requests to the endpoint in your `.env`. It retries on network errors and HTTP 429 and 5xx. |
| `civic_chatbot.py` | `CivicChatbot`, the base class for any chatbot. Sage, the raw baseline bot, and Orchid all inherit from it. |
| `pyproject.toml` | Lets the other projects install this folder as a package. |

## Install

From the repository root, with the venv active:

```bash
pip install -e ./shared
```

The `-e` flag installs it in editable mode, so edits here take effect right away. pip downloads `setuptools` during the install, because it is the build tool this package uses.

## Notes

- `LLMProxy` reads its settings from a `.env` file in the folder you run from, not from this folder. See the root README.
- Changing `civic_chatbot.py` affects both projects.
