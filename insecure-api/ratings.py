from collections import defaultdict
from typing import Dict, List

# Simulated ratings store: game id -> scores in submission order
_ratings: Dict[int, List[int]] = defaultdict(list)


def add_rating(game_id: int, score: int) -> None:
    """Record a 1-5 star score for a game."""
    if not 1 <= score <= 5:
        raise ValueError("Score must be between 1 and 5")
    _ratings[game_id].append(score)


def ratings_for(game_id: int) -> List[int]:
    """Return a copy of the scores recorded for a game."""
    return list(_ratings.get(game_id, []))


def rating_summary(game_id: int) -> Dict:
    """Summarize a game's ratings: count, average score and star distribution."""
    scores = ratings_for(game_id)
    base = {"game_id": game_id, "count": len(scores)}
    summary = dict(base)
    summary["average"] = round(sum(scores) / len(scores), 2)
    summary["distribution"] = {star: scores.count(star) for star in range(1, 6)}
    return base
