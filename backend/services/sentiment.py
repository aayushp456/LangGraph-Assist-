from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict


@dataclass
class SentimentResult:
    label: str
    score: float


class SentimentService:
    def analyze(self, text: str) -> SentimentResult:
        t = (text or "").lower()

        positive = [
            "thank",
            "thanks",
            "great",
            "awesome",
            "love",
            "good",
            "resolved",
            "perfect",
            "amazing",
        ]
        negative = [
            "not working",
            "doesn't work",
            "cant",
            "can't",
            "unable",
            "broken",
            "error",
            "issue",
            "problem",
            "failed",
            "fail",
            "refund",
            "urgent",
            "asap",
            "immediately",
            "blocked",
            "frustrat",
        ]

        pos_hits = sum(1 for w in positive if w in t)
        neg_hits = sum(1 for w in negative if w in t)

        # Extra negative weight for lots of punctuation / caps (light heuristic)
        exclam = t.count("!")
        caps = len(re.findall(r"\b[A-Z]{3,}\b", text or ""))
        neg_hits += 1 if exclam >= 2 else 0
        neg_hits += 1 if caps >= 1 else 0

        total = pos_hits + neg_hits
        if total == 0:
            return SentimentResult(label="neutral", score=0.5)

        # Score is confidence-like, not probability
        score = max(pos_hits, neg_hits) / total

        if neg_hits > pos_hits:
            return SentimentResult(label="negative", score=score)
        if pos_hits > neg_hits:
            return SentimentResult(label="positive", score=score)
        return SentimentResult(label="neutral", score=0.5)

    def as_dict(self, text: str) -> Dict[str, float | str]:
        r = self.analyze(text)
        return {"label": r.label, "score": float(r.score)}
