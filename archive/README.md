# archive

Files moved out of the main project because nothing in the code reads them, or because they are copies of files that now live elsewhere. Nothing here is used by the app or the benchmark.

These are kept until the team decides whether to delete them. Once you've confirmed the list, the folder can be removed.

| Path | Why it's here |
| --- | --- |
| `build/` | An old copy of the LLM proxy client. It has been replaced by `shared/llmproxy/`. |
| `sage-resources/categorize.py` | Differs from `sage/data-prep/categorize.py`. Which version is current is not known. |
| `sage-resources/Healthy-Democracy-Sample-Links.html` | Identical to the copy in `sage/data-prep/`. |
| `sage-resources/question-types.pdf` | Identical to the copy in `sage/data-prep/`. |
| `sage-resources/web-crawl-data/Bingham_News_Chronicle.jsonl` | Crawl data for one outlet. No code reads it. |
| `orchid-resources/orchid-tone-v1.txt` | An earlier version of `orchid-tone.txt`. |
| `orchid-resources/orchid-early-exit-example-1t.txt`, `orchid-early-exit-example-2t.txt`, `orchid-example-convo.txt` | Example conversations. No code reads them. |
| `eval-data/Expert Evaluation Tables.pdf` | Not referenced by any script. |
