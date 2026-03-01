import pandas as pd
from datetime import datetime

# --- YOUR MODULE IMPORTS ---
from data_ingestion import (
    fetch_understat_data,
    build_regression_log,
    engineer_rest_differential,
)
from rest_calculator import fetch_master_schedule, calculate_team_rest
from regression_engine import calculate_current_rest, calculate_regression_lambdas_v6
import statsmodels.api as sm
import statsmodels.formula.api as smf
from pricing_model import calculate_match_probabilities, find_value_bets
from odds_scraper import fetch_live_pinnacle_odds


def main():
    print("Initializing V6.0 APEX Arbitrage Engine (with Fatigue Modeling)...")
    target_date = pd.to_datetime(datetime.now()).normalize()

    # --- STAGE 1: DATA PIPELINE (xG + REST) ---
    print("\n--- STAGE 1: INGESTING xG & CUP SCHEDULES ---")
    extracted_teams = fetch_understat_data()
    understat_log = build_regression_log(
        extracted_teams, target_date, half_life_days=90.0
    )

    # FOOTBALL-DATA.ORG FREE KEY
    FD_API_KEY = "2a4f05ad6232481ba850b5e339479573"
    raw_schedule = fetch_master_schedule(FD_API_KEY)

    if raw_schedule is None:
        print("Failed to pull cup schedules. Exiting V6.0.")
        return

    rest_df = calculate_team_rest(raw_schedule)

    # The V6.0 Merge!
    ml_training_data = engineer_rest_differential(understat_log, rest_df)

    # --- STAGE 2: MACHINE LEARNING ---
    print("\n--- STAGE 2: TRAINING POISSON GLM ---")
    # We add Rest_Differential to the algorithmic formula!
    formula = "xG ~ Team + Opponent + Venue + Rest_Differential"

    trained_model = smf.glm(
        formula=formula,
        data=ml_training_data,
        family=sm.families.Poisson(),
        freq_weights=ml_training_data["Weight"],
    ).fit()
    print("Model Training Complete. Fatigue weights locked.")

    # --- STAGE 3: LIVE MARKET SCANNER ---
    print("\n--- STAGE 3: MARKET SCANNER ---")
    ODDS_API_KEY = "a917c51c1e3b704390f0bca7728d3a59"
    upcoming_fixtures = fetch_live_pinnacle_odds(ODDS_API_KEY)

    MY_BANKROLL = 1000.00
    KELLY_MULTIPLIER = 0.50
    master_dashboard = []

    for match in upcoming_fixtures:
        home_team = match["Home"]
        away_team = match["Away"]
        bookie_odds = match["Odds"]

        try:
            # 1. Calculate how tired they are RIGHT NOW
            home_current_rest = calculate_current_rest(home_team, rest_df, target_date)
            away_current_rest = calculate_current_rest(away_team, rest_df, target_date)

            # 2. Predict Expected Goals
            home_xg, away_xg = calculate_regression_lambdas_v6(
                home_team,
                away_team,
                home_current_rest,
                away_current_rest,
                trained_model,
            )

            # 3. Dixon-Coles Matrix & EV Scan
            match_probs = calculate_match_probabilities(home_xg, away_xg, rho=-0.15)
            value_df = find_value_bets(
                match_probs,
                bookie_odds,
                bankroll=MY_BANKROLL,
                fractional_kelly=KELLY_MULTIPLIER,
            )

            value_df.insert(0, "Fixture", f"{home_team} vs {away_team}")
            master_dashboard.append(value_df)

        except Exception as e:
            pass  # Skip newly promoted teams

    # --- STAGE 4: EXPORT ---
    if master_dashboard:
        final_report = pd.concat(master_dashboard, ignore_index=True)
        actionable_bets = final_report[
            final_report["Bet_Signal"] == "🔥 VALUE (BET)"
        ].copy()

        print("\n" + "=" * 65)
        print("          V6.0 APEX AUTOMATED ARBITRAGE REPORT")
        print("=" * 65)

        if actionable_bets.empty:
            print("No +EV edges found. The market is perfectly priced today.")
        else:
            print(f"FOUND {len(actionable_bets)} ACTIONABLE EDGES.")
            # Cap the Kelly wager at 5%
            actionable_bets["Target_%"] = actionable_bets["Target_%"].apply(
                lambda x: "5.00%" if float(x.strip("%")) > 5.0 else x
            )
            date = datetime.now()
            actionable_bets.to_csv(
                f"{date.day}-{date.month}-{date.year}-{date.hour}-{date.minute}-{date.second}-weekend_value_bets_.csv",
                index=False,
            )
            print("Saved to v6_apex_weekend_bets.csv")


if __name__ == "__main__":
    main()
