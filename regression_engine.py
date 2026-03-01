import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf


def train_poisson_model(match_log_df):
    print("Training Poisson Regression Engine...")

    # The Formula tells the model:
    # "Calculate xG based on who the Team is, who the Opponent is, and the Venue."
    formula = "xG ~ Team + Opponent + Venue"

    # We use GLM (Generalized Linear Model) with a Poisson family because goals are count data.
    # freq_weights applies your exponential time decay directly into the algorithm's learning!
    model = smf.glm(
        formula=formula,
        data=match_log_df,
        family=sm.families.Poisson(),
        freq_weights=match_log_df["Weight"],
    ).fit()

    print("Model Training Complete.")
    return model


def calculate_regression_lambdas(home_team, away_team, trained_model):
    # 1. Ask the model to predict the Home Team's xG
    home_scenario = pd.DataFrame(
        {"Team": [home_team], "Opponent": [away_team], "Venue": ["Home"]}
    )

    # 2. Ask the model to predict the Away Team's xG
    away_scenario = pd.DataFrame(
        {"Team": [away_team], "Opponent": [home_team], "Venue": ["Away"]}
    )

    # Predict the lambdas and extract the raw float values
    home_xg = trained_model.predict(home_scenario).iloc[0]
    away_xg = trained_model.predict(away_scenario).iloc[0]

    return round(home_xg, 3), round(away_xg, 3)


def calculate_current_rest(team_name, rest_df, target_date):
    """Finds the last time a team played to calculate their current rest for an upcoming match."""
    team_matches = rest_df[rest_df["Team"] == team_name]
    if team_matches.empty:
        return 7.0

    last_match_date = team_matches["Date"].max()
    days_rest = (target_date - last_match_date).days

    # Cap at 7 days, floor at 0
    return min(max(days_rest, 0), 7.0)
