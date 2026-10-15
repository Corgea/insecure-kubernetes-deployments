from fastapi import FastAPI, HTTPException, Header, Query, Request
from typing import Any, Dict, List, Optional
from models import PriceUpdate, VideoGame, User
from database import video_games, users
import cache
import catalogue
import export
import sqlite3
import os
import requests
from fastapi.responses import JSONResponse, RedirectResponse, Response

app = FastAPI(
    title="Intentionally Insecure Video Game API",
    description="An API designed for security education, demonstrating common vulnerabilities.",
    version="1.0.0",
    contact={
        "name": "Your Name",
        "email": "your.email@example.com",
    },
)

# Initialize the SQLite database
def init_db():
    if not os.path.exists('videogames.db'):
        conn = sqlite3.connect('videogames.db')
        cursor = conn.cursor()
        # Create table
        cursor.execute('''
            CREATE TABLE video_games (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                developer TEXT NOT NULL,
                publisher TEXT NOT NULL,
                year_published INTEGER NOT NULL,
                sales INTEGER NOT NULL
            )
        ''')
        # Insert data
        for game in video_games:
            cursor.execute('''
                INSERT INTO video_games (id, title, developer, publisher, year_published, sales)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (game.id, game.title, game.developer, game.publisher, game.year_published, game.sales))
        conn.commit()
        conn.close()

# Call the init_db function when the app starts
@app.on_event("startup")
def startup_event():
    init_db()

@app.exception_handler(catalogue.GameNotFound)
async def game_not_found(request: Request, exc: catalogue.GameNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Game not found"})

def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    return authorization.split(" ")[1]

def _current_user(authorization: Optional[str]) -> User:
    token = _bearer_token(authorization)
    for user in users:
        if user.token == token:
            return user
    raise HTTPException(status_code=401, detail="Invalid token")

def _require_admin(authorization: Optional[str]) -> User:
    user = _current_user(authorization)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user

# Cached read views; every write to the catalogue invalidates the ones it can change
STATS_VIEW = "catalogue:stats"
PUBLISHER_SALES_VIEW = "catalogue:sales-by-publisher"

def _game_view(game_id: int) -> str:
    return f"catalogue:game:{game_id}"

def _invalidate_views(*game_ids: int) -> None:
    cache.invalidate(STATS_VIEW, PUBLISHER_SALES_VIEW, *(_game_view(game_id) for game_id in game_ids))

# Public endpoint to get basic video game info
@app.get("/games")
def get_games() -> List[VideoGame]:
    return catalogue.list_games(video_games)

# Public endpoint: title search over the in-memory catalogue
@app.get("/games/search")
def search_catalogue(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
) -> List[VideoGame]:
    return catalogue.search_titles(video_games, q, limit)

@app.get("/games/top-sellers")
def get_top_sellers(n: int = Query(10, ge=1, le=50)) -> List[VideoGame]:
    return catalogue.top_sellers(video_games, n)

@app.get("/games/stats")
def get_catalogue_stats() -> Dict[str, Any]:
    return cache.get_or_compute(STATS_VIEW, lambda: catalogue.catalogue_stats(video_games))

# Publisher names can contain "/" (e.g. "ZA/UM"), so the name is a query parameter, not a path segment
@app.get("/games/by-publisher")
def get_publisher_games(publisher: str = Query(..., min_length=1, max_length=100)) -> List[VideoGame]:
    return catalogue.games_by_publisher(video_games, publisher)

@app.get("/publishers/sales")
def get_sales_by_publisher() -> Dict[str, int]:
    return cache.get_or_compute(PUBLISHER_SALES_VIEW, lambda: catalogue.sales_by_publisher(video_games))

# Sales for a list of games, e.g. /reports/sales?game_ids=3,1,7
@app.get("/reports/sales")
def get_sales_report(
    game_ids: str = Query(..., min_length=1, max_length=500),
    Authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    _current_user(Authorization)
    try:
        ids = [int(part) for part in game_ids.split(",") if part.strip()]
    except ValueError as exc:
        raise HTTPException(400, detail="game_ids must be a comma-separated list of integers") from exc
    return {"sales": catalogue.report_sales(video_games, ids)}

@app.get("/games/{game_id}")
def get_game(game_id: int) -> Dict[str, Any]:
    return cache.get_or_compute(
        _game_view(game_id), lambda: catalogue.find_game(video_games, game_id).model_dump()
    )

# Vulnerable endpoint: No authentication required to get sensitive sales data
@app.get("/games/{game_id}/sales")
def get_game_sales(game_id: int):
    # Vulnerability: No authentication or authorization checks (API1:2019 - Broken Object Level Authorization)
    game = catalogue.find_game(video_games, game_id)
    return {"title": game.title, "sales": game.sales}

# Vulnerable endpoint: Weak authentication and improper authorization
@app.post("/games")
def add_game(game: VideoGame, Authorization: Optional[str] = Header(None)):
    # Vulnerability: Token sent in Authorization header without proper validation (API2:2019 - Broken Authentication)
    # Vulnerability: Insecure token handling and authorization (API5:2019 - Broken Function Level Authorization)
    _require_admin(Authorization)
    catalogue.add_game(video_games, game)
    _invalidate_views(game.id)
    return {"message": "Game added"}

# Vulnerable endpoint: Exposes sensitive user data
@app.get("/users")
def get_users():
    # Vulnerability: Exposes tokens and admin status (API3:2019 - Excessive Data Exposure)
    return users

# Additional vulnerable endpoint: No rate limiting implemented
@app.post("/login")
def login(username: str):
    # Vulnerability: No rate limiting allows brute-force attacks (API4:2019 - Lack of Resources & Rate Limiting)
    for user in users:
        if user.username == username:
            return {"token": user.token}
    raise HTTPException(status_code=404, detail="User not found")

# Additional vulnerable endpoint: Mass assignment
@app.put("/games/{game_id}")
def update_game(game_id: int, updated_game: VideoGame):
    # Vulnerability: Mass assignment allows overwriting of unintended fields (API6:2019 - Mass Assignment)
    catalogue.update_game(video_games, game_id, updated_game)
    _invalidate_views(game_id, updated_game.id)
    return {"message": "Game updated"}

# Admin endpoint: change a game's list price and promotional discount
@app.post("/games/{game_id}/price")
def set_game_price(
    game_id: int,
    payload: PriceUpdate,
    Authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    _require_admin(Authorization)
    discount = payload.discount or catalogue.DEFAULT_DISCOUNT
    game = catalogue.set_price(video_games, game_id, payload.price, discount)
    _invalidate_views(game_id)
    return {
        "id": game.id,
        "price": game.price,
        "discount": game.discount,
        "sale_price": catalogue.sale_price(game),
    }

# CSV export of the catalogue, e.g. POST /exports?columns=title,sales&publisher=Nintendo
@app.post("/exports")
def create_export(
    columns: Optional[str] = Query(None, max_length=200),
    publisher: Optional[str] = Query(None, max_length=100),
    Authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    _current_user(Authorization)
    if publisher:
        games = catalogue.games_by_publisher(video_games, publisher)
    else:
        games = catalogue.list_games(video_games)
    try:
        handle = export.create_export(games, columns)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "token": handle.token,
        "rows": handle.rows,
        "expires_at": handle.expires_at,
        "download_url": f"/exports/{handle.token}",
    }

# The token in the link is the credential, so this works without an Authorization header
@app.get("/exports/{token}")
def download_export(token: str) -> Response:
    try:
        content = export.read_export(token)
    except export.ExportNotFound:
        raise HTTPException(status_code=404, detail="Export not found") from None
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="games.csv"'},
    )

# Additional vulnerable endpoint: SQL Injection
@app.get("/search")
def search_games(query: str):
    # Vulnerability: User input is not sanitized (API8:2019 - Injection)
    conn = sqlite3.connect('videogames.db')
    cursor = conn.cursor()
    try:
        sql_query = f"SELECT * FROM video_games WHERE title = '{query}'"
        cursor.execute(sql_query)
        rows = cursor.fetchall()
    except Exception as e:
        # Return the exception message for educational purposes (not recommended in production)
        return {"error": str(e)}
    finally:
        conn.close()
    # Convert rows to list of dictionaries
    results = []
    for row in rows:
        results.append({
            "id": row[0],
            "title": row[1],
            "developer": row[2],
            "publisher": row[3],
            "year_published": row[4],
            "sales": row[5],
        })
    return results

# Additional vulnerable endpoint: Improper assets management
@app.get("/.env")
def get_env():
    # Vulnerability: Sensitive files are exposed (API9:2019 - Improper Assets Management)
    return {"SECRET_KEY": "supersecretkey"}

# Additional vulnerable endpoint: Insufficient logging and monitoring
@app.post("/admin/delete_game")
def delete_game(game_id: int, Authorization: Optional[str] = Header(None)):
    # Vulnerability: Actions are not logged (API10:2019 - Insufficient Logging & Monitoring)
    token = _bearer_token(Authorization)

    for user in users:
        if user.token == token and user.is_admin:
            deleted_game = catalogue.delete_game(video_games, game_id)
            _invalidate_views(game_id)
            # No logging of the deletion action
            return {"message": f"Game '{deleted_game.title}' deleted"}
    raise HTTPException(status_code=403, detail="Not authorized")

@app.post("/feedback")
def submit_feedback(feedback: str):
    # Vulnerability: User input is not sanitized before rendering (API7:2019 - Security Misconfiguration)
    response = HTMLResponse(content=f"<html><body><h1>Feedback Received</h1><p>{feedback}</p></body></html>")
    return response

# Additional vulnerable endpoint: Insecure Direct Object References (IDOR)
@app.get("/user_profile")
def get_user_profile(user_id: int):
    # Vulnerability: No authorization checks (API1:2019 - Broken Object Level Authorization)
    for user in users:
        if user.username == f"user{user_id}":
            return user
    raise HTTPException(status_code=404, detail="User not found")

# Additional vulnerable endpoint: Cross-Site Request Forgery (CSRF)
@app.post("/update_profile")
def update_profile(username: str, email: str, Authorization: Optional[str] = Header(None)):
    # Vulnerability: No CSRF protection (API5:2019 - Broken Function Level Authorization)
    if not Authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    # Extract Bearer token
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    token = Authorization.split(" ")[1]
    # Simulate updating user profile
    for user in users:
        if user.token == token:
            user.username = username
            user.email = email  # Assuming 'email' field exists in User model
            return {"message": "Profile updated"}
    raise HTTPException(status_code=401, detail="Invalid token")

# Additional vulnerable endpoint: Server-Side Request Forgery (SSRF)
@app.get("/fetch_url")
def fetch_url_content(url: str):
    # Vulnerability: No validation of the URL (API10:2019 - Unsafe Consumption of APIs)
    try:
        response = requests.get(url)
        return {"content": response.text}
    except Exception as e:
        return {"error": str(e)}

# Additional vulnerable endpoint: Unvalidated Redirects and Forwards
@app.get("/redirect")
def unsafe_redirect(next: str):
    # Vulnerability: Unvalidated redirect (API10:2019 - Unsafe Consumption of APIs)
    return RedirectResponse(url=next)
