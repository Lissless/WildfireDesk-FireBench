import os, json, csv, sys
import argparse
from tqdm import tqdm
import re
import time
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from raw_bot import RawBot

if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]

base_dir = os.path.dirname(__file__)


def build_rubric_data(csv_path):
	"""从CSV读取rubric，返回 Category -> [行字典列表] 映射，自动处理重复Label加数字后缀。"""
	category_rows = {}

	with open(csv_path, encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			cat = row['Category'].strip()
			if not cat:
				continue
			if cat not in category_rows:
				category_rows[cat] = []
			category_rows[cat].append({
				'Label':       row['Label'].strip(),
				'Element':     row['Element (Question)'].strip(),
				'Description': row['Description'].strip(),
				'Why':         row['Why it matters'].strip(),
				'Points':      int(row['Points'].strip()),
			})

	# 与 civic_judge.json 的 key 保持一致：重复 Label 加数字后缀
	for cat, rows in category_rows.items():
		labels = [r['Label'] for r in rows]
		counts = Counter(labels)
		seen = defaultdict(int)
		for row in rows:
			lbl = row['Label']
			if counts[lbl] > 1:
				seen[lbl] += 1
				row['Label'] = f"{lbl}{seen[lbl]}"

	return category_rows


def query_llm(query_prompt, bot):
	tries = 0
	while tries < 5:
		tries += 1
		try:
			return bot.chat_with_bot(query_prompt)
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


def build_judge_prompt(conversation_text, rubric_rows):
	"""根据该 Category 的 rubric 行，构建 LLM judge prompt。"""
	dim_lines = []
	json_lines = []

	for i, row in enumerate(rubric_rows, 1):
		label   = row['Label']
		element = row['Element']
		desc    = row['Description']
		pts     = row['Points']
		dim_lines.append(
			f"{i}. {label} (0–{pts} points): {element}\n"
			f"   Criterion: {desc}"
		)
		json_lines.append(f'  "{label}": <integer 0-{pts}>')

	dim_desc   = "\n\n".join(dim_lines)
	json_format = "{\n" + ",\n".join(json_lines) + "\n}"

	prompt = (
		"You are an expert evaluator of civic helpdesk chatbot responses.\n\n"
		"Below is a conversation between a user and an assistant:\n\n"
		f"{conversation_text}\n\n"
		"---\n\n"
		"Please evaluate the assistant's response(s) on the following dimensions. "
		"Each dimension shows its maximum score in parentheses — score from 0 to that maximum.\n\n"
		f"{dim_desc}\n\n"
		"Respond ONLY with a JSON object in this exact format, with no extra text:\n"
		f"{json_format}"
	)
	return prompt


def extract_scores(response_text, rubric_rows):
	"""从 LLM 返回文本中提取各 Label 的得分，超出范围时截断到 [0, max_points]。"""
	max_pts = {row['Label']: row['Points'] for row in rubric_rows}
	result: dict[str, int | None] = {row['Label']: None for row in rubric_rows}

	match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
	if match:
		try:
			print("Found json")
			parsed = json.loads(match.group())
			for label, max_p in max_pts.items():
				val = parsed.get(label)
				if val is not None:
					result[label] = max(0, min(max_p, int(val)))
			print(result)
			return result
		except (json.JSONDecodeError, ValueError):
			pass

	# 备用：逐维度正则匹配
	for label, max_p in max_pts.items():
		pattern = re.escape(label) + r'["\s:]*(\d+)'
		m = re.search(pattern, response_text, re.IGNORECASE)
		if m:
			result[label] = max(0, min(max_p, int(m.group(1))))

	return result


def get_pred(data, args, save_path, rubric_data):
	bot = RawBot(args.model)
	results = []
	for item in tqdm(data):
		high_class  = item.get('high_class', '')
		rubric_rows = rubric_data.get(high_class, [])
		if not rubric_rows:
			print(f"警告：未找到 Category '{high_class}' 对应的 rubric，跳过 id={item.get('_id')}")
			continue

		conversation_text = build_conversation(item)
		query_prompt      = build_judge_prompt(conversation_text, rubric_rows)
		#print("prompt: ", query_prompt)

		response_text = query_llm(query_prompt, bot)
		if not response_text:
			continue
		response_text = response_text.strip()
		#print("response: ", response_text)

		item['AI_grade'] = extract_scores(response_text, rubric_rows)
		results.append(item)

	with open(save_path, "w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent=2)


def eval_pred(out_file, save_dir, rubric_data):
	with open(out_file, "r", encoding="utf-8") as f:
		data = json.load(f)

	stem = os.path.splitext(os.path.basename(out_file))[0]

	# 按难度和 high_class 分别累计实际总分与满分总和
	diff_actual  = defaultdict(int)
	diff_max     = defaultdict(int)
	class_actual = defaultdict(int)
	class_max    = defaultdict(int)

	for item in data:
		ai          = item.get('AI_grade', {})
		high_class  = item.get('high_class', 'Unknown')
		difficulty  = item.get('difficulty', 'Unknown')
		rubric_rows = rubric_data.get(high_class, [])
		for row in rubric_rows:
			score = ai.get(row['Label'])
			if score is not None:
				diff_actual[difficulty]  += score
				diff_max[difficulty]     += row['Points']
				class_actual[high_class] += score
				class_max[high_class]    += row['Points']

	# --- Chart 1：各难度得分比例竖柱状图 ---
	diff_order = [d for d in ['Easy', 'Medium', 'Hard'] if d in diff_max]
	if diff_order:
		ratios = [diff_actual[d] / diff_max[d] for d in diff_order]
		colors = ['#6dbf67', '#5b8fcc', '#e07b54']
		fig1, ax1 = plt.subplots(figsize=(max(4, len(diff_order) * 1.5), 5))
		bars = ax1.bar(diff_order, ratios, color=colors[:len(diff_order)])
		ax1.set_ylim(0, 1)
		ax1.set_ylabel("Score Ratio (Actual / Max)", fontsize=10)
		ax1.set_title("Score Ratio by Difficulty", fontsize=13, fontweight='bold')
		for bar, val in zip(bars, ratios):
			ax1.text(bar.get_x() + bar.get_width() / 2, val + 0.01,
					 f"{val:.1%}", ha='center', fontsize=10)
		plt.tight_layout()
		fig1_path = os.path.join(save_dir, f"{stem}_fig_difficulty.png")
		fig1.savefig(fig1_path, bbox_inches='tight', dpi=150)
		plt.close(fig1)
		print(f"Saved: {fig1_path}")

	# --- Chart 2：各 high_class 得分比例竖柱状图 ---
	if class_max:
		classes = sorted(class_max.keys())
		ratios  = [class_actual[c] / class_max[c] for c in classes]
		short   = [c[:22] + '..' if len(c) > 22 else c for c in classes]
		fig2, ax2 = plt.subplots(figsize=(max(8, len(classes) * 1.6), 5))
		bars = ax2.bar(short, ratios, color='steelblue')
		ax2.set_ylim(0, 1)
		ax2.set_ylabel("Score Ratio (Actual / Max)", fontsize=10)
		ax2.set_title("Score Ratio by Category", fontsize=13, fontweight='bold')
		for bar, val in zip(bars, ratios):
			ax2.text(bar.get_x() + bar.get_width() / 2, val + 0.01,
					 f"{val:.1%}", ha='center', fontsize=9)
		plt.xticks(rotation=20, ha='right', fontsize=8)
		plt.tight_layout()
		fig2_path = os.path.join(save_dir, f"{stem}_fig_highclass.png")
		fig2.savefig(fig2_path, bbox_inches='tight', dpi=150)
		plt.close(fig2)
		print(f"Saved: {fig2_path}")


def main():
	safe_model = args.model.replace(':', '-')
	save_dir = os.path.join(base_dir, "results", safe_model)
	os.makedirs(save_dir, exist_ok=True)
	print(args)

	rubric_data = build_rubric_data(args.rubric)

	out_file    = os.path.join(save_dir, f"{args.file}_{safe_model}.json")
	prompt_path = os.path.join(base_dir, "data", args.file + ".json")
	dataset     = json.load(open(prompt_path, 'r', encoding='utf-8'))
	data        = dataset

	get_pred(data, args, out_file, rubric_data)
	eval_pred(out_file, save_dir, rubric_data)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="用 LLM judge 对 civic_judge.json 按 rubric 打分")
	parser.add_argument("--model",  "-m", type=str,  default="4o-mini")

	parser.add_argument("--file",   "-f", type=str,  default="civic_judge")
	parser.add_argument("--rubric", "-rb", type=str,
		default=os.path.join(base_dir, "data", "civicbench_rubrics.xlsx - Rubric Questions Full.csv"),
		help="Rubric CSV 路径")
	args = parser.parse_args()
	main()
