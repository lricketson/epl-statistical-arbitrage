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
