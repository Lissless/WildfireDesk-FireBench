import json
import csv
import argparse
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')


def build_category_labels(csv_path):
	"""从CSV读取每个Category对应的Label列表，自动为重复Label添加数字后缀。"""
	category_labels = {}

	with open(csv_path, encoding='utf-8') as f:
		reader = csv.DictReader(f)
		for row in reader:
			cat = row['Category'].strip()
			label = row['Label'].strip()
			# 跳过空白行
			if not cat:
				continue
			if cat not in category_labels:
				category_labels[cat] = []
			category_labels[cat].append(label)

	# 检测重复Label并添加数字后缀
	result = {}
	for cat, labels in category_labels.items():
		counts = Counter(labels)
		seen = defaultdict(int)
		new_labels = []
		for label in labels:
			if counts[label] > 1:
				seen[label] += 1
				new_labels.append(f"{label}{seen[label]}")
			else:
				new_labels.append(label)
		result[cat] = new_labels

	return result


HIGH_CLASS_FIXES = {
	"Organizing and Associational Engagement": "Organizing & Associational Engagement"
}


def update_json(json_path, category_labels):
	"""读取JSON，更新每个元素的high_class和Expert_grade的key，写回文件。"""
	with open(json_path, encoding='utf-8') as f:
		data = json.load(f)

	stats = defaultdict(int)

	for element in data:
		# 修正high_class名称不一致
		hc = element.get('high_class', '')
		if hc in HIGH_CLASS_FIXES:
			element['high_class'] = HIGH_CLASS_FIXES[hc]
			hc = element['high_class']

		# 替换Expert_grade的key
		if hc in category_labels:
			labels = category_labels[hc]
			old_values = list(element.get('Expert_grade', {}).values())
			new_expert_grade = {}
			for i, label in enumerate(labels):
				new_expert_grade[label] = old_values[i] if i < len(old_values) else ""
			element['Expert_grade'] = new_expert_grade
			stats[hc] += 1
		else:
			print(f"警告：未找到匹配的Category，high_class='{hc}'，id='{element.get('_id')}'")

	with open(json_path, 'w', encoding='utf-8') as f:
		json.dump(data, f, ensure_ascii=False, indent=2)

	# 打印处理统计
	print(f"处理完成，共更新 {len(data)} 条记录：")
	for cat, count in sorted(stats.items()):
		print(f"  {cat}: {count} 条")


def main(csv_path, json_path):
	category_labels = build_category_labels(csv_path)
	print("已读取CSV中的Category->Label映射：")
	for cat, labels in sorted(category_labels.items()):
		print(f"  {cat}: {labels}")
	print()
	update_json(json_path, category_labels)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="根据CSV中的Label值更新civic_judge.json中Expert_grade的key")
	parser.add_argument(
		"--csv",
		default="eval/data/civicbench_rubrics.xlsx - Rubric Questions Full.csv",
		help="CSV rubric文件路径"
	)
	parser.add_argument(
		"--json",
		default="eval/data/civic_judge.json",
		help="civic_judge.json文件路径"
	)
	args = parser.parse_args()
	main(args.csv, args.json)
