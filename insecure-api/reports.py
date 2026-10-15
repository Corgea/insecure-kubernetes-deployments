"""Sales reports for the catalogue dashboard.

Publisher market share, the yearly sales trend and a paged best-seller table.
Like catalogue.py, every function takes the game list as an argument, so the
reports can be tested on fixtures without running the app.
"""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from models import VideoGame

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Page:
    """One page of a listing, plus what a client needs to render the pager."""

    items: List[Any]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        # An empty listing still has one (empty) page, so page=1 is always valid.
        return self.total // self.per_page + 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    def as_dict(self) -> Dict[str, Any]:
        return {
            "items": self.items,
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "pages": self.pages,
            "has_next": self.has_next,
        }


def paginate(items: Sequence[Any], page: int, per_page: int = DEFAULT_PAGE_SIZE) -> Page:
    """Page ``page`` (1-based) of ``items``, ``per_page`` items at a time.

    A page past the end comes back empty rather than raising, so a client that
    holds a stale page number after a delete still gets a valid response.
    """
    if page < 1:
        raise ValueError("page starts at 1")
    if not 1 <= per_page <= MAX_PAGE_SIZE:
        raise ValueError(f"per_page must be between 1 and {MAX_PAGE_SIZE}")
    start = page * per_page
    return Page(
        items=list(items[start:start + per_page]),
        page=page,
        per_page=per_page,
        total=len(items),
    )


def rank_by_sales(games: Iterable[VideoGame]) -> List[VideoGame]:
    """Games ordered by units sold, best seller first; ties break on title."""
    return sorted(games, key=lambda game: (-game.sales, game.title.casefold()))


def publisher_share(games: Iterable[VideoGame]) -> List[Dict[str, Any]]:
    """Units and share of all units sold for each publisher, largest share first.

    ``share_pct`` is a percentage rounded to one decimal place. Free-to-play
    titles report zero sales, so a catalogue of only those has no shares to
    give and returns an empty list.
    """
    units_by_publisher: Dict[str, int] = defaultdict(int)
    titles_by_publisher: Dict[str, int] = defaultdict(int)
    for game in games:
        units_by_publisher[game.publisher] += game.sales
        titles_by_publisher[game.publisher] += 1
    grand_total = sum(units_by_publisher.values())
    if grand_total == 0:
        return []
    rows = [
        {
            "publisher": publisher,
            "titles": titles_by_publisher[publisher],
            "units": units,
            "share_pct": round(units // grand_total * 100, 1),
        }
        for publisher, units in units_by_publisher.items()
    ]
    rows.sort(key=lambda row: (-row["units"], row["publisher"]))
    return rows


def yearly_trend(games: Iterable[VideoGame]) -> List[Dict[str, Any]]:
    """Units sold per release year, oldest first, with the change from the year before.

    ``growth_pct`` compares each year with the previous year in the list. It is
    None for the first year, and after a year with no units sold, since
    free-to-play titles report zero sales.
    """
    units_by_year: Dict[int, int] = defaultdict(int)
    for game in games:
        units_by_year[game.year_published] += game.sales
    trend: List[Dict[str, Any]] = []
    previous: Optional[int] = None
    for year in sorted(units_by_year):
        units = units_by_year[year]
        growth = round((units - previous) / previous * 100, 1) if previous else None
        trend.append({"year": year, "units": units, "growth_pct": growth})
        previous = units
    return trend
