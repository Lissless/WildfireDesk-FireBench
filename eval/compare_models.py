import os
import json
import csv
import re
import sys
import argparse
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]

base_dir    = os.path.dirname(__file__)
results_dir = os.path.join(base_dir, 'results')
default_csv = os.path.join(base_dir, 'data',
	'civicbench_rubrics.xlsx - Rubric Questions Full.csv')

def make_short_name(model_dir: str) -> str:
	name = model_dir
	name = re.sub(r'^us\.(anthropic\.|meta\.)?', '', name)
	name = re.sub(r'^google\.', '', name)
	name = re.sub(r'-\d{8}-v\d+-\d+$', '', name)
	name = re.sub(r'-v\d+-\d+$', '', name)        
	name = re.sub(r'(-instruct|-it)$', '', name)
	return name


def build_rubric_data(csv_path: str) -> dict:
	category_rows: dict = {}
	with open(csv_path, encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			cat = row['Category'].strip()
			if not cat:
				continue
			category_rows.setdefault(cat, []).append({
				'Label':  row['Label'].strip(),
				'Points': int(row['Points'].strip()),
			})
	for cat, rows in category_rows.items():
		counts = Counter(r['Label'] for r in rows)
		seen: dict = defaultdict(int)
		for row in rows:
			lbl = row['Label']
			if counts[lbl] > 1:
				seen[lbl] += 1
				row['Label'] = f"{lbl}{seen[lbl]}"
	return category_rows


def collect_scores(results_dir: str, rubric_data: dict) -> dict:
	model_scores: dict = {}

	for model_dir in sorted(os.listdir(results_dir)):
		model_path = os.path.join(results_dir, model_dir)
		if not os.path.isdir(model_path):
			continue
		json_files = [f for f in os.listdir(model_path) if f.endswith('.json')]
		if not json_files:
			continue

		json_path = os.path.join(model_path, json_files[0])
		with open(json_path, encoding='utf-8') as f:
			data = json.load(f)

		total_actual = 0
		total_max    = 0
		class_actual: dict = defaultdict(int)
		class_max:    dict = defaultdict(int)

		for item in data:
			ai         = item.get('AI_grade', {})
			high_class = item.get('high_class', 'Unknown')
			for row in rubric_data.get(high_class, []):
				score = ai.get(row['Label'])
				if score is not None:
					total_actual           += score
					total_max              += row['Points']
					class_actual[high_class] += score
					class_max[high_class]    += row['Points']

		short = make_short_name(model_dir)
		entry: dict = {
			'total': total_actual / total_max if total_max > 0 else 0
		}
		for hc in class_actual:
			entry[hc] = class_actual[hc] / class_max[hc] if class_max[hc] > 0 else 0

		model_scores[short] = entry
		print(f"  {short}: total={entry['total']:.1%}  ({json_files[0]})")

	return model_scores


def bar_chart(models: list, ratios: list, title: str, save_path: str, color: str = 'steelblue'):
	fig, ax = plt.subplots(figsize=(max(6, len(models) * 1.3), 5))
	bars = ax.bar(models, ratios, color=color)
	ax.set_ylim(0, 1)
	ax.set_ylabel('Score Ratio (Actual / Max)', fontsize=10)
	ax.set_title(title, fontsize=12, fontweight='bold')
	for bar, val in zip(bars, ratios):
		ax.text(
			bar.get_x() + bar.get_width() / 2,
			val + 0.01,
			f"{val:.1%}",
			ha='center', fontsize=9
		)
	plt.xticks(rotation=20, ha='right', fontsize=9)
	plt.tight_layout()
	fig.savefig(save_path, bbox_inches='tight', dpi=150)
	plt.close(fig)
	print(f"Saved: {save_path}")


def main(csv_path: str, res_dir: str):
	rubric_data  = build_rubric_data(csv_path)
	print("Reading model results...")
	model_scores = collect_scores(res_dir, rubric_data)

	if not model_scores:
		print("No model results found.")
		return

	all_classes = sorted({
		k for entry in model_scores.values() for k in entry if k != 'total'
	})
	models = list(model_scores.keys())

	bar_chart(
		models,
		[model_scores[m]['total'] for m in models],
		title='Overall Score Ratio by Model',
		save_path=os.path.join(res_dir, 'compare_overall.png'),
	)

	for i, hc in enumerate(all_classes):
		hc_models  = [m for m in models if hc in model_scores[m]]
		hc_ratios  = [model_scores[m][hc] for m in hc_models]
		safe_name  = re.sub(r'[^\w]+', '_', hc).strip('_')
		bar_chart(
			hc_models,
			hc_ratios,
			title=f'Score Ratio by Model — {hc}',
			save_path=os.path.join(res_dir, f'compare_{safe_name}.png'),
		)

	print(f"\nAll charts saved to: {res_dir}")


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="final plotting")
	parser.add_argument('--rubric', default=default_csv,  help='Rubric CSV path')
	parser.add_argument('--results', default=results_dir, help='results path')
	args = parser.parse_args()
	main(args.rubric, args.results)
