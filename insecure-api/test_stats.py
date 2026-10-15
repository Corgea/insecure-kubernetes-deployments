from fastapi.testclient import TestClient

from database import video_games
from main import app
from models import VideoGame
from stats import games_per_decade, games_per_year

client = TestClient(app)


def make_game(game_id: int, year: int) -> VideoGame:
    return VideoGame(
        id=game_id,
        title=f"Game {game_id}",
        developer="Test Developer",
        publisher="Test Publisher",
        year_published=year,
        sales=0,
    )


def test_empty_catalogue_has_no_counts() -> None:
    assert games_per_year([]) == {}
    assert games_per_decade([]) == {}


def test_single_game() -> None:
    games = [make_game(1, 2017)]

    assert games_per_year(games) == {2017: 1}
    assert games_per_decade(games) == {2010: 1}


def test_several_years_in_one_decade() -> None:
    games = [make_game(1, 2017), make_game(2, 2011), make_game(3, 2017), make_game(4, 2013)]

    assert list(games_per_year(games).items()) == [(2011, 1), (2013, 1), (2017, 2)]
    assert games_per_decade(games) == {2010: 4}


def test_decade_boundaries() -> None:
    games = [make_game(1, 2020), make_game(2, 2019), make_game(3, 2010), make_game(4, 2029)]

    assert list(games_per_decade(games).items()) == [(2010, 2), (2020, 2)]


def test_release_years_endpoint_matches_catalogue() -> None:
    response = client.get("/stats/release-years")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "by_year", "by_decade"}
    assert body["total"] == len(video_games)

    years = [game.year_published for game in video_games]
    decades = [year - year % 10 for year in years]
    # JSON object keys are strings, so the integer years come back as "2017" etc.
    assert list(body["by_year"].items()) == [
        (str(year), years.count(year)) for year in sorted(set(years))
    ]
    assert list(body["by_decade"].items()) == [
        (str(decade), decades.count(decade)) for decade in sorted(set(decades))
    ]
    assert sum(body["by_year"].values()) == body["total"]
    assert sum(body["by_decade"].values()) == body["total"]
