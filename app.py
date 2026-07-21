"""Local web front-end for the mock interviewer.

A thin Flask wrapper over the same backend the CLI uses (``interviewer.py``).
It serves a two-panel UI — a persistent code editor beside the live chat — so
you can write multi-line code without every newline firing a turn.

Run:  python app.py   then open http://127.0.0.1:5000

Single-user local tool: one interview is held in module state at a time.
"""

import os
import sys

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from interviewer import COMPANIES, DEFAULT_COMPANY, FeedbackError, Interviewer
from main import DIFFICULTIES, load_problems, pick_problem, save_session

load_dotenv()

app = Flask(__name__)

# The single active interview (this is a local, single-user tool).
STATE: dict = {
    "interviewer": None,
    "problem": None,
    "company": DEFAULT_COMPANY,
    "last_code": "",  # last code snapshot already shared with the interviewer
}


@app.get("/")
def index():
    return render_template(
        "index.html",
        companies=COMPANIES,
        difficulties=list(DIFFICULTIES),
        default_company=DEFAULT_COMPANY,
    )


@app.post("/api/start")
def start():
    data = request.get_json(force=True, silent=True) or {}
    company = data.get("company", DEFAULT_COMPANY)
    difficulty = data.get("difficulty", "medium")
    if difficulty not in DIFFICULTIES:
        difficulty = "medium"

    problem = pick_problem(load_problems(), difficulty)
    interviewer = Interviewer(problem, company=company)

    try:
        opening = interviewer.open()
    except Exception as exc:  # surface API/auth errors to the UI
        return jsonify({"error": f"Could not reach the interviewer: {exc}"}), 502

    STATE.update(
        interviewer=interviewer,
        problem=problem,
        company=interviewer.company,
        last_code="",
    )
    return jsonify(
        {
            "problem": {
                "title": problem["title"],
                "difficulty": problem["difficulty"],
                "prompt": problem["prompt"],
                "examples": problem.get("examples", []),
            },
            "message": opening,
        }
    )


def _compose_message(text: str, code: str) -> str | None:
    """Build the candidate turn from chat text + a code snapshot.

    The code block is included only when the code is non-empty and has changed
    since it was last shared, so the interviewer sees fresh code without the
    editor's full contents being re-sent every turn.
    """
    text = (text or "").strip()
    code = (code or "").rstrip()
    code_changed = bool(code) and code != STATE["last_code"]

    parts = []
    if text:
        parts.append(text)
    if code_changed:
        parts.append(f"Here's my current code in the editor:\n```\n{code}\n```")
        STATE["last_code"] = code

    if not parts:
        return None
    return "\n\n".join(parts)


@app.post("/api/message")
def message():
    interviewer = STATE["interviewer"]
    if interviewer is None:
        return jsonify({"error": "No active interview. Start one first."}), 400

    data = request.get_json(force=True, silent=True) or {}
    user_message = _compose_message(data.get("text", ""), data.get("code", ""))
    if user_message is None:
        return jsonify(
            {"error": "Nothing to send — type a message or change your code."}
        ), 400

    try:
        reply = interviewer.chat(user_message)
    except Exception as exc:
        return jsonify({"error": f"Interviewer error: {exc}"}), 502
    return jsonify({"message": reply})


@app.post("/api/feedback")
def feedback():
    interviewer = STATE["interviewer"]
    if interviewer is None:
        return jsonify({"error": "No active interview."}), 400

    data = request.get_json(force=True, silent=True) or {}
    # Make sure the candidate's final code is in the transcript before grading,
    # even if they never clicked "Share code" after their last edits.
    final_code = (data.get("code") or "").rstrip()
    if final_code and final_code != STATE["last_code"]:
        interviewer.messages.append(
            {
                "role": "user",
                "content": f"Here's my final code:\n```\n{final_code}\n```",
            }
        )
        STATE["last_code"] = final_code

    try:
        result = interviewer.get_feedback()
    except FeedbackError as exc:
        return jsonify({"error": f"Could not parse feedback: {exc}"}), 502
    except Exception as exc:
        return jsonify({"error": f"Feedback error: {exc}"}), 502

    saved = None
    try:
        path = save_session(
            STATE["problem"], STATE["company"], interviewer.messages, result
        )
        saved = path.name
    except Exception:
        pass

    return jsonify({"feedback": result, "saved": saved})


def main() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set.")
        print("Copy .env.example to .env and add your key, then try again.")
        sys.exit(1)
    print("Mock Interviewer web UI running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
