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
