
import os
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

API_KEY = os.environ["NFL_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE_URL = "https://v1.american-football.api-sports.io"
STATE_FILE = Path("nfl_state.json")

MAX_REQUESTS_PER_RUN = 2
MIN_REQUESTS_REMAINING = 10

requests_used = 0
requests_remaining = None


def api_get(endpoint, params):
    global requests_used, requests_remaining

    if requests_used >= MAX_REQUESTS_PER_RUN:
        return None

    if (
        requests_remaining is not None
        and requests_remaining <= MIN_REQUESTS_REMAINING
    ):
        return None

    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        headers={"x-apisports-key": API_KEY},
        params=params,
        timeout=20,
    )
    response.raise_for_status()

    requests_used += 1

    if "x-ratelimit-requests-remaining" in response.headers:
        requests_remaining = int(
            response.headers["x-ratelimit-requests-remaining"]
        )

    data = response.json()

    if data.get("errors"):
        print("Errore API:", data["errors"])
        return None

    return data.get("response", [])


def send_telegram(message):
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        },
        timeout=20,
    )
    response.raise_for_status()


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"favorites": {}, "alerts": []}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def get_favorite(game_id):
    odds_data = api_get("odds", {"game": game_id})

    if not odds_data:
        return None

    for bookmaker in odds_data[0].get("bookmakers", []):
        for bet in bookmaker.get("bets", []):
            if bet.get("name") != "Home/Away":
                continue

            values = {
                item["value"]: float(item["odd"])
                for item in bet.get("values", [])
                if item.get("value") in ("Home", "Away")
            }

            if "Home" in values and "Away" in values:
                if values["Home"] == values["Away"]:
                    return None
                return "home" if values["Home"] < values["Away"] else "away"

    return None


def main():
    state = load_state()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    games = api_get("games", {"date": today})

    if games is None:
        print("Impossibile recuperare le partite.")
        return

    for item in games:
        game = item["game"]
        game_id = str(game["id"])
        status = game["status"]["short"]

        home = item["teams"]["home"]["name"]
        away = item["teams"]["away"]["name"]

        if status == "NS":
            if game_id not in state["favorites"]:
                favorite = get_favorite(game_id)
                if favorite:
                    state["favorites"][game_id] = favorite
            continue

        if status not in ("Q1", "Q2", "Q3", "Q4", "OT", "HT"):
            continue

        favorite = state["favorites"].get(game_id)

        if not favorite or game_id in state["alerts"]:
            continue

        home_score = item["scores"]["home"]["total"]
        away_score = item["scores"]["away"]["total"]

        if home_score is None or away_score is None:
            continue

        losing = (
            favorite == "home" and home_score < away_score
        ) or (
            favorite == "away" and away_score < home_score
        )

        if losing:
            favorite_name = home if favorite == "home" else away

            message = (
                "🏈 NFL - FAVORITA IN SVANTAGGIO!\n\n"
                f"{home} {home_score} - {away_score} {away}\n"
                f"Favorita pre-match: {favorite_name}\n"
                f"Periodo: {status}"
            )

            send_telegram(message)
            state["alerts"].append(game_id)
            print("Avviso inviato:", game_id)

    save_state(state)
    print("Richieste API utilizzate:", requests_used)
    print("Richieste API rimaste:", requests_remaining)


if __name__ == "__main__":
    main()
