# English Premier League Statistical Arbitrage Engine

An end-to-end model for identifying bets on the English Premier League that have a positive expected value, using a Poisson Generalised Linear Model.

## Executive Summary

- Sports betting is a multi-billion dollar industry, and the Premier League is the most-watched sports league in the world. Bookmakers (or 'bookies') use predictive models to set odds for match outcomes, implementing a small 'house edge' in the setup of the odds to ensure that they will win in the long run.
- This project aims to beat them at their own game. It scrapes data from a hidden API used by Understat.com, predicts match outcomes using Poisson Regression, and compares these probabilistic predictions with live Pinnacle odds scraped from The-Odds-API, finally outputting a CSV of bets with positive expected value. It was built as a paper-trading environment to explore quantitative sports modelling without financial risk.

### Maths and Modelling

- **Poisson Regression:** A Poisson Generalised Linear Model (GLM) was used to ensure the predicted xG (continuous $\lambda$) never dropped below zero.
- **Probability Matrix:** These predicted lambdas were then fed into a Poisson distribution with respect to each match outcome, and probabilities were predicted by creating a matrix of Poisson pmf values multiplied together for each combination of home/away number of goals, with these two counts assumed to be independent.
- **Dixon-Coles Adjustment:** The only exception to the independence assumption was in the case of 0-0 and 1-1 draws, where empirical testing has revealed that Poisson Regression tends to underestimate the true probability of these scorelines, due to nuance in team objectives. In these cases the Dixon-Coles adjustment was used with an industry standard rho of $-0.15$.
- **Half-Life Decay** In calculating the lambdas, recent matches were intuited to be more relevant to assessing team form, so a half-life of 90 days was used in calculating the weights each match contributed to the overall scores.
- **A Feature as Noise:** Rest differential, measured by the difference between the two teams' numbers of rest days between games, was initially taken into account as a factor in the regression model. But after inspecting the model's coefficients, rest was discovered to have a p-value of 0.877, meaning there was an 87.7% chance that rest differential had zero predictive power over xG.

### Data Pipeline and Engineering

- **Secret API Sourcing:** The match data was sourced from Understat. At first an attempt was made to scrape the data from FBref, but FBref's Cloudflare protection made it impossible to scrape with a bot. Because I'd hit a wall with FBref, I instead turned to Understat, and while they too had Cloudflare, after inspecting Understat's page and going to Network, it was found that it gets its data from a hidden, unprotected API, so the data ingestion engine for this project was hooked up to that as well, employing a User-Agent that got a cookie from the main page before accessing the API.
- **Market Sourcing:** Live odds were scraped from Pinnacle, using a permissive API called The-Odds-API.
- **Entity Resolution:** A recurring issue was the fact that different APIs used slightly different names for different teams, such as "AFC Bournemouth" and "Bournemouth". To resolve these differences, a name mapper dictionary was used as a standardising intermediary whenever API output was being processed. Strings were also converted to datetime objects on occasion when working with match dates, another example of discrepancies between API outputs.

### Risk Management

- **Ruin through Variance:** Even with positive EV bets, variance in returns can still cause the loss of a bettor's entire bankroll. An extreme example of this is as follows: a naive bettor is overjoyed to calculate she has a 5% edge in a bet, and eagerly puts her entire bankroll on it. She loses, and her bankroll is wiped out. While the Law of Large Numbers theoretically guarantees positive returns from positive EV bets in the long run, it says nothing of the short run, and a bettor's bankroll is susceptible to huge fluctuations after any given bet.
- **Kelly Criterion:** To guard against ruin from variance in wins, this model uses the Kelly Criterion, a mathematical formula calculates the optimal wager for long-term wealth growth to put on bets depending on their odds and percentage edge. For further protection against variance, the 'Fractional Kelly' was used, only betting half of what a normal Kelly formula would output.
- **EV Ceiling:** A cap on the EV of 10% was put into place to avoid hallucinating huge edges caused by the model missing data on factors like injuries.
- **Mutually Exclusive:** Where multiple edges were found on bets regarding the same match, only the one with the highest EV% was kept, to ensure bets did not conflict.

### Tech Stack and Libraries

Language: Python 3.10.6
Data Scraping & Manipulation: requests, pandas
Maths and Machine Learning: statsmodels, scipy, scikit-learn
Compute Environment: Jupyter Notebooks

To use this yourself, get an API key from The-Odds-API and put it in your .env file

1. Clone the repo and install dependencies: `pip install pandas scipy requests statsmodels scikit-learn`
2. Get a free API key from The-Odds-API
3. Create a .env file in the root directory and add your key as `ODDS_API_KEY=your_key_here`.
4. Run the script as `python main.py`
   _This script will output a timestamped CSV of actionable +EV bets._

### Limitations

- **Missing Factors:** This model incorporates xG/xGA, time decay and the Dixon-Coles adjustment, but it misses several factors likely useful in calculating match outcome probabilities: injuries, weather, club internal issues like dissent/a new manager, and stage of the season.
- **Future Scope:** Future for the project could include implementing data such as recent form of a squad's players or a spatiotemporal feed showing player positions over 90 minutes, which is available online for a price. It was decided for these to be omitted due to diminishing returns.
