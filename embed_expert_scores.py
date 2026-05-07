import json

with open('eval/data/civic_judge.json', 'r', encoding='utf-8') as f:
	data = json.load(f)
score_mapping = {
	"001": [4, 5, 3, 0, 2, 0],
	"002": [4, 5, 3, 2, 1, 0],
	"021": [3, 4, 3, 3, 1, 1],
	"041": [5, 5, 4, 3, 2, 1],
	"081": [3, 3, 3, 1, 1, 1],
	"101": [3, 4, 4, 3, 1, 2],
	"121": [5, 3, 3, 3, 2, 2],
}

updated = []
for entry in data:
	id_ = entry["_id"]
	if id_ in score_mapping:
		keys = list(entry["Expert_grade"].keys())
		scores = score_mapping[id_]
		assert len(keys) == len(scores), f"_id {id_}: keys={len(keys)}, scores={len(scores)}"
		for k, v in zip(keys, scores):
			entry["Expert_grade"][k] = v
		updated.append(id_)

with open('eval/data/civic_judge.json', 'w', encoding='utf-8') as f:
	json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
	pass
