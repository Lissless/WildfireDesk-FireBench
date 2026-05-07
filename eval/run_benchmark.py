import datetime
from civic_chatbot import CivicChatbot
from wildfire_desk import Sage
from orchid_persona import BenchEvaluatorOrchid
import os
import sys
import json
import glob
import pandas as pd
import argparse

def run_benchmark(data_dir="eval/data", output_path="eval/data/civic_judge.json"):
	#TODO: before final push we should remove False from the Sage declaration below
	sage = Sage(False) # I changed Sage creation to run setup_sage() when made, the Boolean False just tells it not to do all the uploads
	# TODO: Effectiely add a RawBot here and do the same evaluations throughout the pipeline, this will show the difference between Sage and plain GPT
	sage.setup_sage(False)
	orchid = BenchEvaluatorOrchid(sage)

	if not orchid.setup_orchid():
		print("An error occurred when setting up this application.")
		sys.exit(1)

	os.makedirs(os.path.join(data_dir, "log_orchid"), exist_ok=True)

	csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
	if not csv_files:
		print(f"No CSV files found in {data_dir}")
		return

	results = []
	current_id = 1

	for csv_path in csv_files:
		print(f"\nreading: {csv_path}")
		df = pd.read_csv(csv_path)

		df = df[df["Question"].notna() & (df["Question"].str.strip() != "")]

		for _, row in df.iterrows():
			question = row["Question"].strip()
			level = row.get("Level", "")
			category = row.get("Category", "")
			subcategory = row.get("Subcategory", "")

			print(f"\n[{current_id}] run question: {question[:60]}...")

			timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
			log_path = f"eval/data/log_orchid/log-orchid-{current_id:03d}-{timestamp}.txt"

			with open(log_path, "w", encoding="utf-8") as log_file:
				log_file.write(f"Key Question: {question}\n\n")
				orchid_prompts, civbot_responses = orchid.eval_convo(log_file, question)

			orchid.refresh_orchid()

			results.append({
				"_id": str(current_id).zfill(3),
				"conversation": {
					"prompts": orchid_prompts,
					"responses": civbot_responses
				},
				"difficulty": level if pd.notna(level) else "",
				"high_class": category if pd.notna(category) else "",
				"sub_class": subcategory if pd.notna(subcategory) else "",
				"Expert_grade": {
					"Factual and Procedural Accuracy": "",
					"Actionability": "",
					"Contextual Relevance": "",
					"Completeness": "",
					"Clarity & Usability": "",
					"Civic Responsibility": ""
				}
			})
			current_id += 1

	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent=2)

	print(f"\nDone! total {len(results)} elements, write to {output_path}")
	
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["interactive", "benchmark"], default="interactive")
    parser.add_argument("--data_dir", default="eval/data")
    parser.add_argument("--output", default="eval/data/civic_judge.json")
    args = parser.parse_args()
    run_benchmark(data_dir=args.data_dir, output_path=args.output)