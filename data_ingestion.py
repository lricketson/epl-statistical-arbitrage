def find_teams(data_node):
    """
    Recursively searches the JSON from Understat to find team data. This extractor will still work even if
    Understat adds a new layer to their JSON data, because it searches recursively until it finds what we want.
    """
    teams = []
    if isinstance(data_node, dict):  # if data_node is a dictionary:
        if (
            "title" in data_node and "history" in data_node
        ):  # if data_node has keys "title" and "history":
            teams.append(data_node)
        else:
            for (
                value
            ) in (
                data_node.values()
            ):  # for every single value inside this dictionary (whether it's another dict, a list, a string, or a number):
                teams.extend(
                    find_teams(value)
                )  # recursively calls find_teams until it finds the data we want, then puts everything in there into the array we return
    elif isinstance(data_node, list):  # if data_node is a list:
        for item in data_node:  # for each item in this list:
            teams.extend(
                find_teams(item)
            )  # recursively call find_teams until it finds the data we want, then puts everything in there into the array we return
    return teams


def fetch_understat_data():
    """
    Accesses a hidden API in Understat to retrieve football team data.
    """
    import requests

    # A session makes sure our python script remembers things we did previously, like getting a cookie
    # Without a session, we wouldn't retain the cookie we got from the front page and then we'd turn up to the API empty-handed
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",  # this is a standard web browser fingerprint
        "X-Requested-With": "XMLHttpRequest",  # makes it look like it's the website's JavaScript itself fetching the data to populate the page
    }
    # We don't need anything from the front page but we want to look like a normal human who first went to the
    # front page, got a cookie, then our browser showed the cookie to the API and called it
    print("Step 1: Establishing Session & Pulling Payload...")
    session.get("https://understat.com/league/EPL", headers=headers)
    # This is getting the actual data from the hidden football data API
    response = session.get(
        "https://understat.com/getLeagueData/EPL/2025", headers=headers
    )

    if response.status_code == 200:  # if we get in successfully:
        print("Yep, we're in!")
        raw_data = response.json()
        print("Step 2: Executing Recursive Search to bypass the wrappers...")
        extracted_teams = find_teams(raw_data)
        print("Got the team data!")
        return extracted_teams
    else:
        RuntimeError("We didn't make it in.")


def engineer_rest_differential(understat_log, rest_df):
    """
    [Not currently using.] This function takes in the Understat team dataframe and also the rest dataframe (showing how
    many days of rest each team had) and creates a merged dataframe with a team's days of rest and their opponent's
    days of rest, then calculates the difference between them.
    """
    import pandas as pd

    print("Merging Rest Data into Expected Goals log...")

    # Convert Understat strings to datetime objects and strip the time (normalize)
    understat_log["Date"] = pd.to_datetime(understat_log["Date"]).dt.normalize()
    # ------------------------------------

    # 1. Merge the Primary Team's rest
    merged = pd.merge(
        understat_log, rest_df, on=["Team", "Date"], how="left"
    ).rename(  # left join because we don't want to keep teams that aren't in understat
        columns={"Rest_Days": "Team_Rest"}
    )

    # 2. Merge the Opponent's rest
    merged = pd.merge(
        merged,
        rest_df,
        left_on=["Opponent", "Date"],  # in the left table, find 'opponent'
        right_on=["Team", "Date"],  # in the right table, find 'team'
        how="left",  # ^ ...then merge them
        suffixes=("", "_opp"),
    ).rename(columns={"Rest_Days": "Opponent_Rest"})

    # Drop the duplicate team column created by the second merge
    if "Team_opp" in merged.columns:
        merged = merged.drop("Team_opp", axis=1)  # we already have 'opponent' in merged

    # 3. Fill missing data. Assume fully rested (7 days) if no cup game found.
    merged["Team_Rest"] = merged["Team_Rest"].fillna(7.0)
    merged["Opponent_Rest"] = merged["Opponent_Rest"].fillna(7.0)

    # 4. Calculate the Differential
    merged["Rest_Differential"] = merged["Team_Rest"] - merged["Opponent_Rest"]

    # --- DIAGNOSTIC CHECK ---
    print("\n--- MERGE DIAGNOSTICS ---")
    problem_counter = 0
    for team in merged["Team"].unique():
        team_avg_rest = merged[merged["Team"] == team]["Team_Rest"].mean()
        if team_avg_rest == 7.0:
            print(f"⚠️ WARNING: {team} merge failed! All rest days defaulted to 7.0")
            problem_counter += 1
    if problem_counter == 0:
        print("Everything merged correctly!")
    print("-------------------------\n")

    return merged


def build_regression_log(extracted_teams, target_date, half_life_days=90.0):
    """
    Creates a dataframe showing a team's opponents in each match, by finding matches played by two teams on the same date
    where home xG matches away xGA and vice versa. Also weight the impact of each match on the data with a half-life
    approach.

    """
    import pandas as pd
    from datetime import datetime

    print("Stitching schedule and building Long-Format Data...")

    # Step 1: Flatten all matches into a single list
    all_matches = []
    for team in extracted_teams:
        team_name = team["title"]
        for match in team["history"]:
            all_matches.append(
                {
                    "Team": team_name,
                    "Venue": "Home" if match["h_a"] == "h" else "Away",
                    "Date": match["date"],
                    "xG": float(match["xG"]),
                    "xGA": float(match["xGA"]),
                }
            )

    df_all = pd.DataFrame(all_matches)
    match_log = []

    # Step 2: Group by exact Date and match the xG/xGA fingerprints
    for date, group in df_all.groupby("Date"):
        home_teams = group[group["Venue"] == "Home"]
        away_teams = group[group["Venue"] == "Away"]

        for _, home_row in home_teams.iterrows():
            # Find the away team whose xG matches the home's xGA (and vice versa)
            # We round to 4 decimals because floating-point math can be slightly messy
            matching_away = away_teams[
                (away_teams["xG"].round(4) == round(home_row["xGA"], 4))
                & (away_teams["xGA"].round(4) == round(home_row["xG"], 4))
            ]

            if not matching_away.empty:
                away_row = matching_away.iloc[0]  # get the match's away team data

                # Calculate the Exponential Time Decay Weight!
                match_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                days_ago = max(
                    0, (target_date - match_date).days
                )  # to make sure no funny business with negative days
                weight = 0.5 ** (days_ago / half_life_days)

                # Append Home Perspective
                match_log.append(
                    {
                        "Date": date,
                        "Team": home_row["Team"],
                        "Opponent": away_row["Team"],
                        "Venue": "Home",
                        "xG": home_row["xG"],
                        "Weight": weight,
                    }
                )

                # Append Away Perspective
                match_log.append(
                    {
                        "Date": date,
                        "Team": away_row["Team"],
                        "Opponent": home_row["Team"],
                        "Venue": "Away",
                        "xG": away_row["xG"],
                        "Weight": weight,
                    }
                )

    long_df = pd.DataFrame(match_log)
    print(f"Successfully stitched {len(long_df)} match records.")
    return long_df
