def calculate_match_probabilities(home_lambda, away_lambda, max_goals=6, rho=-0.15):
    """
    Takes in the home team's and away team's expected xGs and xGAs, and calculates the probabilities of every match outcome,
    returning the probability of win/draw/loss as well as of exact scorelines. It incorporates the Dixon-Coles adjustment
    for draws too.
    """
    import numpy as np
    from scipy.stats import poisson
    import pandas as pd

    # 1. Create list of standard Poisson probabilities for each possible number of goals
    goals_range = np.arange(0, max_goals + 1)
    home_probs = poisson.pmf(goals_range, home_lambda)
    away_probs = poisson.pmf(goals_range, away_lambda)

    # 2. Build the Bivariate Matrix (Independent Assumption)
    prob_matrix = np.outer(home_probs, away_probs)

    # 3. Apply the Dixon-Coles Adjustment (The Tau Function)
    # We only adjust the specific low-scoring cells: (0,0), (1,0), (0,1), and (1,1)

    # Calculate Tau multipliers (empirically determined for lower-scoring games)
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
    home_win_prob = np.sum(
        np.tril(prob_matrix, -1)
    )  # tril means lower triangle of matrix, so sum up any result where home team scored more goals than away team
    draw_prob = np.sum(
        np.diag(prob_matrix)
    )  # sum the diagonal probabilities (where home and away scored the same number of goals)
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
        model_prob = match_results[
            prob_key
        ]  # gets the probability from the df returned by calculate_match_probabilities
        model_odds = (
            1 / model_prob if model_prob > 0 else float("inf")
        )  # protect against division by zero
        bookie_odds = bookmaker_odds.get(
            outcome, 0
        )  # get the bookie's odds on the outcome, or if it's not there, get 0

        # Calculate Expected Value (EV)
        ev = (model_prob * bookie_odds) - 1
        # ev = (p * (o - 1)) - ((1 - p) * 1)
        # ev = (po - p) - (1 - p)
        # ev = po - p - 1 + p
        # ev = po - 1

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
