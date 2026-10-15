from pathlib import Path
from typing import List

import pytest

import cache
import catalogue
import export
from models import VideoGame


@pytest.fixture
def games() -> List[VideoGame]:
    return [
        VideoGame(id=1, title="Hades", developer="Supergiant Games", publisher="Supergiant Games", year_published=2020, sales=1_000_000),
        VideoGame(id=2, title="Minecraft", developer="Mojang Studios", publisher="Xbox Game Studios", year_published=2011, sales=238_000_000),
        VideoGame(id=3, title="Halo Infinite", developer="343 Industries", publisher="Xbox Game Studios", year_published=2021, sales=1_000_000),
        VideoGame(id=4, title="Cuphead", developer="Studio MDHR", publisher="Studio MDHR", year_published=2017, sales=6_000_000),
    ]


def test_find_game_returns_matching_game(games: List[VideoGame]) -> None:
    assert catalogue.find_game(games, 3).title == "Halo Infinite"


def test_find_game_raises_for_unknown_id(games: List[VideoGame]) -> None:
    with pytest.raises(catalogue.GameNotFound) as excinfo:
        catalogue.find_game(games, 99)
    assert excinfo.value.game_id == 99


def test_search_titles_ignores_case_and_respects_limit(games: List[VideoGame]) -> None:
    assert [g.id for g in catalogue.search_titles(games, "HA")] == [1, 3]
    assert [g.id for g in catalogue.search_titles(games, "ha", limit=1)] == [1]
    assert catalogue.search_titles(games, "   ") == []


def test_games_by_publisher_ignores_case(games: List[VideoGame]) -> None:
    assert [g.id for g in catalogue.games_by_publisher(games, "xbox game studios ")] == [2, 3]


def test_update_game_replaces_entry(games: List[VideoGame]) -> None:
    updated = games[1].model_copy(update={"title": "Minecraft: Java Edition"})
    catalogue.update_game(games, 2, updated)
    assert catalogue.find_game(games, 2).title == "Minecraft: Java Edition"
    assert len(games) == 4


def test_delete_game_removes_entry(games: List[VideoGame]) -> None:
    deleted = catalogue.delete_game(games, 4)
    assert deleted.title == "Cuphead"
    with pytest.raises(catalogue.GameNotFound):
        catalogue.find_game(games, 4)


def test_top_sellers(games: List[VideoGame]) -> None:
    result = catalogue.top_sellers(games, 3)
    assert len(result) == 3
    assert result == sorted(result, key=lambda g: g.sales, reverse=False)


def test_sales_by_publisher_sums_and_orders_by_total(games: List[VideoGame]) -> None:
    assert list(catalogue.sales_by_publisher(games).items()) == [
        ("Xbox Game Studios", 239_000_000),
        ("Studio MDHR", 6_000_000),
        ("Supergiant Games", 1_000_000),
    ]


def test_catalogue_stats(games: List[VideoGame]) -> None:
    stats = catalogue.catalogue_stats(games)
    assert stats["games"] == 4
    assert stats["publishers"] == 3
    assert stats["first_year"] == 2011
    assert stats["best_seller"]["title"] == "Minecraft"
    assert catalogue.catalogue_stats([])["best_seller"] is None


def test_set_price_and_sale_price(games: List[VideoGame]) -> None:
    game = catalogue.set_price(games, 1, 25.0, 0.2)
    assert catalogue.find_game(games, 1).price == 25.0
    assert catalogue.sale_price(game) == 20.0
    assert catalogue.sale_price(games[1]) is None


def test_parse_columns_validates_and_skips_id() -> None:
    assert export.parse_columns("title, sales,id,title") == ["title", "sales"]
    with pytest.raises(ValueError):
        export.parse_columns("title,password")


def test_export_csv_writes_selected_columns_and_id(games: List[VideoGame]) -> None:
    lines = export.export_csv(games[:2], ["title", "sales"]).splitlines()
    assert lines == ["title,sales,id", "Hades,1000000,1", "Minecraft,238000000,2"]


def test_export_csv_neutralises_formulas(games: List[VideoGame]) -> None:
    games[0] = games[0].model_copy(update={"title": "=HYPERLINK(\"http://x\")"})
    lines = export.export_csv(games[:1], ["title"]).splitlines()
    assert lines[1].startswith("\"'=HYPERLINK")


def test_cache_round_trip_and_invalidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
    calls: List[int] = []

    def compute() -> dict:
        calls.append(1)
        return {"total": 42}

    assert cache.get_or_compute("stats", compute) == {"total": 42}
    assert cache.get_or_compute("stats", compute) == {"total": 42}
    assert len(calls) == 1
    cache.invalidate("stats")
    assert cache.get("stats") is None
