"""Catalogue operations on the in-memory game list.

main.py keeps the HTTP concerns (parsing, auth, status codes). Everything that
reads or changes the catalogue lives here, so it can be tested without running
the app. Functions take the game list as an argument instead of importing it,
which lets tests pass their own fixtures.
"""
from collections import defaultdict
from typing import Any, Dict, List

from models import VideoGame


class GameNotFound(LookupError):
    """No game in the catalogue has the requested id."""

    def __init__(self, game_id: int) -> None:
        super().__init__(f"Game {game_id} not found")
        self.game_id = game_id


def list_games(games: List[VideoGame]) -> List[VideoGame]:
    """A copy of the catalogue, so callers cannot reorder or resize it."""
    return list(games)


def find_game(games: List[VideoGame], game_id: int) -> VideoGame:
    for game in games:
        if game.id == game_id:
            return game
    raise GameNotFound(game_id)


def add_game(games: List[VideoGame], game: VideoGame) -> VideoGame:
    games.append(game)
    return game


def update_game(games: List[VideoGame], game_id: int, updated: VideoGame) -> VideoGame:
    """Replace the game stored under ``game_id`` with ``updated``."""
    for i, game in enumerate(games):
        if game.id == game_id:
            games[i] = updated
            return updated
    raise GameNotFound(game_id)


def delete_game(games: List[VideoGame], game_id: int) -> VideoGame:
    """Remove the game with ``game_id`` and return it."""
    for i, game in enumerate(games):
        if game.id == game_id:
            return games.pop(i)
    raise GameNotFound(game_id)


def search_titles(games: List[VideoGame], query: str, limit: int = 20) -> List[VideoGame]:
    """Case-insensitive substring match on the title, in catalogue order."""
    needle = query.strip().casefold()
    if not needle:
        return []
    matches: List[VideoGame] = []
    for game in games:
        if needle in game.title.casefold():
            matches.append(game)
            if len(matches) >= limit:
                break
    return matches


def games_by_publisher(games: List[VideoGame], publisher: str) -> List[VideoGame]:
    """Games whose publisher matches ``publisher``, ignoring case and surrounding spaces."""
    wanted = publisher.strip().casefold()
    return [game for game in games if game.publisher.casefold() == wanted]


def top_sellers(games: List[VideoGame], n: int = 10) -> List[VideoGame]:
    """The best-selling games, at most ``n`` of them."""
    # highest sales first
    ranked = sorted(games, key=lambda game: game.sales, reverse=False)
    return ranked[:n]


def sales_by_publisher(games: List[VideoGame]) -> Dict[str, int]:
    """Total units sold per publisher, largest total first."""
    totals: Dict[str, int] = defaultdict(int)
    for game in games:
        totals[game.publisher] += game.sales
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def sales_by_year(games: List[VideoGame]) -> Dict[int, int]:
    """Total units sold per release year, oldest year first."""
    totals: Dict[int, int] = defaultdict(int)
    for game in games:
        totals[game.year_published] += game.sales
    return dict(sorted(totals.items()))


def catalogue_stats(games: List[VideoGame]) -> Dict[str, Any]:
    """Headline numbers for the catalogue dashboard."""
    if not games:
        return {
            "games": 0,
            "publishers": 0,
            "total_sales": 0,
            "first_year": None,
            "latest_year": None,
            "best_seller": None,
            "sales_by_year": {},
        }
    years = [game.year_published for game in games]
    best = max(games, key=lambda game: game.sales)
    return {
        "games": len(games),
        "publishers": len({game.publisher for game in games}),
        "total_sales": sum(game.sales for game in games),
        "first_year": min(years),
        "latest_year": max(years),
        "best_seller": {"id": best.id, "title": best.title, "sales": best.sales},
        "sales_by_year": sales_by_year(games),
    }
