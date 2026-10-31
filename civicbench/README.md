# CivicBench

CivicBench evaluates how well a civic AI system gives useful, accurate, and responsible guidance. It contains:

- **140 scenario questions** across 7 civic categories and 35 subcategories, each with a difficulty level.
- **A scoring rubric.** Several LLM judges score each response against the same rubric.
- **Orchid**, a simulated user that asks follow-up questions for up to five turns.
- **A baseline bot** (`RawBot`), a simpler model to compare Sage against.
- **Analysis and report scripts** that produce charts and a Word report.

Sage is the system under test. The benchmark imports Sage from the `sage/` folder.

## Setup

Run these from the repository root, after the first-time setup in the [root README](../README.md):

```bash
source .venv/bin/activate
pip install -r civicbench/requirements.txt
cd civicbench
cp .env.example .env     # then fill in LLMPROXY_API_KEY and LLMPROXY_ENDPOINT
```

Everything below assumes you are in the `civicbench/` folder.

## Main workflow

1. **Run the benchmark.** Sage answers all 140 questions, and Orchid follows up with up to five turns each. Each conversation is logged to `data/log_orchid/`. The results go to `data/civic_judge.json` and are saved after every question.

   This is a long, paid run. It first uploads Sage's 41 documents, which takes about two minutes, then makes many LLM calls.

   ```bash
   python run_benchmark.py
   ```

2. **Judge the answers.** Scores each saved answer with an LLM judge and writes the results to `results/sage/<model>/`.

   ```bash
   python judging/fire_bench_judge.py --model 4o-mini --file civic_judge
   ```

3. **Compare judge models.** Reads every judge run in `results/sage/` and saves comparison charts in the same folder.

   ```bash
   python analysis/compare_models.py
   ```

   `analysis/plot_sage_vs_base.py` compares Sage with the baseline bot. It needs a judged baseline file, which is not in the repo, so pass one with `--base <file>`. The two `results/sage_vs_base_*.png` charts come from an earlier run.

4. **Build the expert report.** Writes `data/civic_expert_eval.docx`.

   ```bash
   python reports/generate_eval_doc.py
   ```

`judging/update_expert_grade_keys.py` updates the expert grades in `data/civic_judge.json`. It runs with its default paths unless you pass others.

## Folder map

| Path | What it is |
| --- | --- |
| `run_benchmark.py` | **Main entry point.** Runs Sage through the question set and writes `data/civic_judge.json`. Keeps existing `Expert_grade` values when re-run. Use `--mode interactive` to give Orchid a starting question yourself. That mode writes a `log-orchid-<timestamp>.txt` file to the current folder. |
| `bots/raw_bot.py` | `RawBot`: the baseline model. Also used as Orchid's model. |
| `bots/orchid_persona.py` | Orchid, the simulated user class that runs multi-turn conversations. Run it through `run_benchmark.py`. |
| `judging/` | Scripts that score answers with LLM judges and update expert grades. |
| `analysis/` | Scripts that compare models and plot Sage against the baseline. |
| `reports/` | Builds the Word report. |
| `data/` | Questions, rubrics, saved answers, expert grades, and the generated Orchid logs. |
| `prompts/` | Judge and chooser prompts. |
| `resources/orchid/` | Orchid's persona and exit-check instructions. |
| `results/` | Judge outputs and charts. `results/sage/` holds the Sage judge results. Tracked in git, so new outputs show up as changes. |

## Notes on the data

- `data/` holds two CSVs with long, space-filled names: the questions (`civicbench_questions.xlsx - iteration 2.csv`) and the rubric (`civicbench_rubrics.xlsx - Rubric Questions Full.csv`). The code finds them by these names, so renaming them means updating the code too.
- `run_benchmark.py` reads only the questions CSV named by `--questions_csv`. It does not read every CSV in `data/`.
- Category names must match the rubric exactly. On 2026-10-31, "Organizing and Associational Engagement" was renamed to "Organizing & Associational Engagement" in the questions CSV and `civic_judge.json`. Before that, the judge skipped those 20 questions.

## Known issues

- `judging/embed_expert_scores.py` is a one-off script with a hard-coded score mapping. It overwrites `data/civic_judge.json`, so check it before running.
- `run_benchmark.py` used to pass Orchid one argument, which crashed. It now passes `RawBot("4o-mini")`, the same model the old Orchid runner used. Confirm that choice.
