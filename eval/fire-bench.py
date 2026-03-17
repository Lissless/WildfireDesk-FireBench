from build.lib.llmproxy import LLMProxy
import os, json
import argparse
from datetime import datetime
from tqdm import tqdm
import re
import time
import numpy as np
agent = LLMProxy()
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
base_dir = os.path.dirname(__file__)
prompt_path = os.path.join(base_dir, "prompts", "prompt_choose.txt")
template_choose = open(prompt_path, encoding="utf-8").read()

def query_llm(query_prompt, model_name,session_id_value,rag_enabled,system_instructions):
    tries = 0
    while tries < 5:
        tries += 1
        try:
            response = agent.generate(
                model = model_name,
                system = system_instructions,
                query = query_prompt,
                temperature = 0,
                lastk = 0, # Question, does verifyer need to rememmber anything?
                session_id = session_id_value,
                rag_usage = rag_enabled,
            )
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

def get_pred(data, args, fout):
    model_name = args.model
    session_id_value = 'verify'+str(timestamp) # This would generate a different session every time it is prompted
    rag_enabled = args.rag
    system_instructions = (
        """You are a helpdesk for grassroots activists and groups. Understand users' situations and answer their questions.
        """
    )
    for item in tqdm(data):
        context = item['context']

        template = template_choose
        prompt = template.replace('$DOC$', context.strip()).replace('$Q$', item['question'].strip()).replace('$C_A$', item['choice_A'].strip()).replace('$C_B$', item['choice_B'].strip()).replace('$C_C$', item['choice_C'].strip()).replace('$C_D$', item['choice_D'].strip())

        output = query_llm(prompt, model_name,session_id_value,rag_enabled,system_instructions)

        if output == '':
            continue
        response = output["result"].strip()
        item['response'] = response
        item['pred'] = extract_answer(response)
        item['judge'] = item['pred'] == item['answer']
        item['rag_context'] = output["rag_context"]
        item['context'] = context[:1000]
        fout.write(json.dumps(item, ensure_ascii=False) + '\n')
        fout.flush()
def eval_pred(out_file,save_dir):
    prompt_path = os.path.join(base_dir, "results", out_file)
    data = []
    with open(prompt_path, "r", encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))

    num_right = sum(1 for item in data if item.get("judge"))

    data = {
        "win_rate": np.round((num_right/len(data)),2)
    }
    score_file = os.path.join(save_dir, f"{args.model}_{timestamp}_score.jsonl")
    with open(score_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
def main():
    save_dir = os.path.join(base_dir, "results")
    os.makedirs(save_dir, exist_ok=True)
    print(args)
    out_file = os.path.join(save_dir, f"{args.model}_{timestamp}.jsonl")
    prompt_path = os.path.join(base_dir, "data", "civic_group.json")
    dataset = json.load(open(prompt_path, 'r', encoding='utf-8'))
    data_all = [{"_id": item["_id"], "context": item["context"], "question": item["question"], "choice_A": item["choice_A"], "choice_B": item["choice_B"], "choice_C": item["choice_C"], "choice_D": item["choice_D"], "answer": item["answer"]} for item in dataset]

    # cache
    has_data = {}
    if os.path.exists(out_file):
        with open(out_file, encoding='utf-8') as f:
            has_data = {json.loads(line)["_id"]: 0 for line in f}
    fout = open(out_file, 'a', encoding='utf-8')
    data = []
    for item in data_all:
        if item["_id"] not in has_data:
            data.append(item)

    get_pred(data, args, fout)
    eval_pred(out_file,save_dir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", "-m", type=str, default="4o-mini", choices=["gpt-4.1-mini, gpt-5-mini, gpt-5-nano, 4o-mini, us.meta.llama4-maverick-17b-instruct-v1:0, us.meta.llama4-scout-17b-instruct-v1:0, us.meta.llama3-2-90b-instruct-v1:0, us.meta.llama3-3-70b-instruct-v1:0, us.meta.llama3-2-3b-instruct-v1:0, us.meta.llama3-2-1b-instruct-v1:0, us.meta.llama3-1-8b-instruct-v1:0, us.anthropic.claude-3-haiku-20240307-v1:0, google.gemma-3-4b-it, google.gemma-3-12b-it, google.gemma-3-27b-it, gemini-2.5-flash-lite"])
    parser.add_argument("--rag", "-r", type=bool, default=True)
    args = parser.parse_args()
    main()
