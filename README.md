# WildfireDesk FireBench

This repository holds two related projects and the code they share:

| Folder | What it is | Start here |
| --- | --- | --- |
| [`sage/`](sage/README.md) | **Sage**, a civic helpdesk for wildfire recovery. Runs as a web app or a command-line chatbot. | [sage/README.md](sage/README.md) |
| [`civicbench/`](civicbench/README.md) | **CivicBench**, a benchmark for evaluating civic AI systems. Includes LLM judges, the Orchid simulated user, and report generation. | [civicbench/README.md](civicbench/README.md) |
| [`shared/`](shared/README.md) | Code both projects use: the LLM proxy client (`llmproxy`) and the chatbot interface (`civic_chatbot.py`). | [shared/README.md](shared/README.md) |
| `archive/` | Files that appear unused. Nothing in the code reads them. Kept until the team decides what to delete. | [archive/README.md](archive/README.md) |

## First-time setup

Do this once per computer. Run the commands from the repository root.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./shared
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

## Open items before handoff

- **Owners:** the business, delivery, and support owners are not named yet. Fill these in before anyone relies on the project: [ ] business owner, [ ] delivery owner, [ ] support owner.
- **Hosting:** the org's policy says hosted apps must run on Cloudflare Workers. Sage is a Flask app and is not set up for that yet.
- **Old `.env` at the repo root:** it has been copied into `sage/.env` and `civicbench/.env`. Delete the root copy once you've confirmed both projects run.
- **Discord bot token:** it was in an old file in git history. It needs to be rotated, because deleting the file doesn't remove it from history.
- **Pinned versions:** the requirements files pin the versions currently installed. They have not been checked against the org's 7-day release-age rule.
