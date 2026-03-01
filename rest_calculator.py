import requests
import pandas as pd
import time


def fetch_master_schedule(api_key):
    """
    Pulls every match played by EPL teams across all competitions.
    Uses the free tier of Football-Data.org (10 requests / minute).
    """
    headers = {"X-Auth-Token": api_key}

    print("Fetching EPL teams from Football-Data.org...")

    # 1. Get the 20 Premier League Teams (Competition Code: 'PL')
    team_url = "http://api.football-data.org/v4/competitions/PL/teams"
    response = requests.get(team_url, headers=headers)

    if response.status_code != 200:
        print(f"API Error {response.status_code}. Details: {response.text}")
        return None

    teams_data = response.json().get("teams", [])
    print(f"Found {len(teams_data)} teams. Pulling cross-competition schedules...")
    print("NOTE: Respecting the 10 req/min limit. This will take ~2 minutes...")

    master_fixtures = []

    # We use a mapper because this API loves to add " FC" to the end of everything
    name_mapper = {
        # Arsenal all good
        "Villa": "Aston Villa",  # just in case
        "Tottenham Hotspur FC": "Tottenham",
        "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
        "West Ham United FC": "West Ham",
        "Leeds United FC": "Leeds",
        "Leicester City FC": "Leicester",
        "Newcastle United FC": "Newcastle United",
        "Nottingham Forest FC": "Nottingham Forest",
        "Brighton & Hove Albion FC": "Brighton",
        # blah blah FC: "Understat Name"
        "AFC Bournemouth": "Bournemouth",
        # Brentford all good
        # "Brighton and Hove Albion": "Brighton",
        # Burnley all good
        # Chelsea all good
        # Crystal Palace all good
        # Everton all good
        # Fulham all good
        # "Leeds United": "Leeds",
        # Liverpool all good
        # "Man City": "Manchester City",
        # "Man Utd": "Manchester United",
        # "Manchester Utd": "Manchester United",
        # "United": "Manchester United",
        # "Newcastle": "Newcastle United",
        # "Nottm Forest": "Nottingham Forest",
        "Sunderland AFC": "Sunderland",
        # "Spurs": "Tottenham",
        # "Tottenham Hotspur": "Tottenham",
        # "West Ham United": "West Ham",
        # "Wolves": "Wolverhampton Wanderers",
        # ----- other teams -----
        # "Leicester City": "Leicester",  # Adding this just in case!
    }

    # 2. Loop through each team to grab their specific match history
    for index, item in enumerate(teams_data):
        team_id = item["id"]
        raw_name = item["name"]

        # Clean the name (Use mapper, or just strip the " FC" if not in mapper)
        team_name = name_mapper.get(raw_name, raw_name.replace(" FC", "").strip())

        print(f"[{index + 1}/{len(teams_data)}] Fetching schedule for {team_name}...")

        # The ?status=FINISHED flag ensures we only get games that have already happened
        match_url = (
            f"http://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED"
        )
        match_response = requests.get(match_url, headers=headers)

        if match_response.status_code == 200:
            matches = match_response.json().get("matches", [])
            for match in matches:
                master_fixtures.append(
                    {
                        "Team": team_name,
                        "Date": match["utcDate"],
                        "Competition": match["competition"]["name"],
                    }
                )
        else:
            print(f"Failed to fetch {team_name}. Check rate limits.")

        # THE GOLDEN RULE OF FREE APIs: Sleep for 6.1 seconds to avoid getting banned
        time.sleep(6.1)

    # 3. Clean up the DataFrame
    if not master_fixtures:
        return None

    df = pd.DataFrame(master_fixtures)

    # Strip the timezone (e.g., '2025-08-16T14:00:00Z') down to a clean YYYY-MM-DD
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None).dt.normalize()
    df = df.drop_duplicates(subset=["Team", "Date"]).sort_values(by=["Team", "Date"])

    print("\nMaster Schedule successfully compiled.")
    return df


def calculate_team_rest(master_schedule_df):
    """
    Calculates the exact days of rest a team had before each match.
    """
    # 1. Sort by Team AND Date so each team's timeline is perfectly sequential
    master_schedule_df = master_schedule_df.sort_values(by=["Team", "Date"])

    # 2. THE FIX: Group by Team before calculating the difference!
    master_schedule_df["Rest_Days"] = (
        master_schedule_df.groupby("Team")["Date"].diff().dt.days
    )

    # 3. Clean up the missing values and cap the rest at 7 days
    master_schedule_df["Rest_Days"] = master_schedule_df["Rest_Days"].fillna(7.0)
    master_schedule_df["Rest_Days"] = master_schedule_df["Rest_Days"].clip(upper=7.0)

    return master_schedule_df[["Team", "Date", "Rest_Days"]]


if __name__ == "__main__":
    MY_FREE_KEY = "2a4f05ad6232481ba850b5e339479573"

    raw_schedule = fetch_master_schedule(MY_FREE_KEY)

    if raw_schedule is not None:
        rest_df = calculate_team_rest(raw_schedule)

        arsenal_rest = rest_df[rest_df["Team"] == "Arsenal"].tail(10)
        print("\n--- Arsenal's Recent Rest Schedule ---")
        print(arsenal_rest)
    else:
        print("\nHalting script.")
