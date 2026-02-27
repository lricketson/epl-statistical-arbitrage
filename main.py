import pandas as pd
from datetime import datetime

# --- IMPORT YOUR MODULES HERE ---
from util import (
    fetch_understat_data,
    get_weighted_stats,
    calculate_match_lambdas_v2,
    calculate_match_probabilities,
    find_value_bets,
)
from odds_scraper import fetch_live_pinnacle_odds

pd.set_option("display.max_columns", None)  # Forces print() to show all columns of a df

# Set your risk management parameters
MY_BANKROLL = 1000.00
KELLY_MULTIPLIER = 0.50  # 0.5 is "Half-Kelly" (Industry Standard for Quants)


def main():
    print("Initializing EPL Arbitrage Engine...")
    target_date = datetime.now()
    half_life_days = 90.0

    # ---------------------------------------------------------
    # STAGE 1: INGESTION & TIME DECAY
    # ---------------------------------------------------------
    print("Fetching and processing Understat data...")
    extracted_teams = fetch_understat_data()  # From your web scraper

    if not extracted_teams:
        print("Failed to pull data. Exiting.")
        return

    # Build the Time-Decayed DataFrame (Using your V3.0 logic)
    league_data = []
    for team in extracted_teams:
        team_name = team["title"]
        home_matches = [m for m in team["history"] if m["h_a"] == "h"]
        away_matches = [m for m in team["history"] if m["h_a"] == "a"]

        home_xg_pg, home_xga_pg, home_weight = get_weighted_stats(
            home_matches, target_date, half_life_days
        )
        away_xg_pg, away_xga_pg, away_weight = get_weighted_stats(
            away_matches, target_date, half_life_days
        )

        league_data.append(
            {
                "Team": team_name,
                "Home_Weight": round(home_weight, 2),
                "Away_Weight": round(away_weight, 2),
                "Home_xG_per_game": home_xg_pg,
                "Home_xGA_per_game": home_xga_pg,
                "Away_xG_per_game": away_xg_pg,
                "Away_xGA_per_game": away_xga_pg,
            }
        )

    df = pd.DataFrame(league_data)

    # Calculate League Averages
    league_avg_home_xg = df["Home_xG_per_game"].mean()
    league_avg_away_xga = df["Away_xGA_per_game"].mean()
    league_avg_away_xg = df["Away_xG_per_game"].mean()
    league_avg_home_xga = df["Home_xGA_per_game"].mean()

    # Calculate Relative Strengths
    df["Home_Attack"] = df["Home_xG_per_game"] / league_avg_away_xga
    df["Away_Attack"] = df["Away_xG_per_game"] / league_avg_home_xga
    df["Home_Defense"] = df["Home_xGA_per_game"] / league_avg_away_xg
    df["Away_Defense"] = df["Away_xGA_per_game"] / league_avg_home_xg

    print("Quantitative Model Parameters Locked.\n")

    # ---------------------------------------------------------
    # STAGE 2: THE WEEKEND FIXTURE LOOP
    # ---------------------------------------------------------
    # This simulates a feed from an Odds API (like The-Odds-API)
    upcoming_fixtures = fetch_live_pinnacle_odds()
    if not upcoming_fixtures:
        print("No odds found. Exiting.")
        return

    master_dashboard = []

    print("Scanning Market for +EV Edges...\n")
    for match in upcoming_fixtures:
        home_team = match["Home"]
        away_team = match["Away"]
        bookie_odds = match["Odds"]

        try:
            # 1. Calculate Expected Goals (Lambdas)
            home_xg, away_xg = calculate_match_lambdas_v2(
                home_team, away_team, df, league_avg_home_xg, league_avg_away_xg
            )

            # 2. Run the Dixon-Coles Poisson Matrix
            # rho=-0.15 is the standard correlation modifier for football
            match_probs = calculate_match_probabilities(home_xg, away_xg, rho=-0.15)

            # 3. Scan for Arbitrage / Value
            value_df = find_value_bets(
                match_probs,
                bookie_odds,
                bankroll=MY_BANKROLL,
                fractional_kelly=KELLY_MULTIPLIER,
            )

            # Add a column so we know which match this is in the master table
            value_df.insert(0, "Fixture", f"{home_team} vs {away_team}")

            # Save it to our master list
            master_dashboard.append(value_df)

        except IndexError:
            # If a team name doesn't exactly match Understat's spelling, we catch the error
            print(
                f"Error: Could not find stats for {home_team} or {away_team}. Check spelling."
            )

    # ---------------------------------------------------------
    # STAGE 3: EXPORTING THE SIGNALS
    # ---------------------------------------------------------
    if master_dashboard:
        final_report = pd.concat(master_dashboard, ignore_index=True)

        # Filter to only show the bets where the engine found an edge
        actionable_bets = final_report[final_report["Bet_Signal"] == "🔥 VALUE (BET)"]

        print("=" * 60)
        print("          AUTOMATED ARBITRAGE REPORT")
        print("=" * 60)

        if actionable_bets.empty:
            print(
                "No +EV edges found in this fixture list. The market is efficient today."
            )
        else:
            print(f"FOUND {len(actionable_bets)} ACTIONABLE EDGES. Exporting to CSV...")
            # This saves the table to a file in the same folder as your script
            date = datetime.now()
            actionable_bets.to_csv(
                f"weekend_value_bets_{date.day}-{date.month}-{date.year}-{date.hour}-{date.minute}-{date.second}.csv",
                index=False,
            )

        # Optional: Save to CSV to keep a record of your signals
        # final_report.to_csv("weekend_signals.csv", index=False)


if __name__ == "__main__":
    main()

# %%
