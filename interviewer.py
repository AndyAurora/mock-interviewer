"""Claude API wrapper for the mock interviewer.

Exposes an ``Interviewer`` that maintains the live conversation (``chat``) and
generates calibrated end-of-session feedback (``get_feedback``).
"""

import json
import os
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-4-6"
PROMPTS_DIR = Path(__file__).parent / "prompts"
COMPANIES_DIR = PROMPTS_DIR / "companies"

# Selectable interviewer personas. Key -> display name. "generic" is the default
# company-agnostic screen; the rest override tone and emphasis per company.
COMPANIES = {
    "generic": "Generic",
    "palantir": "Palantir",
    "jane_street": "Jane Street",
    "google": "Google",
    "meta": "Meta",
}
DEFAULT_COMPANY = "generic"

# Max output tokens. Interview turns are short and conversational; feedback is a
# structured JSON report and needs more room.
CHAT_MAX_TOKENS = 1024
FEEDBACK_MAX_TOKENS = 2048

# Stage-direction user turns (the interviewer kickoff and proactive code
# observations) are prefixed with this so they can be filtered out of the
# feedback transcript — they aren't things the candidate actually said.
STAGE_PREFIX = "[The candidate"

# observe() returns exactly this (and nothing else) when a real interviewer
# would have nothing to say; the UI suppresses it.
SILENT_TOKEN = "[SILENT]"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_company_style(company: str) -> str:
    """Load a company's persona overlay, falling back to the generic default."""
    if company not in COMPANIES:
        company = DEFAULT_COMPANY
    path = COMPANIES_DIR / f"{company}.txt"
    if not path.exists():
        path = COMPANIES_DIR / f"{DEFAULT_COMPANY}.txt"
    return path.read_text(encoding="utf-8").strip()


def _build_problem_block(problem: dict) -> str:
    """Render a problem dict into the text injected into the interviewer prompt."""
    lines = [
        f"Title: {problem['title']}",
        f"Difficulty: {problem['difficulty']}",
        "",
        problem["prompt"],
    ]
    examples = problem.get("examples") or []
    if examples:
        lines.append("")
        lines.append("Examples:")
        lines.extend(f"  - {ex}" for ex in examples)
    return "\n".join(lines)


class Interviewer:
    """A single interview session backed by the Claude API."""

    def __init__(
        self, problem: dict, company: str = DEFAULT_COMPANY, model: str = MODEL
    ):
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.model = model
        self.problem = problem
        self.company = company if company in COMPANIES else DEFAULT_COMPANY
        self.messages: list[dict] = []

        persona = _load_prompt("interviewer.txt")
        self.system_prompt = persona.replace(
            "[[COMPANY_STYLE]]", _load_company_style(self.company)
        ).replace("[[PROBLEM_BLOCK]]", _build_problem_block(problem))

    def chat(self, user_message: str) -> str:
        """Send a candidate message, return the interviewer's reply."""
        self.messages.append({"role": "user", "content": user_message})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=CHAT_MAX_TOKENS,
            system=self.system_prompt,
            messages=self.messages,
        )

        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def open(self) -> str:
        """Kick off the interview: have the interviewer present the problem."""
        return self.chat(
            "[The candidate has just joined the call. Introduce yourself briefly "
            "and present the problem, then invite them to begin.]"
        )

    def observe(self, code: str) -> str | None:
        """Let the interviewer proactively react to the candidate's current code.

        The interviewer chimes in only when a real one naturally would; otherwise
        it stays silent and this returns ``None`` (leaving history untouched, so a
        silent observation costs nothing in the transcript).
        """
        probe = (
            "[The candidate is working quietly and has not addressed you directly. "
            "Their code editor currently shows:\n```\n"
            f"{code}\n```\n"
            "If — and only if — a real interviewer would naturally speak up right "
            "now, say that one short remark: nudge a bug you spot, ask about their "
            "approach or its time/space complexity, point at an edge case they seem "
            "to be missing, or ask them to explain what they're doing. Do not repeat "
            "a point you've already made. If there is genuinely nothing worth "
            f"interrupting for, reply with exactly {SILENT_TOKEN} and nothing else.]"
        )
        self.messages.append({"role": "user", "content": probe})

        response = self.client.messages.create(
            model=self.model,
            max_tokens=CHAT_MAX_TOKENS,
            system=self.system_prompt,
            messages=self.messages,
        )
        reply = "".join(b.text for b in response.content if b.type == "text").strip()

        if not reply or SILENT_TOKEN in reply:
            self.messages.pop()  # discard the probe — nothing was said
            return None

        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def _transcript(self) -> str:
        """Render the conversation as plain text for the evaluator."""
        lines = []
        for msg in self.messages:
            # Skip stage-direction turns (kickoff, proactive observations) so they
            # don't pollute scoring — they aren't things the candidate said.
            if msg["role"] == "user" and msg["content"].startswith(STAGE_PREFIX):
                continue
            speaker = "Interviewer" if msg["role"] == "assistant" else "Candidate"
            lines.append(f"{speaker}: {msg['content']}")
        return "\n\n".join(lines)

    def get_feedback(self) -> dict:
        """Generate calibrated, structured feedback for the session.

        Returns a parsed dict following the schema in prompts/feedback.txt. Raises
        ``FeedbackError`` if the model output cannot be parsed as JSON.
        """
        feedback_system = _load_prompt("feedback.txt")

        problem_block = _build_problem_block(self.problem)
        user_content = (
            f"## Problem posed\n\n{problem_block}\n\n"
            f"## Interview transcript\n\n{self._transcript()}\n\n"
            "Now produce the JSON evaluation."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=FEEDBACK_MAX_TOKENS,
            system=feedback_system,
            messages=[{"role": "user", "content": user_content}],
        )

        raw = "".join(b.text for b in response.content if b.type == "text").strip()
        return _parse_feedback(raw)


class FeedbackError(ValueError):
    """Raised when the model's feedback response is not valid JSON."""


def _parse_feedback(raw: str) -> dict:
    """Parse the model's response into a feedback dict, tolerating code fences."""
    text = raw.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence if the model added one.
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.startswith("json"):
            text = text[len("json"):]
        text = text.strip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost JSON object.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise FeedbackError(f"Could not parse feedback as JSON:\n{raw}")
