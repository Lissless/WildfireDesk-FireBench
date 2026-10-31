import argparse
import datetime
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

CIVICBENCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CIVICBENCH_DIR.parent / "sage"))  # Sage lives in ../sage

from wildfire_desk import Sage
from bots.orchid_persona import BenchEvaluatorOrchid
from bots.raw_bot import RawBot


def run_interactive():
    sage = Sage()
    orchid_bot = RawBot("4o-mini")
    orchid = BenchEvaluatorOrchid(sage, orchid_bot)

    if not orchid.setup_orchid():
        print("An error occurred when setting up this application.")
        sys.exit(1)
    
    usr = input("What is the initial prompt for Orchid?: ")
    while usr != "quit":
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"log-orchid-{timestamp}.txt", "w", encoding="utf-8") as file:
            file.write(f"Key Question: {usr}\n\n")
            orchid_resp, civbot_resp = orchid.eval_convo(file, usr)
            orchid.refresh_orchid()
            usr = input("What is the initial prompt for Orchid?: ")

            # while usr != "quit":
            #     log_user(file, usr)

            #     result = prompt_orchid(usr)

            #     log_orchid(file, result, verbose=verbose)

            #     usr = input("Type your response here: ")


def _load_rubric_labels(rubric_csv: str) -> dict:
    rubric_df = pd.read_csv(rubric_csv)
    rubric_df = rubric_df[rubric_df['Category'].notna()]

    category_labels: dict = {}
    for _, row in rubric_df.iterrows():
        cat = str(row['Category']).strip()
        lbl = str(row['Label']).strip()
        category_labels.setdefault(cat, []).append(lbl)

    for cat, labels in category_labels.items():
        counts = Counter(labels)
        seen: dict = defaultdict(int)
        new_labels = []
        for lbl in labels:
            if counts[lbl] > 1:
                seen[lbl] += 1
                new_labels.append(f"{lbl}{seen[lbl]}")
            else:
                new_labels.append(lbl)
        category_labels[cat] = new_labels

    return category_labels


def run_benchmark(
    data_dir=str(CIVICBENCH_DIR / "data"),
    questions_csv=os.path.join(CIVICBENCH_DIR, "data", "civicbench_questions.xlsx - iteration 2.csv"),
    rubric_csv=os.path.join(CIVICBENCH_DIR, "data", "civicbench_rubrics.xlsx - Rubric Questions Full.csv"),
    output_path=os.path.join(CIVICBENCH_DIR, "data", "civic_judge.json"),
):
    sage = Sage()
    orchid_bot = RawBot("4o-mini")
    orchid = BenchEvaluatorOrchid(sage, orchid_bot)

    if not orchid.setup_orchid():
        print("An error occurred when setting up this application.")
        sys.exit(1)

    os.makedirs(os.path.join(data_dir, "log_orchid"), exist_ok=True)

    category_labels = _load_rubric_labels(rubric_csv)

    df = pd.read_csv(questions_csv)
    df = df[df["Question"].notna() & (df["Question"].str.strip() != "")]

    # 加载已有数据，用于保留 Expert_grade
    existing_by_id = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
        existing_by_id = {entry["_id"]: entry for entry in existing_data}

    results = []
    current_id = 1

    for _, row in df.iterrows():
        question   = row["Question"].strip()
        level      = row.get("Level", "")
        category   = row.get("Category", "")
        subcategory = row.get("Subcategory", "")

        cat_str = str(category).strip() if pd.notna(category) else ""
        print(f"\n[{current_id}] run question: {question[:60]}...")

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(data_dir, "log_orchid",
            f"log-orchid-{current_id:03d}-{timestamp}.txt")

        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"Key Question: {question}\n\n")
            orchid_prompts, civbot_responses = orchid.eval_convo(log_file, question)

        orchid.refresh_orchid()

        id_str = str(current_id).zfill(3)
        if id_str in existing_by_id:
            expert_grade = existing_by_id[id_str].get("Expert_grade", {})
        else:
            expert_grade = {lbl: "" for lbl in category_labels.get(cat_str, [])}

        results.append({
            "_id": id_str,
            "conversation": {
                "prompts": orchid_prompts,
                "responses": civbot_responses
            },
            "difficulty": str(level).strip() if pd.notna(level) else "",
            "high_class": cat_str,
            "sub_class":  str(subcategory).strip() if pd.notna(subcategory) else "",
            "Expert_grade": expert_grade,
        })
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  -> saved {id_str} to {output_path}")
        current_id += 1

    print(f"\nDone！total {len(results)} elements, write to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["interactive", "benchmark"], default="benchmark")
    parser.add_argument("--data_dir", default=str(CIVICBENCH_DIR / "data"))
    parser.add_argument("--questions_csv", default=os.path.join(CIVICBENCH_DIR, "data", "civicbench_questions.xlsx - iteration 2.csv"))
    parser.add_argument("--rubric_csv", default=os.path.join(CIVICBENCH_DIR, "data", "civicbench_rubrics.xlsx - Rubric Questions Full.csv"))
    parser.add_argument("--output", default=os.path.join(CIVICBENCH_DIR, "data", "civic_judge.json"))
    args = parser.parse_args()

    if args.mode == "benchmark":
        run_benchmark(
            data_dir=args.data_dir,
            questions_csv=args.questions_csv,
            rubric_csv=args.rubric_csv,
            output_path=args.output,
        )
    else:
        run_interactive()
