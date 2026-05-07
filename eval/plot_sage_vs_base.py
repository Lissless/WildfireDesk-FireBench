import os
import sys
import json
import csv
import argparse
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
	sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[union-attr]

base_dir = os.path.dirname(__file__)

DEFAULT_SAGE = os.path.join(
	base_dir, 'results_sage',
	'us.meta.llama4-maverick-17b-instruct-v1-0',
	'civic_judge_us.meta.llama4-maverick-17b-instruct-v1-0.json',
)
DEFAULT_BASE = os.path.join(
	base_dir, 'results',
	'us.meta.llama4-maverick-17b-instruct-v1-0',
	'civic_judge_us.meta.llama4-maverick-17b-instruct-v1-0.json',
)
DEFAULT_RUBRIC = os.path.join(
	base_dir, 'data',
	'civicbench_rubrics.xlsx - Rubric Questions Full.csv',
)

HIGH_CLASS_ORDER = [
	'Civic & Political Knowledge',
	'Civic Information Access & Media Literacy',
	'Formal Participation in Government Processes',
	'Civic Communication & Deliberation',
	'Organizing & Associational Engagement',
	'Community Problem-Solving & Public Work',
	'Relationships & Trust',
]

HIGH_CLASS_SHORT = {
	'Civic & Political Knowledge':                 'Civic &\nPolitical\nKnowledge',
	'Civic Information Access & Media Literacy':   'Civic Info\nAccess &\nMedia Literacy',
	'Formal Participation in Government Processes':'Formal\nParticipation',
	'Civic Communication & Deliberation':          'Civic Comm.\n& Deliberation',
	'Organizing & Associational Engagement':       'Organizing &\nAssociational\nEngagement',
	'Community Problem-Solving & Public Work':     'Community\nProblem-Solving\n& Public Work',
	'Relationships & Trust':                       'Relationships\n& Trust',
}

DIFF_ORDER = ['Easy', 'Medium', 'Hard', 'Overall']


def build_rubric_data(csv_path: str) -> dict:
	from collections import Counter
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


def load_scores(json_path: str, rubric_data: dict) -> dict:
	with open(json_path, encoding='utf-8') as f:
		data = json.load(f)

	by_diff:  dict = defaultdict(lambda: [0, 0])
	by_class: dict = defaultdict(lambda: [0, 0])
	overall = [0, 0]

	for item in data:
		diff       = item.get('difficulty', '').strip()
		high_class = item.get('high_class', '').strip()
		ai         = item.get('AI_grade', {})

		rubric = rubric_data.get(high_class, [])
		if not rubric:
			continue

		actual = 0
		max_v  = 0
		for row in rubric:
			score = ai.get(row['Label'])
			if isinstance(score, (int, float)):
				actual += score
				max_v  += row['Points']

		if max_v == 0:
			continue
		if diff in ('Easy', 'Medium', 'Hard'):
			by_diff[diff][0] += actual
			by_diff[diff][1] += max_v

		by_class[high_class][0] += actual
		by_class[high_class][1] += max_v

		if diff in ('Easy', 'Medium', 'Hard'):
			overall[0] += actual
			overall[1] += max_v

	by_diff['Overall'] = overall
	return {'by_diff': dict(by_diff), 'by_class': dict(by_class)}


def ratio(scores: list) -> float:
	return scores[0] / scores[1] if scores[1] > 0 else 0.0


def plot_difficulty_chart(sage: dict, base: dict, out_path: str):
	sage_d = sage['by_diff']
	base_d = base['by_diff']

	labels  = DIFF_ORDER
	sage_r  = [ratio(sage_d.get(d, [0, 1])) for d in labels]
	base_r  = [ratio(base_d.get(d, [0, 1])) for d in labels]

	x     = np.arange(len(labels))
	width = 0.35

	fig, ax = plt.subplots(figsize=(8, 5))
	bars1 = ax.bar(x - width / 2, sage_r, width, label='Sage',  color='#4C72B0', alpha=0.88)
	bars2 = ax.bar(x + width / 2, base_r, width, label='Base',  color='#DD8452', alpha=0.88)

	ax.set_xticks(x)
	ax.set_xticklabels(labels, fontsize=11)
	ax.set_ylim(0, 1.12)
	ax.set_ylabel('Score Ratio (Actual / Max)', fontsize=11)
	ax.set_title(
		'Sage vs Base — Score Ratio by Difficulty\n(Llama4-Maverick-17B, AI Grade)',
		fontsize=12, fontweight='bold',
	)
	ax.legend(fontsize=10)
	ax.grid(axis='y', alpha=0.3)

	for bar, val in zip(bars1, sage_r):
		ax.text(bar.get_x() + bar.get_width() / 2, val + 0.012,
		        f'{val:.1%}', ha='center', va='bottom', fontsize=9, color='#2c4a7c')
	for bar, val in zip(bars2, base_r):
		ax.text(bar.get_x() + bar.get_width() / 2, val + 0.012,
		        f'{val:.1%}', ha='center', va='bottom', fontsize=9, color='#8b4a1a')

	fig.tight_layout()
	fig.savefig(out_path, dpi=150, bbox_inches='tight')
	plt.close(fig)
	print(f'Saved: {out_path}')


def plot_highclass_chart(sage: dict, base: dict, out_path: str):
	sage_c = sage['by_class']
	base_c = base['by_class']

	labels     = HIGH_CLASS_ORDER
	short_lbls = [HIGH_CLASS_SHORT[hc] for hc in labels]
	sage_r     = [ratio(sage_c.get(hc, [0, 1])) for hc in labels]
	base_r     = [ratio(base_c.get(hc, [0, 1])) for hc in labels]

	x     = np.arange(len(labels))
	width = 0.35

	fig, ax = plt.subplots(figsize=(14, 5))
	bars1 = ax.bar(x - width / 2, sage_r, width, label='Sage',  color='#4C72B0', alpha=0.88)
	bars2 = ax.bar(x + width / 2, base_r, width, label='Base',  color='#DD8452', alpha=0.88)

	ax.set_xticks(x)
	ax.set_xticklabels(short_lbls, fontsize=8.5)
	ax.set_ylim(0, 1.15)
	ax.set_ylabel('Score Ratio (Actual / Max)', fontsize=11)
	ax.set_title(
		'Sage vs Base — Score Ratio by High Class\n(Llama4-Maverick-17B, AI Grade)',
		fontsize=12, fontweight='bold',
	)
	ax.legend(fontsize=10)
	ax.grid(axis='y', alpha=0.3)

	for bar, val, hc in zip(bars1, sage_r, labels):
		label_txt = 'N/A' if val == 0.0 and hc not in sage_c else f'{val:.1%}'
		ax.text(bar.get_x() + bar.get_width() / 2, val + 0.012,
		        label_txt, ha='center', va='bottom', fontsize=8, color='#2c4a7c')
	for bar, val in zip(bars2, base_r):
		ax.text(bar.get_x() + bar.get_width() / 2, val + 0.012,
		        f'{val:.1%}', ha='center', va='bottom', fontsize=8, color='#8b4a1a')

	fig.tight_layout()
	fig.savefig(out_path, dpi=150, bbox_inches='tight')
	plt.close(fig)
	print(f'Saved: {out_path}')


def main(sage_path: str, base_path: str, rubric_path: str, out_dir: str):
	rubric_data = build_rubric_data(rubric_path)
	sage_scores = load_scores(sage_path, rubric_data)
	base_scores = load_scores(base_path, rubric_data)

	os.makedirs(out_dir, exist_ok=True)

	plot_difficulty_chart(
		sage_scores, base_scores,
		os.path.join(out_dir, 'sage_vs_base_by_difficulty.png'),
	)
	plot_highclass_chart(
		sage_scores, base_scores,
		os.path.join(out_dir, 'sage_vs_base_by_highclass.png'),
	)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Sage vs Base')
	parser.add_argument('--sage',   default=DEFAULT_SAGE)
	parser.add_argument('--base',   default=DEFAULT_BASE)
	parser.add_argument('--rubric', default=DEFAULT_RUBRIC)
	parser.add_argument('--out',    default=base_dir)
	args = parser.parse_args()
	main(args.sage, args.base, args.rubric, args.out)
