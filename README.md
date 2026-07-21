# Mock Interviewer

A CLI tool that simulates a realistic technical coding interview with an AI interviewer. You pick a difficulty, get a coding problem, converse with the interviewer in real time, and receive rigorous, calibrated feedback across four dimensions at the end.

Unlike a "grade my answer" tool, the interviewer behaves like a real person: it probes for clarifying questions, asks about time/space complexity before you code, pushes on edge cases without handing you the answer, and stays in character throughout. The feedback is evidence-grounded and honestly scored — not generic praise.

## How it works

1. Pick an interviewer persona (Generic, Palantir, Jane Street, Google, or Meta).
2. Pick a difficulty (`easy` / `medium` / `hard`).
3. A random problem is pulled from the problem bank.
4. The AI interviewer presents the problem and conducts a live conversation.
5. Type `done` when you're finished coding to trigger feedback generation.
6. Feedback is printed and saved as JSON in `sessions/`.

Type `quit` at any point to exit without feedback.

## Interviewer personas

Each company gets a distinct interviewing style layered on top of the shared
interview mechanics:

- **Palantir** — heavy emphasis on communication and real-world problem framing.
- **Jane Street** — precise, rigorous, correctness-and-invariants focused.
- **Google** — classic SWE: clean code, complexity analysis, scalability.
- **Meta** — fast-paced and pragmatic; ship, then iterate.
- **Generic** — a balanced, company-agnostic screen (the default).

## Feedback dimensions

Each session is scored 1–10 on:

- **Communication** — thinking out loud, clarifying questions, keeping the interviewer oriented.
- **Problem Solving** — quality of approach, insight, complexity analysis, trade-offs.
- **Technical Competency** — correctness and quality of the actual solution.
- **Testing & Verification** — tracing examples, edge cases, catching your own bugs.

Plus concrete strengths, actionable areas to improve, an honest summary, and a hire recommendation.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
```

You'll need an Anthropic API key from https://console.anthropic.com/settings/keys.

## Running

**Web UI (recommended)** — a two-panel layout with a real code editor beside the
chat, so you can write multi-line code without every newline sending a turn:

```bash
python app.py
# then open http://127.0.0.1:5000
```

Write code freely in the editor (Enter is just a newline). Send a chat message to
talk to the interviewer — your current code is included automatically when it has
changed — or click **Share code** to show it without a message. Click **Done →
Get feedback** to end and grade the session.

**CLI** — simpler, no browser, but every Enter submits a turn:

```bash
python main.py
```

Both front-ends share the same backend (`interviewer.py`) and save sessions to
`sessions/`.

## Project layout

```
mock-interviewer/
├── app.py               # web UI — Flask server over the same backend
├── templates/
│   └── index.html       # two-panel web front-end (code editor + chat)
├── main.py              # CLI entry point — runs the session loop
├── interviewer.py       # Claude API wrapper — chat() and get_feedback()
├── prompts/
│   ├── interviewer.txt  # base interviewer mechanics (shared by all personas)
│   ├── feedback.txt     # system prompt for end-of-session feedback
│   └── companies/       # per-company persona overlays
│       ├── generic.txt
│       ├── palantir.txt
│       ├── jane_street.txt
│       ├── google.txt
│       └── meta.txt
├── problems/
│   └── problems.json    # problem bank (easy / medium / hard, tagged by topic)
├── sessions/            # saved session transcripts (gitignored)
├── requirements.txt
├── .env.example
└── README.md
```

## Stack

- Python 3.11+
- Anthropic API (`claude-sonnet-4-6`)
- `python-dotenv` for env management
- No frameworks — plain Python CLI.
