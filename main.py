"""Mock Interviewer — a CLI technical interview with an AI interviewer.

Run: python main.py
"""

import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from interviewer import FeedbackError, Interviewer

ROOT = Path(__file__).parent
PROBLEMS_FILE = ROOT / "problems" / "problems.json"
SESSIONS_DIR = ROOT / "sessions"

DIFFICULTIES = ("easy", "medium", "hard")
DIMENSION_LABELS = {
    "communication": "Communication",
    "problem_solving": "Problem Solving",
    "technical_competency": "Technical Competency",
    "testing_and_verification": "Testing & Verification",
}
RECOMMENDATION_LABELS = {
    "strong_hire": "Strong Hire",
    "hire": "Hire",
    "lean_hire": "Lean Hire",
    "no_hire": "No Hire",
}


def load_problems() -> list[dict]:
    return json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))


def pick_problem(problems: list[dict], difficulty: str) -> dict:
    matches = [p for p in problems if p.get("difficulty") == difficulty]
    if not matches:
        print(f"(No {difficulty} problems found — picking from the full bank.)")
        matches = problems
    return random.choice(matches)


def prompt_difficulty() -> str:
    while True:
        choice = input("Choose a difficulty (easy / medium / hard): ").strip().lower()
        if choice in DIFFICULTIES:
            return choice
        print("Please type one of: easy, medium, hard.")


def print_banner() -> None:
    print("=" * 64)
    print("  MOCK INTERVIEWER")
    print("  A live technical interview with an AI interviewer.")
    print("=" * 64)
    print()
    print("Tips:")
    print("  - Talk through your thinking like you would in a real interview.")
    print("  - Ask clarifying questions before you code.")
    print("  - Type 'done' on its own line when you're finished to get feedback.")
    print("  - Type 'quit' to exit without feedback.")
    print()


def render_feedback(feedback: dict) -> None:
    print()
    print("=" * 64)
    print("  FEEDBACK")
    print("=" * 64)

    scores = feedback.get("scores", {})
    fb = feedback.get("feedback", {})
    for key, label in DIMENSION_LABELS.items():
        score = scores.get(key, "?")
        print(f"\n{label}: {score}/10")
        detail = fb.get(key)
        if detail:
            print(f"  {detail}")

    strengths = feedback.get("strengths") or []
    if strengths:
        print("\nStrengths:")
        for s in strengths:
            print(f"  + {s}")

    improvements = feedback.get("areas_to_improve") or []
    if improvements:
        print("\nAreas to improve:")
        for a in improvements:
            print(f"  - {a}")

    summary = feedback.get("overall_summary")
    if summary:
        print("\nOverall:")
        print(f"  {summary}")

    rec = feedback.get("recommendation")
    if rec:
        print(f"\nRecommendation: {RECOMMENDATION_LABELS.get(rec, rec)}")
    print("=" * 64)


def save_session(problem: dict, transcript: list[dict], feedback: dict | None) -> Path:
    SESSIONS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc)
    fname = f"{ts.strftime('%Y%m%d-%H%M%S')}-{problem['id']}.json"
    path = SESSIONS_DIR / fname
    record = {
        "timestamp": ts.isoformat(),
        "problem": {
            "id": problem["id"],
            "title": problem["title"],
            "difficulty": problem["difficulty"],
        },
        "transcript": transcript,
        "feedback": feedback,
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def run() -> None:
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set.")
        print("Copy .env.example to .env and add your key, then try again.")
        sys.exit(1)

    print_banner()

    problems = load_problems()
    difficulty = prompt_difficulty()
    problem = pick_problem(problems, difficulty)

    print(f"\nStarting a {difficulty} interview. Connecting you with your interviewer...\n")

    interviewer = Interviewer(problem)
    print(f"Interviewer: {interviewer.open()}\n")

    finished = False
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession interrupted. Exiting without feedback.")
            return

        if not user_input:
            continue

        command = user_input.lower()
        if command == "quit":
            print("\nExiting without feedback. See you next time.")
            return
        if command == "done":
            finished = True
            break

        try:
            reply = interviewer.chat(user_input)
        except Exception as exc:  # network / API errors shouldn't crash the loop
            print(f"\n[Error talking to the interviewer: {exc}]\n")
            continue
        print(f"\nInterviewer: {reply}\n")

    if not finished:
        return

    print("\nGenerating your feedback — hang tight...")
    feedback = None
    try:
        feedback = interviewer.get_feedback()
        render_feedback(feedback)
    except FeedbackError as exc:
        print(f"\n[Could not parse feedback: {exc}]")
    except Exception as exc:
        print(f"\n[Error generating feedback: {exc}]")

    try:
        path = save_session(problem, interviewer.messages, feedback)
        print(f"\nSession saved to {path.relative_to(ROOT)}")
    except Exception as exc:
        print(f"\n[Could not save session: {exc}]")


if __name__ == "__main__":
    run()
