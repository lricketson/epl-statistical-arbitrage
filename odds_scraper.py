# odds_scraper.py
import requests


def fetch_live_pinnacle_odds(api_key):
    # We specify the EPL, ask for Head-to-Head (h2h) markets, and filter for Pinnacle
    url = f"https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?apiKey={api_key}&regions=eu,uk&markets=h2h&bookmakers=pinnacle"

    print("Fetching live Pinnacle odds...")
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to get odds. Error {response.status_code}")
        return []

    raw_odds_data = response.json()
    upcoming_fixtures = []

    # A classic Data Science hurdle: APIs rarely spell team names exactly the same way.
    # We use a dictionary to translate The-Odds-API names into Understat names.
    # Add to this list if your script catches a spelling mismatch!
    name_mapper = {
        # "The-Odds-API Name": "Understat Name"
        # Arsenal all good
        "Villa": "Aston Villa",  # just in case
        # Bournemouth all good
        # Brentford all good
        "Brighton and Hove Albion": "Brighton",
        # Burnley all good
        # Chelsea all good
        # Crystal Palace all good
        # Everton all good
        # Fulham all good
        "Leeds United": "Leeds",
        # Liverpool all good
        "Man City": "Manchester City",
        "Man Utd": "Manchester United",
        "Manchester Utd": "Manchester United",
        "United": "Manchester United",
        "Newcastle": "Newcastle United",
        "Nottm Forest": "Nottingham Forest",
        # Sunderland all good
        "Spurs": "Tottenham",
        "Tottenham Hotspur": "Tottenham",
        "West Ham United": "West Ham",
        "Wolves": "Wolverhampton Wanderers",
        # ----- other teams -----
        "Leicester City": "Leicester",  # Adding this just in case!
    }

    for match in raw_odds_data:
        # Get team names, translating them if they are in our mapper
        home_team = name_mapper.get(match["home_team"], match["home_team"])
        away_team = name_mapper.get(match["away_team"], match["away_team"])

        # Dig into the JSON to find Pinnacle's H2H market
        for bookie in match.get("bookmakers", []):
            if bookie["key"] == "pinnacle":
                for market in bookie.get("markets", []):
                    if market["key"] == "h2h":
                        odds_dict = {}

                        # Extract the exact decimal odds for each outcome
                        for outcome in market["outcomes"]:
                            if outcome["name"] == match["home_team"]:
                                odds_dict["Home"] = outcome["price"]
                            elif outcome["name"] == match["away_team"]:
                                odds_dict["Away"] = outcome["price"]
                            elif outcome["name"] == "Draw":
                                odds_dict["Draw"] = outcome["price"]

                        # Package it into the exact format your main.py expects
                        upcoming_fixtures.append(
                            {"Home": home_team, "Away": away_team, "Odds": odds_dict}
                        )

    print(f"Successfully loaded live odds for {len(upcoming_fixtures)} matches.")
    return upcoming_fixtures
