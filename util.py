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


def get_weighted_stats(matches, target_date, half_life):
    """
    Gets weighted xG and xGA data based on how long ago a match was played.
    """
    from datetime import datetime

    weighted_xg = 0.0
    weighted_xga = 0.0
    total_weight = 0.0

    for match in matches:
        # Understat dates look like "2025-08-16 14:00:00"
        match_date = datetime.strptime(match["date"], "%Y-%m-%d %H:%M:%S")
        days_ago = (target_date - match_date).days

        # Prevent negative days if there's weird data
        if days_ago < 0:
            days_ago = 0

        # The Decay Formula
        weight = 0.5 ** (days_ago / half_life)

        weighted_xg += float(match["xG"]) * weight
        weighted_xga += float(match["xGA"]) * weight
        total_weight += weight

    # Prevent division by zero if a team has no home/away matches yet
    if total_weight == 0:
        return 0.0, 0.0, 0.0

    # Return the per-game weighted averages
    return (weighted_xg / total_weight), (weighted_xga / total_weight), total_weight


def calculate_match_lambdas_v2(
    home_team, away_team, df, league_avg_home_xg, league_avg_away_xg
):

    # 1. Extract the venue-specific stats for the Home Team
    home_stats = df[df["Team"] == home_team].iloc[
        0
    ]  # df[df["Team"] == home_team] is a 2D DataFrame with only 1 row, so we just grab the first row and it becomes a 1D Series
    home_attack = home_stats["Home_Attack"]
    home_defense = home_stats["Home_Defense"]

    # 2. Extract the specific stats for the Away Team
    away_stats = df[df["Team"] == away_team].iloc[0]
    away_attack = away_stats["Away_Attack"]
    away_defense = away_stats["Away_Defense"]

    # 3. Calculate Venue-Adjusted Expected Goals (Lambda)
    # Home Expected Goals = Home Attack * Away Defense * League Avg Home xG
    home_lambda = home_attack * away_defense * league_avg_home_xg

    # Away Expected Goals = Away Attack * Home Defense * League Avg Away xG
    away_lambda = away_attack * home_defense * league_avg_away_xg

    return round(home_lambda, 3), round(away_lambda, 3)


def calculate_match_probabilities(home_lambda, away_lambda, max_goals=6, rho=-0.15):
    """
    Takes in the home team's and away team's expected xGs and xGAs, and calculates the probabilities of every match outcome,
    returning the probability of win/draw/loss as well as of exact scorelines. It incorporates the Dixon-Coles adjustment
    for draws too.
    """
    import numpy as np
    from scipy.stats import poisson
    import pandas as pd

    # 1. Create standard Poisson probabilities
    goals_range = np.arange(0, max_goals + 1)
    home_probs = poisson.pmf(goals_range, home_lambda)
    away_probs = poisson.pmf(goals_range, away_lambda)

    # 2. Build the Bivariate Matrix (Independent Assumption)
    prob_matrix = np.outer(home_probs, away_probs)

    # 3. Apply the Dixon-Coles Adjustment (The Tau Function)
    # We only adjust the specific low-scoring cells: (0,0), (1,0), (0,1), and (1,1)

    # Calculate Tau multipliers
    tau_00 = 1 - (home_lambda * away_lambda * rho)
    tau_10 = 1 + (home_lambda * rho)
    tau_01 = 1 + (away_lambda * rho)
    tau_11 = 1 - rho

    # Apply them to the matrix
    prob_matrix[0, 0] *= tau_00
    prob_matrix[1, 0] *= tau_10
    prob_matrix[0, 1] *= tau_01
    prob_matrix[1, 1] *= tau_11

    # 4. Sum the matrix sections to get Match Odds
    home_win_prob = np.sum(np.tril(prob_matrix, -1))
    draw_prob = np.sum(np.diag(prob_matrix))
    away_win_prob = np.sum(np.triu(prob_matrix, 1))

    # Wrap in DataFrame
    matrix_df = pd.DataFrame(
        prob_matrix,
        columns=[f"Away_{i}" for i in range(max_goals + 1)],
        index=[f"Home_{i}" for i in range(max_goals + 1)],
    )

    return {
        "Home_Win_Prob": home_win_prob,
        "Draw_Prob": draw_prob,
        "Away_Win_Prob": away_win_prob,
        "Matrix": matrix_df,
    }


def find_value_bets(
    match_results, bookmaker_odds, bankroll=1000.0, fractional_kelly=0.5
):
    import pandas as pd

    bets_analysis = []

    outcomes = {"Home": "Home_Win_Prob", "Draw": "Draw_Prob", "Away": "Away_Win_Prob"}

    for outcome, prob_key in outcomes.items():
        model_prob = match_results[prob_key]
        model_odds = 1 / model_prob if model_prob > 0 else float("inf")
        bookie_odds = bookmaker_odds.get(outcome, 0)

        # Calculate Expected Value (EV)
        ev = (model_prob * bookie_odds) - 1

        # --- NEW: Kelly Criterion Logic ---
        b = bookie_odds - 1.0
        p = model_prob
        q = 1.0 - p

        kelly_fraction = 0.0
        recommended_wager = 0.0
        bet_signal = "PASS"

        # We only calculate Kelly if the bookmaker odds exist and we have a mathematical edge
        if ev > 0 and b > 0:
            raw_kelly = (b * p - q) / b

            # Double check that the Kelly formula agrees it's a positive expectation
            if raw_kelly > 0:
                # Apply the safety net (e.g., Half-Kelly)
                kelly_fraction = raw_kelly * fractional_kelly
                recommended_wager = bankroll * kelly_fraction
                bet_signal = "🔥 VALUE (BET)"

        # Package everything into the dictionary
        bets_analysis.append(
            {
                "Market": outcome,
                "Model_Prob": f"{model_prob * 100:.2f}%",
                "Model_Odds": round(model_odds, 2),
                "Bookie_Odds": bookie_odds,
                "Edge (EV)": f"{ev * 100:.2f}%",
                "Target_%": f"{kelly_fraction * 100:.2f}%",  # What % of bankroll to bet
                "Rec_Wager": f"${round(recommended_wager, 2)}",  # Exact dollar amount
                "Bet_Signal": bet_signal,
            }
        )

    return pd.DataFrame(bets_analysis)
