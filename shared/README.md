# shared

Code that both Sage and CivicBench import.

| Path | What it is |
| --- | --- |
| `llmproxy/` | The LLM proxy client. `LLMProxy` sends `generate`, `retrieve`, and `upload_file` requests to the endpoint in your `.env`. It retries on network errors and on HTTP 429 and 5xx responses. |
| `civic_chatbot.py` | `CivicChatbot`, the base class for any chatbot. Sage, the raw baseline bot, and Orchid all inherit from it. |

## No install needed

You don't install this folder. Each Sage and CivicBench file that uses it adds `shared/` to Python's import path at the top of the file. Keep this folder next to `sage/` and `civicbench/`.

## Notes

- `LLMProxy` reads its settings from a `.env` file in the folder you run from, not from this folder. See the root README.
- Changing `civic_chatbot.py` affects both projects.
