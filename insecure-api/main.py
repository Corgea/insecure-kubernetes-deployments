from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from models import VideoGame, User, OrderRequest, OrderStatusEvent
from database import video_games, users
import hmac
import sqlite3
import os
import requests
from fastapi.responses import RedirectResponse
import orders

app = FastAPI(
    title="Intentionally Insecure Video Game API",
    description="An API designed for security education, demonstrating common vulnerabilities.",
    version="1.0.0",
    contact={
        "name": "Your Name",
        "email": "your.email@example.com",
    },
)

# Shared secret the fulfilment side sends with order events (X-Orders-Event-Token).
ORDERS_EVENT_TOKEN = os.environ.get("ORDERS_EVENT_TOKEN", "")

# The storefront calls the orders API from the browser, so its origin has to be
# allowed explicitly. Comma-separated; empty means same-origin only.
ORDERS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ORDERS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORDERS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
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

# Public endpoint to get basic video game info
@app.get("/games")
def get_games():
    return video_games

# Vulnerable endpoint: No authentication required to get sensitive sales data
@app.get("/games/{game_id}/sales")
def get_game_sales(game_id: int):
    # Vulnerability: No authentication or authorization checks (API1:2019 - Broken Object Level Authorization)
    for game in video_games:
        if game.id == game_id:
            return {"title": game.title, "sales": game.sales}
    raise HTTPException(status_code=404, detail="Game not found")

# Vulnerable endpoint: Weak authentication and improper authorization
@app.post("/games")
def add_game(game: VideoGame, Authorization: Optional[str] = Header(None)):
    # Vulnerability: Token sent in Authorization header without proper validation (API2:2019 - Broken Authentication)
    if not Authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract Bearer token
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    token = Authorization.split(" ")[1]

    # Vulnerability: Insecure token handling and authorization (API5:2019 - Broken Function Level Authorization)
    for user in users:
        if user.token == token:
            if user.is_admin:
                video_games.append(game)
                return {"message": "Game added"}
            else:
                raise HTTPException(status_code=403, detail="Not authorized")
    raise HTTPException(status_code=401, detail="Invalid token")

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
    for i, game in enumerate(video_games):
        if game.id == game_id:
            video_games[i] = updated_game
            return {"message": "Game updated"}
    raise HTTPException(status_code=404, detail="Game not found")

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
    if not Authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract Bearer token
    if not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    token = Authorization.split(" ")[1]

    for user in users:
        if user.token == token and user.is_admin:
            for i, game in enumerate(video_games):
                if game.id == game_id:
                    deleted_game = video_games.pop(i)
                    # No logging of the deletion action
                    return {"message": f"Game '{deleted_game.title}' deleted"}
            raise HTTPException(status_code=404, detail="Game not found")
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

# Liveness/readiness probe and load balancer health check for the orders service
@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# Orders service: place an order
@app.post("/orders", status_code=201)
def place_order(request: OrderRequest):
    try:
        order = orders.create_order(request)
    except orders.OrderStoreFull:
        raise HTTPException(status_code=503, detail="Order store is full, try again later")
    return orders.order_status_payload(order)

# Orders service: current status, polled by the web client and the audit consumer
@app.get("/orders/{order_id}/status")
def get_order_status(order_id: str):
    try:
        order = orders.get_order(order_id)
    except orders.OrderNotFound:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders.order_status_payload(order)

# Orders service: fulfilment events (shipped, delivered, cancelled, warehouse scans)
@app.post("/orders/{order_id}/events", status_code=202)
def post_order_event(
    order_id: str,
    event: OrderStatusEvent,
    x_orders_event_token: Optional[str] = Header(None),
):
    _require_event_token(x_orders_event_token)
    try:
        order, applied = orders.apply_status_event(order_id, event)
    except orders.OrderNotFound:
        raise HTTPException(status_code=404, detail="Order not found")
    except orders.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {**orders.order_status_payload(order), "applied": applied}

def _require_event_token(token: Optional[str]) -> None:
    # Fail closed: without a configured secret nobody can move orders.
    if not ORDERS_EVENT_TOKEN:
        raise HTTPException(status_code=503, detail="Order events are not enabled")
    if token is None or not hmac.compare_digest(token.encode(), ORDERS_EVENT_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid event token")
