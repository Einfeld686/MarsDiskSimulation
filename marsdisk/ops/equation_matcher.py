from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.linear_model import LogisticRegression
import joblib

from .doc_sync_agent import EquationEntry, InventoryRecord


@dataclass
class MatchSuggestion:
    eq_id: str
    file_path: str
    symbol: str
    score: float
    confidence: float | None = None
    priority: int | None = None


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _equation_text(entry: EquationEntry) -> str:
    parts = [entry.eq_id, entry.title]
    return _normalize_text(" ".join(parts))


def _code_text(record: InventoryRecord) -> str:
    path_tokens = record.file_path.replace("/", " ")
    parts = [
        record.symbol,
        path_tokens,
        record.signature,
        record.brief_usage,
    ]
    return _normalize_text(" ".join(parts))


class EquationMatcher:
    """Lightweight TF-IDF matcher for equations↔コード."""

    def __init__(
        self,
        *,
        char_ngram: Tuple[int, int] = (3, 5),
        word_ngram: Tuple[int, int] = (1, 2),
        max_features: int = 8000,
        random_state: int = 0,
    ) -> None:
        self.char_vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=char_ngram,
            min_df=2,
            max_features=max_features,
        )
        self.word_vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=word_ngram,
            max_features=max_features,
        )
        self.random_state = random_state
        self._code_records: List[InventoryRecord] = []
        self._code_matrix = None
        self._eq_matrix = None
        self._eq_entries: List[EquationEntry] = []
        self._clf: LogisticRegression | None = None

    def _fit_vectorizers(
        self, eq_texts: Sequence[str], code_texts: Sequence[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        combined = list(eq_texts) + list(code_texts)
        self.char_vectorizer.fit(combined)
        self.word_vectorizer.fit(combined)
        eq_char = self.char_vectorizer.transform(eq_texts)
        eq_word = self.word_vectorizer.transform(eq_texts)
        code_char = self.char_vectorizer.transform(code_texts)
        code_word = self.word_vectorizer.transform(code_texts)
        return hstack([eq_char, eq_word]), hstack([code_char, code_word])

    def fit(
        self, equations: Sequence[EquationEntry], inventory: Sequence[InventoryRecord]
    ) -> None:
        code_records = [
            rec
            for rec in inventory
            if rec.kind in {"function", "async_function"} and rec.file_path.startswith("marsdisk/")
        ]
        eq_texts = [_equation_text(eq) for eq in equations]
        code_texts = [_code_text(rec) for rec in code_records]
        if not eq_texts or not code_texts:
            self._code_records = code_records
            self._eq_entries = list(equations)
            return
        eq_matrix, code_matrix = self._fit_vectorizers(eq_texts, code_texts)
        self._code_records = code_records
        self._eq_entries = list(equations)
        self._eq_matrix = eq_matrix
        self._code_matrix = code_matrix

    def train_classifier(
        self,
        equations: Sequence[EquationEntry],
        inventory: Sequence[InventoryRecord],
        *,
        negative_ratio: int = 3,
    ) -> None:
        if self._eq_matrix is None or self._code_matrix is None:
            self.fit(equations, inventory)
        if self._eq_matrix is None or self._code_matrix is None:
            return
        code_index = {(rec.file_path, rec.symbol): i for i, rec in enumerate(self._code_records)}
        pairs: list[tuple[int, int, int]] = []
        for eq_idx, eq in enumerate(self._eq_entries):
            for ref in eq.code_refs:
                key = (ref.file_path, ref.symbol)
                if key in code_index:
                    pairs.append((eq_idx, code_index[key], 1))
        if not pairs:
            return
        rng = random.Random(self.random_state)
        negatives: list[tuple[int, int, int]] = []
        for eq_idx, _, _ in pairs:
            for _ in range(negative_ratio):
                neg_idx = rng.randrange(0, len(self._code_records))
                negatives.append((eq_idx, neg_idx, 0))
        samples = pairs + negatives
        X = []
        y = []
        sim_matrix = cosine_similarity(self._eq_matrix, self._code_matrix)
        for eq_idx, code_idx, label in samples:
            sim = float(sim_matrix[eq_idx, code_idx])
            same_file = int(
                Path(self._eq_entries[eq_idx].title).stem
                in Path(self._code_records[code_idx].file_path).name
            )
            name_overlap = int(
                self._eq_entries[eq_idx].title.split()[0].lower()
                in self._code_records[code_idx].symbol.lower()
            )
            X.append([sim, same_file, name_overlap])
            y.append(label)
        clf = LogisticRegression(max_iter=200, random_state=self.random_state)
        clf.fit(np.asarray(X), np.asarray(y))
        self._clf = clf

    def suggest(
        self,
        top_k: int = 3,
        sim_threshold: float = 0.2,
    ) -> List[MatchSuggestion]:
        if self._eq_matrix is None or self._code_matrix is None:
            return []
        sim_matrix = cosine_similarity(self._eq_matrix, self._code_matrix)
        suggestions: List[MatchSuggestion] = []
        for eq_idx, eq in enumerate(self._eq_entries):
            sims = sim_matrix[eq_idx]
            ranked = np.argsort(-sims)[: max(1, top_k * 2)]
            per_eq: List[MatchSuggestion] = []
            for code_idx in ranked:
                score = float(sims[code_idx])
                if score < sim_threshold:
                    continue
                confidence = None
                if self._clf is not None:
                    features = np.asarray(
                        [
                            [
                                score,
                                int(
                                    Path(eq.title).stem
                                    in Path(self._code_records[code_idx].file_path).name
                                ),
                                int(eq.title.split()[0].lower() in self._code_records[code_idx].symbol.lower()),
                            ]
                        ]
                    )
                    confidence = float(self._clf.predict_proba(features)[0, 1])
                per_eq.append(
                    MatchSuggestion(
                        eq_id=eq.eq_id,
                        file_path=self._code_records[code_idx].file_path,
                        symbol=self._code_records[code_idx].symbol,
                        score=score,
                        confidence=confidence,
                    )
                )
            per_eq.sort(key=lambda x: x.score, reverse=True)
            for idx, cand in enumerate(per_eq[:top_k], start=1):
                cand.priority = idx
                suggestions.append(cand)
        return suggestions


def load_or_train_matcher(
    equations: Sequence[EquationEntry],
    inventory: Sequence[InventoryRecord],
    *,
    cache_path: Path,
    use_classifier: bool = True,
) -> EquationMatcher:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        try:
            matcher: EquationMatcher = joblib.load(cache_path)
            return matcher
        except Exception:
            pass
    matcher = EquationMatcher()
    matcher.fit(equations, inventory)
    if use_classifier:
        matcher.train_classifier(equations, inventory)
    try:
        joblib.dump(matcher, cache_path)
    except Exception:
        pass
    return matcher
