import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from scipy.stats import pearsonr

matplotlib.rcParams['font.family'] = 'DejaVu Sans'

MAX_SCORES = {
	"001": {"Factual & Procedural Accuracy1": 5, "Factual & Procedural Accuracy2": 5,
	        "Clarity & Usability": 3, "Contextual Relevance": 3,
	        "Actionability": 3, "Civic Responsibility": 1},
	"002": {"Factual & Procedural Accuracy1": 5, "Factual & Procedural Accuracy2": 5,
	        "Clarity & Usability": 3, "Contextual Relevance": 3,
	        "Actionability": 3, "Civic Responsibility": 1},
	"021": {"Actionability1": 5, "Factual & Procedural Accuracy": 5,
	        "Actionability2": 4, "Clarity & Usability": 3,
	        "Actionability3": 2, "Civic Responsibility": 1},
	"041": {"Contextual Relevance": 5, "Factual & Procedural Accuracy1": 5,
	        "Actionability": 4, "Factual & Procedural Accuracy2": 3,
	        "Completeness": 2, "Civic Responsibility": 1},
	"081": {"Contextual Relevance": 5, "Actionability1": 5,
	        "Actionability2": 4, "Completeness1": 3,
	        "Civic Responsibility": 2, "Completeness2": 1},
	"101": {"Contextual Relevance1": 3, "Civic Responsibility1": 5,
	        "Actionability": 5, "Contextual Relevance2": 3,
	        "Civic Responsibility2": 2, "Completeness": 2},
	"121": {"Contextual Relevance": 5, "Actionability": 4,
	        "Civic Responsibility1": 3, "Civic Responsibility2": 4,
	        "Civic Responsibility3": 2, "Civic Responsibility4": 2},
}

TARGET_IDS = set(MAX_SCORES.keys())

EXCLUDE_MODELS = {"us.meta.llama3-3-70b-instruct-v1-0"}

QUESTION_LABELS = {
	"001": "Q#001\nCivic & Political Knowledge",
	"002": "Q#002\nCivic & Political Knowledge",
	"021": "Q#021\nCivic Info Access &\nMedia Literacy",
	"041": "Q#041\nFormal Participation\nin Gov. Processes",
	"081": "Q#081\nOrganizing &\nAssociational Engagement",
	"101": "Q#101\nCommunity Problem-\nSolving & Public Work",
	"121": "Q#121\nRelationships & Trust",
}

MODEL_SHORT = {
	"4o-mini": "GPT-4o-mini",
	"gpt-4.1-mini": "GPT-4.1-mini",
	"gpt-5-nano": "GPT-5-nano",
	"us.anthropic.claude-3-haiku-20240307-v1-0": "Claude-3-Haiku",
	"google.gemma-3-27b-it": "Gemma-3-27B",
	"gemini-2.5-flash-lite": "Gemini-2.5-Flash-Lite",
	"us.meta.llama3-1-8b-instruct-v1-0": "Llama3.1-8B",
	"us.meta.llama3-2-90b-instruct-v1-0": "Llama3.2-90B",
	"us.meta.llama3-3-70b-instruct-v1-0": "Llama3.3-70B",
	"us.meta.llama4-scout-17b-instruct-v1-0": "Llama4-Scout",
	"us.meta.llama4-maverick-17b-instruct-v1-0": "Llama4-Maverick",
}

def load_expert_grades(civic_path):
	with open(civic_path, encoding="utf-8") as f:
		data = json.load(f)
	result = {}
	for entry in data:
		qid = entry["_id"]
		if qid in TARGET_IDS:
			grades = entry.get("Expert_grade", {})
			if all(isinstance(v, (int, float)) for v in grades.values()):
				result[qid] = grades
	return result

def load_ai_grades(json_path):
	with open(json_path, encoding="utf-8") as f:
		data = json.load(f)
	result = {}
	for entry in data:
		qid = entry["_id"]
		if qid in TARGET_IDS and "AI_grade" in entry:
			result[qid] = entry["AI_grade"]
	return result

def compute_similarity(expert_grades, ai_grades):
	expert_norm, ai_norm = [], []
	expert_raw, ai_raw = [], []

	for qid in sorted(TARGET_IDS):
		if qid not in ai_grades or qid not in expert_grades:
			continue
		max_s = MAX_SCORES[qid]
		eg = expert_grades[qid]
		ag = ai_grades[qid]
		for rubric, max_v in max_s.items():
			ev = eg.get(rubric, 0) or 0
			av = ag.get(rubric, 0) or 0
			expert_norm.append(ev / max_v)
			ai_norm.append(av / max_v)
			expert_raw.append(ev)
			ai_raw.append(av)

	if not expert_norm:
		return None, None

	mae = float(np.mean(np.abs(np.array(ai_norm) - np.array(expert_norm))))
	norm_mae_sim = 1.0 - mae

	if len(set(expert_raw)) > 1 and len(set(ai_raw)) > 1:
		r, _ = pearsonr(expert_raw, ai_raw)
	else:
		r = float("nan")

	return norm_mae_sim, r

def compute_per_question_similarity(expert_grades, ai_grades):
	per_q = {}
	for qid in sorted(TARGET_IDS):
		if qid not in ai_grades or qid not in expert_grades:
			per_q[qid] = float("nan")
			continue
		max_s = MAX_SCORES[qid]
		eg = expert_grades[qid]
		ag = ai_grades[qid]
		diffs = []
		for rubric, max_v in max_s.items():
			ev = eg.get(rubric, 0) or 0
			av = ag.get(rubric, 0) or 0
			diffs.append(abs(ev / max_v - av / max_v))
		per_q[qid] = 1.0 - float(np.mean(diffs)) if diffs else float("nan")
	return per_q

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
civic_path = os.path.join(base, "eval", "data", "civic_judge.json")
results_dir = os.path.join(base, "eval", "results")
out_dir = os.path.join(base, "eval", "results")

expert_grades = load_expert_grades(civic_path)
print(f"Expert grades loaded: {len(expert_grades)} questions")

models_data = []
per_q_data = {}

for model_folder in sorted(os.listdir(results_dir)):
	if model_folder in EXCLUDE_MODELS:
		continue
	folder_path = os.path.join(results_dir, model_folder)
	if not os.path.isdir(folder_path):
		continue
	json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
	if not json_files:
		continue
	json_path = os.path.join(folder_path, json_files[0])
	ai_grades = load_ai_grades(json_path)
	sim, r = compute_similarity(expert_grades, ai_grades)
	per_q = compute_per_question_similarity(expert_grades, ai_grades)
	short_name = MODEL_SHORT.get(model_folder, model_folder)
	models_data.append({
		"folder": model_folder,
		"name": short_name,
		"norm_mae_sim": sim,
		"pearson_r": r,
	})
	per_q_data[short_name] = per_q
	print(f"  {short_name}: MAE-sim={sim:.3f}, Pearson r={r:.3f}")

models_data.sort(key=lambda x: x["norm_mae_sim"] if x["norm_mae_sim"] else 0, reverse=True)
names = [m["name"] for m in models_data]
mae_sims = [m["norm_mae_sim"] for m in models_data]
pearson_rs = [m["pearson_r"] for m in models_data]

fig1, ax1 = plt.subplots(figsize=(12, 5))

x = np.arange(len(names))
width = 0.38

bars1 = ax1.bar(x - width/2, mae_sims, width, label="1 − Normalized MAE", color="#4C72B0", alpha=0.88)
bars2 = ax1.bar(x + width/2, pearson_rs, width, label="Pearson r", color="#DD8452", alpha=0.88)

ax1.set_xticks(x)
ax1.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
ax1.set_ylabel("Similarity Score", fontsize=11)
ax1.set_title("AI Grader vs Expert Grade — Overall Similarity\n(10 models, 7 questions, per-rubric comparison)",
              fontsize=12, fontweight="bold")
ax1.set_ylim(0.5, 1.05)
ax1.legend(fontsize=10)
ax1.grid(axis="y", alpha=0.3)

for bar in bars1:
	h = bar.get_height()
	ax1.text(bar.get_x() + bar.get_width()/2, h + 0.005, f"{h:.3f}",
	         ha="center", va="bottom", fontsize=7.5, color="#2c4a7c")
for bar in bars2:
	h = bar.get_height()
	ax1.text(bar.get_x() + bar.get_width()/2, h + 0.005, f"{h:.3f}",
	         ha="center", va="bottom", fontsize=7.5, color="#8b4a1a")

fig1.tight_layout()
out1 = os.path.join(out_dir, "expert_ai_similarity_bar.png")
fig1.savefig(out1, dpi=150, bbox_inches="tight")
print(f"Bar chart saved to: {out1}")

q_ids = sorted(TARGET_IDS)
y_labels = [QUESTION_LABELS[q] for q in q_ids]

heatmap_data = np.array([
	[per_q_data[n][qid] for qid in q_ids]
	for n in names
]).T  

fig2, ax2 = plt.subplots(figsize=(13, 6))

im = ax2.imshow(heatmap_data, aspect="auto", cmap="RdYlGn", vmin=0.4, vmax=1.0)
cbar = plt.colorbar(im, ax=ax2, shrink=0.85)
cbar.set_label("1 − Normalized MAE (per question)", fontsize=10)

ax2.set_xticks(range(len(names)))
ax2.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
ax2.set_yticks(range(len(q_ids)))
ax2.set_yticklabels(y_labels, fontsize=8.5)
ax2.set_title("Per-Question Similarity Heatmap (AI Grader vs Expert)\nX: Model  |  Y: Question Category",
              fontsize=12, fontweight="bold")

for i in range(len(q_ids)):
	for j in range(len(names)):
		val = heatmap_data[i, j]
		txt = f"{val:.2f}" if not np.isnan(val) else "N/A"
		brightness = val if not np.isnan(val) else 0.5
		color = "white" if brightness < 0.58 or brightness > 0.92 else "black"
		ax2.text(j, i, txt, ha="center", va="center", fontsize=8, color=color, fontweight="bold")

fig2.tight_layout()
out2 = os.path.join(out_dir, "expert_ai_similarity_heatmap.png")
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"Heatmap saved to: {out2}")
plt.show()

if __name__ == "__main__":
	pass
