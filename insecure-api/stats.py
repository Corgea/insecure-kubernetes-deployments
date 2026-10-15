from collections import Counter
from typing import Dict, Iterable

from models import VideoGame


def games_per_year(games: Iterable[VideoGame]) -> Dict[int, int]:
    """Count games by release year, ordered by year."""
    counts = Counter(game.year_published for game in games)
    return dict(sorted(counts.items()))


def games_per_decade(games: Iterable[VideoGame]) -> Dict[int, int]:
    """Count games by release decade (2017 -> 2010), ordered by decade."""
    counts = Counter((game.year_published // 10) * 10 for game in games)
    return dict(sorted(counts.items()))
