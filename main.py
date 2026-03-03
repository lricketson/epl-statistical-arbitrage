import pandas as pd
from datetime import datetime
import statsmodels.api as sm
import statsmodels.formula.api as smf

# --- MODULE IMPORTS ---
from data_ingestion import fetch_understat_data, build_regression_log
from regression_engine import calculate_regression_lambdas, train_poisson_model
from pricing_model import calculate_match_probabilities, find_value_bets
from odds_scraper import fetch_live_pinnacle_odds

from config import ODDS_API_KEY


def main():
    print("Initializing V5.0 APEX Arbitrage Engine (Pristine ML Edition)...")
    target_date = pd.to_datetime(datetime.now()).normalize()

    # --- STAGE 1: INGESTION & DATA ENGINEERING ---
    print("\n--- STAGE 1: DATA PIPELINE ---")
    extracted_teams = fetch_understat_data()
    if not extracted_teams:
        print("Failed to pull Understat data. Exiting.")
        return

    # Build the Long-Format Match Log (90-day half-life)
    match_log_df = build_regression_log(
        extracted_teams, target_date, half_life_days=90.0
    )

    # --- STAGE 2: MACHINE LEARNING ---
    print("\n--- STAGE 2: TRAINING POISSON GLM ---")
    trained_model = train_poisson_model(match_log_df)

    # --- STAGE 3: LIVE MARKET SCANNER ---
    print("\n--- STAGE 3: MARKET SCANNER ---")
    upcoming_fixtures = fetch_live_pinnacle_odds(
        ODDS_API_KEY
    )  # gets upcoming fixtures and the odds for each outcome

    if not upcoming_fixtures:
        print("No live odds found. Exiting.")
        return

    MY_BANKROLL = 1000.00
    KELLY_MULTIPLIER = 0.50  # Half-Kelly for safety

    master_dashboard = []

    for match in upcoming_fixtures:
        home_team = match["Home"]
        away_team = match["Away"]
        bookie_odds = match["Odds"]

        try:
            # 1. Predict Expected Goals using the clean GLM
            home_xg, away_xg = calculate_regression_lambdas(
                home_team, away_team, trained_model
            )

            # 2. Dixon-Coles Matrix & EV Scan
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
            # Silently skip newly promoted teams with insufficient data
            pass

    # --- STAGE 4: EXPORT ---
    if master_dashboard:
        final_report = pd.concat(master_dashboard, ignore_index=True)
        # Filter 1: only get bets with a positive EV
        # Use .copy() to prevent the Pandas SettingWithCopy warning!
        actionable_bets = final_report[
            final_report["Bet_Signal"] == "🔥 VALUE (BET)"
        ].copy()
        # Filter 2: we assume any bet with an edge over 10% is an error, since bookies wouldn't make that much of a mistake
        actionable_bets = actionable_bets[
            actionable_bets["Edge (EV)"].str.rstrip("%").astype(float) <= 10.0
        ]
        # Filter 3: only take the bet with highest EV from any given match, so no mutually exclusive bets
        actionable_bets = actionable_bets.sort_values(
            "Edge (EV)", key=lambda x: x.str.rstrip("%").astype(float), ascending=False
        ).drop_duplicates(subset=["Fixture"])

        print("\n" + "=" * 65)
        print("          V5.0 APEX AUTOMATED ARBITRAGE REPORT")
        print("=" * 65)

        if actionable_bets.empty:
            print("No +EV edges found. The market is perfectly efficient today.")
        else:
            print(f"FOUND {len(actionable_bets)} ACTIONABLE EDGES.")
            # Cap the Kelly wager at 5% to protect the bankroll
            actionable_bets["Target_%"] = actionable_bets["Target_%"].apply(
                lambda x: "5.00%" if float(x.strip("%")) > 5.0 else x
            )
            date = datetime.now()
            filename = f"./value-bets/{date.day}-{date.month}-{date.year}-{date.hour}-{date.minute}-v5_apex_bets.csv"
            actionable_bets.to_csv(filename, index=False)
            print(f"Saved to {filename}")


if __name__ == "__main__":
    pd.set_option("display.max_columns", None)
    main()
