from build.lib.llmproxy import LLMProxy
import os, json
import argparse
from datetime import datetime
from tqdm import tqdm
import re
import time
import numpy as np
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from wildfire_desk import Sage

agent = LLMProxy()
base_dir = os.path.dirname(__file__)

### ----------------------
### System Settings
### ----------------------

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

### ----------------------
### Sage Settings
### ----------------------
sage = Sage()
sage_core = ""
sage_temperature = 0.6
sage_session_id = "sage" + str(timestamp)
sage_rag_t = 0.4
sage_rag_k = 5

DIMENSIONS = [
	"Factual and Procedural Accuracy",
	"Actionability",
	"Contextual Relevance",
	"Completeness",
	"Clarity & Usability",
	"Civic Responsibility",
]

DIM_ABBREV = [
	"Factual\nAccuracy",
	"Actionability",
	"Contextual\nRelevance",
	"Completeness",
	"Clarity &\nUsability",
	"Civic\nResponsibility",
]


def query_llm(query_prompt, args):
	tries = 0
	while tries < 5:
		tries += 1
		try:
			sage.sage_model = args.model
			response_dict, rag_context = sage.prompt_sage(query_prompt, args.rag)
			return response_dict, rag_context
		except KeyboardInterrupt as e:
			raise e
		except Exception as e:
			print("Error Occurs: \"%s\"        Retry ..." % (str(e)))
			time.sleep(1)
	print("Max tries. Failed.")
	return ''


def build_conversation(item):
	prompts = item['conversation']['prompts']
	responses = item['conversation']['responses']
	parts = []
	for p, r in zip(prompts, responses):
		parts.append(f"User: {p}\n\nAssistant: {r}")
	return "\n\n---\n\n".join(parts)


def build_judge_prompt(conversation_text):
	dim_desc = (
		"1. Factual and Procedural Accuracy (1-5): Whether the response is correct and reflects "
		"real civic processes, roles, and rules.\n"
		"2. Actionability (1-5): Whether the response provides clear, concrete steps the user can take.\n"
		"3. Contextual Relevance (1-5): Whether the response is tailored to the user's situation, "
		"location, and goals.\n"
		"4. Completeness (1-5): Whether the response covers all key steps, options, or considerations.\n"
		"5. Clarity & Usability (1-5): Whether the response is easy to understand, well-structured, "
		"and accessible to non-experts.\n"
		"6. Civic Responsibility (1-5): Whether the response promotes constructive, ethical, and "
		"inclusive civic engagement."
	)
	prompt = (
		"You are an expert evaluator of civic helpdesk chatbot responses.\n\n"
		"Below is a conversation between a user and an assistant:\n\n"
		f"{conversation_text}\n\n"
		"---\n\n"
		"Please evaluate the assistant's response(s) on the following 6 dimensions, "
		"each scored 1 to 5 (1 = very poor, 5 = excellent):\n\n"
		f"{dim_desc}\n\n"
		"Respond ONLY with a JSON object in this exact format, with no extra text:\n"
		"{\n"
		'  "Factual and Procedural Accuracy": <integer 1-5>,\n'
		'  "Actionability": <integer 1-5>,\n'
		'  "Contextual Relevance": <integer 1-5>,\n'
		'  "Completeness": <integer 1-5>,\n'
		'  "Clarity & Usability": <integer 1-5>,\n'
		'  "Civic Responsibility": <integer 1-5>\n'
		"}"
	)
	return prompt


def extract_scores(response_text):
	result = {dim: None for dim in DIMENSIONS}
	match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
	if match:
		try:
			print("Found json")
			parsed = json.loads(match.group())
			for dim in DIMENSIONS:
				val = parsed.get(dim)
				if val is not None:
					result[dim] = max(1, min(5, int(val)))
			print(result)
			return result
		except (json.JSONDecodeError, ValueError):
			pass
	for dim in DIMENSIONS:
		pattern = re.escape(dim) + r'["\s:]*(\d)'
		m = re.search(pattern, response_text, re.IGNORECASE)
		if m:
			result[dim] = max(1, min(5, int(m.group(1))))
	return result


def get_pred(data, args, save_path):
	results = []
	for item in tqdm(data):
		conversation_text = build_conversation(item)
		query_prompt = build_judge_prompt(conversation_text)
		print("prompt: ",query_prompt)
		output = query_llm(query_prompt, args)
		if output == '':
			continue
		response_dict, _ = output
		response_text = response_dict["result"].strip()
		print("response: ",response_text)
		item['AI_grade'] = extract_scores(response_text)
		results.append(item)
	with open(save_path, "w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent=2)


def eval_pred(out_file, save_dir):
	with open(out_file, "r", encoding="utf-8") as f:
		data = json.load(f)

	stem = os.path.splitext(os.path.basename(out_file))[0]

	dim_scores = defaultdict(list)
	class_dim_scores = defaultdict(lambda: defaultdict(list))
	diff_dim_scores = defaultdict(lambda: defaultdict(list))

	for item in data:
		ai = item.get('AI_grade', {})
		high_class = item.get('high_class', 'Unknown')
		difficulty = item.get('difficulty', 'Unknown')
		for dim in DIMENSIONS:
			score = ai.get(dim)
			if score is not None:
				dim_scores[dim].append(score)
				class_dim_scores[high_class][dim].append(score)
				diff_dim_scores[difficulty][dim].append(score)

	fig1, axes = plt.subplots(2, 3, figsize=(14, 8))
	fig1.suptitle("Score Distribution by Dimension", fontsize=14, fontweight='bold')
	for idx, (dim, abbrev) in enumerate(zip(DIMENSIONS, DIM_ABBREV)):
		ax = axes[idx // 3][idx % 3]
		scores = dim_scores[dim]
		counts = [scores.count(s) for s in range(1, 6)]
		ax.bar(range(1, 6), counts, color='steelblue', edgecolor='white')
		ax.set_title(abbrev.replace('\n', ' '), fontsize=9)
		ax.set_xlabel("Score", fontsize=8)
		ax.set_ylabel("Count", fontsize=8)
		ax.set_xticks(range(1, 6))
		ax.set_ylim(bottom=0)
	plt.tight_layout()
	fig1_path = os.path.join(save_dir, f"{stem}_fig_dimension.png")
	fig1.savefig(fig1_path, bbox_inches='tight', dpi=150)
	plt.close(fig1)
	print(f"Saved: {fig1_path}")

	high_classes = sorted(class_dim_scores.keys())
	n_groups = len(high_classes)
	if n_groups > 0:
		fig2, ax2 = plt.subplots(figsize=(14, 6))
		x = np.arange(len(DIMENSIONS))
		width = 0.8 / n_groups
		for i, hc in enumerate(high_classes):
			avgs = [
				np.mean(class_dim_scores[hc][dim]) if class_dim_scores[hc][dim] else 0
				for dim in DIMENSIONS
			]
			offset = (i - n_groups / 2 + 0.5) * width
			ax2.bar(x + offset, avgs, width, label=hc)
		ax2.set_title("Average Score by Dimension and High Class", fontsize=13, fontweight='bold')
		ax2.set_ylabel("Average Score (1-5)", fontsize=10)
		ax2.set_xticks(x)
		ax2.set_xticklabels(DIM_ABBREV, fontsize=8)
		ax2.set_ylim(0, 5.5)
		ax2.legend(fontsize=8, loc='lower right')
		plt.tight_layout()
		fig2_path = os.path.join(save_dir, f"{stem}_fig_highclass.png")
		fig2.savefig(fig2_path, bbox_inches='tight', dpi=150)
		plt.close(fig2)
		print(f"Saved: {fig2_path}")

	difficulties = sorted(diff_dim_scores.keys())
	n_diff = len(difficulties)
	if n_diff > 0:
		fig3, ax3 = plt.subplots(figsize=(14, 6))
		x = np.arange(len(DIMENSIONS))
		width = 0.8 / n_diff
		colors = ['#e07b54', '#5b8fcc', '#6dbf67']
		for i, diff in enumerate(difficulties):
			avgs = [
				np.mean(diff_dim_scores[diff][dim]) if diff_dim_scores[diff][dim] else 0
				for dim in DIMENSIONS
			]
			offset = (i - n_diff / 2 + 0.5) * width
			color = colors[i % len(colors)]
			ax3.bar(x + offset, avgs, width, label=diff, color=color)
		ax3.set_title("Average Score by Dimension and Difficulty", fontsize=13, fontweight='bold')
		ax3.set_ylabel("Average Score (1-5)", fontsize=10)
		ax3.set_xticks(x)
		ax3.set_xticklabels(DIM_ABBREV, fontsize=8)
		ax3.set_ylim(0, 5.5)
		ax3.legend(fontsize=9)
		plt.tight_layout()
		fig3_path = os.path.join(save_dir, f"{stem}_fig_difficulty.png")
		fig3.savefig(fig3_path, bbox_inches='tight', dpi=150)
		plt.close(fig3)
		print(f"Saved: {fig3_path}")


def main():
	save_dir = os.path.join(base_dir, "results")
	os.makedirs(save_dir, exist_ok=True)
	print(args)

	out_file = os.path.join(save_dir, f"{args.file}_{args.model}_{timestamp}.json")
	prompt_path = os.path.join(base_dir, "data", args.file + ".json")
	dataset = json.load(open(prompt_path, 'r', encoding='utf-8'))

	has_data = set()
	if os.path.exists(out_file):
		with open(out_file, encoding='utf-8') as f:
			try:
				cached = json.load(f)
				has_data = {item["_id"] for item in cached}
			except json.JSONDecodeError:
				pass

	data = [item for item in dataset if item["_id"] not in has_data]

	get_pred(data, args, out_file)
	eval_pred(out_file, save_dir)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--model", "-m", type=str, default="4o-mini")
	parser.add_argument("--rag", "-r", type=bool, default=True)
	parser.add_argument("--file", "-f", type=str, default="civic_judge")
	args = parser.parse_args()
	main()
