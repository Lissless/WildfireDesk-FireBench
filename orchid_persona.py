import datetime
import sys
import os
import json
import pandas as pd
from collections import Counter, defaultdict
from civic_chatbot import CivicChatbot
from wildfire_desk import Sage
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eval'))
from raw_bot import RawBot

### ----------------------------------------------------------------------------------------------------
### Orchid Class
### ----------------------------------------------------------------------------------------------------

class BenchEvaluatorOrchid():
    ### ----------------------------------------------------------------------------------------------------
    ### System Settings
    ### ----------------------------------------------------------------------------------------------------

    verbose = True
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    ### ----------------------------------------------------------------------------------------------------
    ### Orchid Settings
    ### ----------------------------------------------------------------------------------------------------

    orchid_sys = ""
    orchid_temperature = 0.7
    orchid_session_id = "orchid_" + str(timestamp)
    orchid_sys_filepath = "orchid-resources/orchid-tone.txt"

    exit_eval_session_id = "orchid_early_exit_"+ str(timestamp)
    exit_eval_sys = ""
    exit_eval_filepath = "orchid-resources/exit-evaluator-tone.txt"


    def __init__(self, civic_bot: CivicChatbot, orchid_bot: RawBot):
        self.civic_bot  = civic_bot
        self.orchid_bot = orchid_bot


    ### ----------------------------------------------------------------------------------------------------
    ### Request and Response Helper Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: prompt_orchid
    # sends a prompt to ivy and returns the model response
    def prompt_orchid(self, query_prompt, sys):
        response = self.orchid_bot.rchatgpt.generate(
            model=self.orchid_bot.model,
            system=sys,
            query=query_prompt,
            temperature=self.orchid_temperature,
            session_id=self.orchid_session_id,
            lastk=5
        )
        return response

    def prompt_early_exit(self, query_prompt):
        response = self.orchid_bot.rchatgpt.generate(
            model=self.orchid_bot.model,
            system=self.exit_eval_sys,
            query=query_prompt,
            temperature=0,
            session_id=self.exit_eval_session_id,
            lastk=0
        )
        return response

    # function: extract_response_string
    # pulls the text result out of orchid's response format
    def extract_response_string(self, response):
        if isinstance(response, dict):
            res = response.get("result")
        elif isinstance(response, tuple):
            res = response[0]["result"]
        else:
            res = response
        return res

    def setup_orchid(self):
        global orchid_sys
        try:
            self.orchid_sys = self.load_text_file(self.orchid_sys_filepath)
            self.exit_eval_sys = self.load_text_file(self.exit_eval_filepath)
        except:
            return False
        return True

    ### ----------------------------------------------------------------------------------------------------
    ### Logging Functions
    ### ----------------------------------------------------------------------------------------------------


    def log_orchid(self, file, response, verbose=verbose):
        phrase = f"Orchid: {self.extract_response_string(response)}\n"
        file.write(phrase)
        
        if verbose:
            print(phrase)

    # function: load_text_file
    # loads a text file and returns contents, handles file errors
    def load_text_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"Error: could not find file {filepath}")
            return None
        except PermissionError:
            print(f"Error: permission denied when opening file {filepath}")
            return None
        except OSError as e:
            print(f"Error: could not open file {filepath}: {e}")
            return None
    
    def interpret_bot_response(self, bot_res):
        if isinstance(bot_res, tuple):
            return bot_res[0]
        elif isinstance(bot_res, str):
            return bot_res
        else:
            return "Bad return - Cannot interpret"
    
    def determine_early_exit(self, file, initial_qu, bot_responses):
        # format all the evaluation prompt
        bot_str = ""
        for resp in bot_responses:
            bot_str = bot_str + resp + "\n"
        exit_prompt = f"QUESTION : {initial_qu}\nRESPONSES : {bot_str}"
        early_exit_resp = self.prompt_early_exit(exit_prompt)
        determination = self.extract_response_string(early_exit_resp)
        early_det = "\nEarly Exit Determination: " + determination + "\n"

        file.write(early_det)
        print(early_det)

        juegement = determination.split("|")[0]
        try:
            return int(juegement) == 1
        except:    
            return 0
        
    def eval_convo(self, file, initial_qu, timeout_turns=5):
        initial_sys_inclusion = f"""\n\n**First Message Requirement (MANDATORY)**
        On your very first message only, you MUST begin with the exact phrase:

        '{initial_qu}'

        * This phrase must appear at the very start of the message
        * Do not modify or paraphrase it
        * Mandatory: Say only this phrase and nothing else"""
        initial_sys = self.orchid_sys + initial_sys_inclusion
        bot_res = ""
        orchid_responses = []
        civbot_responses = []
        for i in range(timeout_turns):
            if i == 0:
                orchid_res = self.prompt_orchid(initial_sys_inclusion, initial_sys)
            else:
                orchid_res = self.prompt_orchid(bot_res, self.orchid_sys)
            
            self.log_orchid(file, orchid_res)
            orchid_res_str = self.extract_response_string(orchid_res)

            bot_res = self.interpret_bot_response(self.civic_bot.chat_with_bot(orchid_res_str))

            self.civic_bot.log_bot(file, bot_res)
            orchid_responses.append(orchid_res_str)
            civbot_responses.append(bot_res)

            if self.determine_early_exit(file, initial_qu, civbot_responses):
                break
        
        # Add a question asking if the question was answered

        return orchid_responses, civbot_responses

    def refresh_orchid(self):
        # This just moves orchid to a completely clean session. If there is nothing in a room there isnt anything it can rememeber!
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.orchid_session_id = "orchid_" + str(self.timestamp)


### ----------------------------------------------------------------------------------------------------
### Command Line Interface
### ----------------------------------------------------------------------------------------------------


def main():
    sage = Sage()
    sage.setup_sage(True)
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
	data_dir="eval/data",
	questions_csv="eval/data/civicbench_questions.xlsx - iteration 2.csv",
	rubric_csv="eval/data/civicbench_rubrics.xlsx - Rubric Questions Full.csv",
	output_path="eval/data/civic_judge.json",
):
	sage = Sage()
	sage.setup_sage(True)
	orchid_bot = RawBot("4o-mini")
	orchid = BenchEvaluatorOrchid(sage, orchid_bot)

	if not orchid.setup_orchid():
		print("An error occurred when setting up this application.")
		sys.exit(1)

	os.makedirs(os.path.join(data_dir, "log_orchid"), exist_ok=True)

	category_labels = _load_rubric_labels(rubric_csv)

	df = pd.read_csv(questions_csv)
	df = df[df["Question"].notna() & (df["Question"].str.strip() != "")]

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

		expert_grade = {lbl: "" for lbl in category_labels.get(cat_str, [])}

		results.append({
			"_id": str(current_id).zfill(3),
			"conversation": {
				"prompts": orchid_prompts,
				"responses": civbot_responses
			},
			"difficulty": str(level).strip() if pd.notna(level) else "",
			"high_class": cat_str,
			"sub_class":  str(subcategory).strip() if pd.notna(subcategory) else "",
			"Expert_grade": expert_grade,
		})
		current_id += 1

	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent=2)

	print(f"\nDone！total {len(results)} elements, write to {output_path}")


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--mode", choices=["interactive", "benchmark"], default="benchmark")
	parser.add_argument("--data_dir",      default="eval/data")
	parser.add_argument("--questions_csv", default="eval/data/civicbench_questions.xlsx - iteration 2.csv")
	parser.add_argument("--rubric_csv",    default="eval/data/civicbench_rubrics.xlsx - Rubric Questions Full.csv")
	parser.add_argument("--output",        default="eval/data/civic_judge2.json")
	args = parser.parse_args()

	if args.mode == "benchmark":
		run_benchmark(
			data_dir=args.data_dir,
			questions_csv=args.questions_csv,
			rubric_csv=args.rubric_csv,
			output_path=args.output,
		)
	else:
		main()