# CLAUDE.md — Mock Interviewer

## What this project is

A CLI tool that simulates a realistic technical interview using an AI interviewer. The user is prompted with a coding problem, converses with an AI interviewer in real-time, and receives structured feedback across 4 dimensions at the end of the session.

Built by Andy Cui (Stanford CS/Math, rising junior) as a portfolio project. Andy has experience building LLM evaluation pipelines at Zoom (human eval, LLM-as-judge, inter-rater reliability). That background informs the design — the feedback system is meant to be rigorous and calibrated, not generic.

---

## Current state

The project is functional but just scaffolded. All core files exist:

```
mock-interviewer/
├── main.py              # entry point — runs the session loop
├── interviewer.py       # Claude API calls — chat() and get_feedback()
├── prompts/
│   ├── interviewer.txt  # system prompt for the AI interviewer persona
│   └── feedback.txt     # system prompt for end-of-session feedback
├── problems/
│   └── problems.json    # 5 problems (easy/medium) to start
├── sessions/            # saved session transcripts (gitignored)
├── requirements.txt     # anthropic, python-dotenv
├── .env.example
└── README.md
```

---

## How it works

1. User picks an interviewer persona (Generic / Palantir / Jane Street / Google / Meta)
2. User picks difficulty (easy/medium/hard)
3. A random problem is pulled from `problems/problems.json`
4. AI interviewer presents the problem and conducts a real-time conversation
5. User types `done` when finished coding → triggers feedback generation
6. Feedback is printed and saved as JSON in `sessions/`

The base interviewer mechanics (in `prompts/interviewer.txt`) are designed to:
- Probe clarifying questions if the user jumps straight to coding
- Ask about time/space complexity before they code
- Push back on edge cases without giving away answers
- Stay in character — no breaking the fourth wall

Company personas layer on top of the base via overlay files in
`prompts/companies/` (one per company). The base holds the shared mechanics and
exposes a `[[COMPANY_STYLE]]` slot; `Interviewer(problem, company=...)` composes
the two, so a mechanics change only touches `interviewer.txt`.

---

## What to build next

These are roughly prioritized:

### 1. Progress tracking across sessions
Right now sessions are saved as JSON but nothing is analyzed. Build a `progress.py` that:
- Reads all past sessions
- Tracks scores over time per dimension
- Shows trends ("your communication score improved from 5.2 → 7.1 over last 10 sessions")

### 2. Expand problem bank
The bank now has 8 problems across easy/medium/hard, tagged by topic. Still want:
- More problems at every difficulty level
- User should be able to filter by topic (tags already exist in `problems.json`)

### 3. Voice mode
Use Whisper API for speech-to-text so the user can speak instead of type. This makes it feel much closer to a real interview. Lower priority — get the core loop polished first.

### 4. Web interface
Eventually move from CLI to a simple web app (Flask or FastAPI backend, simple HTML/JS frontend). Not a priority yet.

---

## Design principles

- **Realism over features** — the interviewer should feel like a real person. Prioritize prompt quality over adding features.
- **Specific feedback over generic** — "your solution had O(n²) complexity when O(n) was possible using a hashmap" is good. "Good job!" is not.
- **CLI first** — keep it simple and fast to iterate. Don't add UI complexity until the core loop is solid.

---

## Stack

- Python 3.11+
- Anthropic API (`claude-sonnet-4-6`)
- `python-dotenv` for env management
- No frameworks — plain Python CLI for now

---

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
# add ANTHROPIC_API_KEY to .env
python main.py
```
