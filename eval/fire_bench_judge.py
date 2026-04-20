from build.lib.llmproxy import LLMProxy
import os, json
import argparse
from datetime import datetime
from tqdm import tqdm
import re
import time
import numpy as np
from collections import defaultdict
from wildfire_desk import prompt_sage
agent = LLMProxy()
base_dir = os.path.dirname(__file__)
prompt_path = os.path.join(base_dir, "prompts", "prompt_choose.txt")
template_choose = open(prompt_path, encoding="utf-8").read()
### ----------------------
### System Settings        -
### ----------------------

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = True

### ----------------------
### Sage Settings        -
### ----------------------
sage = LLMProxy()
sage_core = "" # to be uploaded upon setup
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_rag_t = 0.4 # subject to change
sage_rag_k = 5 # top number of documents to fetch to use for rag, lets see if we need to set this
def query_llm(query_prompt,args):
    tries = 0
    while tries < 5:
        tries += 1
        try:
            response = prompt_sage(query_prompt,args.rag,args.model)
            return response
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            print("Error Occurs: \"%s\"        Retry ..."%(str(e)))
            time.sleep(1)
    else:
        print("Max tries. Failed.")
        return ''

def extract_answer(response):
    response = response.replace('*', '')
    match = re.search(r'The correct answer is \(([A-D])\)', response)
    if match:
        return match.group(1)
    else:
        match = re.search(r'The correct answer is ([A-D])', response)
        if match:
            return match.group(1)
        else:
            return None

def get_pred(data, args, save_path):
    model_name = args.model
    session_id_value = 'verify' + str(timestamp)
    rag_enabled = args.rag

    system_instructions = (
        """You are a helpdesk for grassroots activists and groups. Understand users' situations and answer their questions."""
    )

    results = [] 

    for item in tqdm(data):
        context = item['context']

        template = template_choose
        prompt = template.replace('$DOC$', context.strip()) \
                         .replace('$Q$', item['question'].strip()) \
                         .replace('$C_A$', item['choice_A'].strip()) \
                         .replace('$C_B$', item['choice_B'].strip()) \
                         .replace('$C_C$', item['choice_C'].strip()) \
                         .replace('$C_D$', item['choice_D'].strip())

        output = query_llm(prompt,args)

        if output == '':
            continue

        response = output["result"].strip()
        item['response'] = response
        item['pred'] = extract_answer(response)
        item['judge'] = item['pred'] == item['answer']
        item['rag_context'] = output["rag_context"]
        item['context'] = context[:1000]

        results.append(item) 
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
def eval_pred(out_file, save_dir):
    prompt_path = os.path.join(base_dir, "results", out_file)

    with open(prompt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    num_right = sum(1 for item in data if item.get("judge"))
    overall_win_rate = np.round(num_right / len(data), 2) if data else 0.0

    source_counts = defaultdict(lambda: {"correct": 0, "total": 0})
    class_counts = defaultdict(lambda: {"correct": 0, "total": 0})
    class_counts2 = defaultdict(lambda: {"A": 0, "B": 0, "C": 0, "D": 0})
    source_counts2 = defaultdict(lambda: {"A": 0, "B": 0, "C": 0, "D": 0})
    for item in data:
        judge = item.get("judge", False)
        source = item.get("source", "Unknown")
        cls = item.get("class", "Unknown")
        answer = item.get("answer","Unknown")

        source_counts[source]["total"] += 1
        source_counts[source]["correct"] += int(judge)

        class_counts[cls]["total"] += 1
        class_counts[cls]["correct"] += int(judge)

        class_counts2[cls][answer] += 1
        source_counts2[source][answer] += 1

    source_win_rate = {k: np.round(v["correct"] / v["total"], 2) if v["total"] > 0 else 0.0
                       for k, v in source_counts.items()}
    class_win_rate = {k: np.round(v["correct"] / v["total"], 2) if v["total"] > 0 else 0.0
                      for k, v in class_counts.items()}
    class2 = dict(class_counts2)

    result = {
        "overall_win_rate": overall_win_rate,
        "source_win_rate": source_win_rate,
        "class_win_rate": class_win_rate
    }
    result2 = {
        "answer_class_distribution": class2,
        "answer_source_distribution": source_counts2
    }
    score_file = os.path.join(save_dir, f"{args.file}_{args.model}_{timestamp}_score.json")
    answer_file = os.path.join(save_dir, f"{args.file}_{args.model}_{timestamp}_answer.json")
    with open(score_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    with open(answer_file, "w", encoding="utf-8") as f:
        json.dump(result2, f, indent=2)
def main():
    save_dir = os.path.join(base_dir, "results")
    os.makedirs(save_dir, exist_ok=True)
    print(args)
    out_file = os.path.join(save_dir, f"{args.file}_{args.model}_{timestamp}.jsonl")
    prompt_path = os.path.join(base_dir, "data", args.file + ".json")
    dataset = json.load(open(prompt_path, 'r', encoding='utf-8'))
    data_all = [{"_id": item["_id"], "context": item["context"], "question": item["question"], "choice_A": item["choice_A"], "choice_B": item["choice_B"], "choice_C": item["choice_C"], "choice_D": item["choice_D"], "answer": item["answer"], "source": item["source"], "class": item["class"]} for item in dataset]

    # cache
    has_data = {}
    if os.path.exists(out_file):
        with open(out_file, encoding='utf-8') as f:
            has_data = {json.loads(line)["_id"]: 0 for line in f}
    data = []
    for item in data_all:
        if item["_id"] not in has_data:
            data.append(item)

    get_pred(data, args, out_file)
    #out_file = r"civic_4o-mini_20260323_195550.jsonl"
    eval_pred(out_file,save_dir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", "-m", type=str, default="4o-mini", choices=["gpt-4.1-mini, gpt-5-mini, gpt-5-nano, 4o-mini, us.meta.llama4-maverick-17b-instruct-v1:0, us.meta.llama4-scout-17b-instruct-v1:0, us.meta.llama3-2-90b-instruct-v1:0, us.meta.llama3-3-70b-instruct-v1:0, us.meta.llama3-2-3b-instruct-v1:0, us.meta.llama3-2-1b-instruct-v1:0, us.meta.llama3-1-8b-instruct-v1:0, us.anthropic.claude-3-haiku-20240307-v1:0, google.gemma-3-4b-it, google.gemma-3-12b-it, google.gemma-3-27b-it, gemini-2.5-flash-lite"])
    parser.add_argument("--rag", "-r", type=bool, default=True)
    parser.add_argument("--file", "-f", type=str, default="civic")
    args = parser.parse_args()
    main()
