# WildfireDesk FireBench

This repository holds two related projects and the code they share:

| Folder | What it is | Start here |
| --- | --- | --- |
| [`sage/`](sage/README.md) | **Sage**, a civic helpdesk for wildfire recovery. Runs as a web app or a command-line chatbot. | [sage/README.md](sage/README.md) |
| [`civicbench/`](civicbench/README.md) | **CivicBench**, a benchmark for evaluating civic AI systems. Includes LLM judges, the Orchid simulated user, and report generation. | [civicbench/README.md](civicbench/README.md) |
| [`shared/`](shared/README.md) | Code both projects use: the LLM proxy client (`llmproxy`) and the chatbot interface (`civic_chatbot.py`). Nothing to install, since both projects find it automatically. | [shared/README.md](shared/README.md) |

## Prerequisites

- **Python 3.** Tested with Python 3.14.6. The pinned package versions may not install on much older versions.
- **Git**
- **An LLM proxy API key and endpoint URL.** Get both from the project owner.

## Quick start: run Sage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r sage/requirements.txt
cp sage/.env.example sage/.env     # then fill in the two values
cd sage
python app.py                      # open http://localhost:5000 once uploads finish
```

## First-time setup

Do this once per computer. Run the commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Then install the packages for the project you want to run:

```bash
# Sage only
pip install -r sage/requirements.txt

# CivicBench (also installs what Sage needs)
pip install -r civicbench/requirements.txt
```

Then create a `.env` file in each project folder you use. Copy the template and fill in your two values:

```bash
cp sage/.env.example sage/.env
cp civicbench/.env.example civicbench/.env
```

Each `.env` needs `LLMPROXY_API_KEY` and `LLMPROXY_ENDPOINT`. Get both from the project owner.

## Ground rules

- **Run each project's commands from that project's folder.** For example, `cd sage` before `python app.py`. The `.env` file is read from the folder you run in.
- **Keep `.env` files out of git.** They hold API keys. The `.gitignore` already excludes them, and `.env.example` is the template that is committed.
- **Use the project READMEs for day-to-day work.** This page only covers setup and layout.