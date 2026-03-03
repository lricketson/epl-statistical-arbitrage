# English Premier League Statistical ArbitrageE Engine

===
An end-to-end model for identifying bets on the English Premier League that have a positive expected value, using a Poisson Generalised Linear Model.

## Executive Summary

Sports betting is a multi-billion dollar industry, and the Premier League is the most-watched sports league in the world. Bookmakers (or 'bookies') use predictive models to set odds for match outcomes, implementing a small 'house edge' in the setup of the odds to ensure that they will win in the long run.
This project aims to beat them at their own game. It scrapes data from a hidden API used by Understat.com, predicts match outcomes using Poisson Regression, and compares these probabilistic predictions with live Pinnacle odds scraped from The-Odds-API, finally outputting a CSV of bets with positive expected value. It was built as a paper-trading environment to explore quantitative sports modelling without financial risk.

### Maths and Modelling

Poisson Regression was used to predict match outcomes: continuous lambdas for xG and xGA were found with Poisson Regression, and then the match outcomes were predicted by counting the number of goals (discrete) using those lambdas. The discreteness of the Poisson distribution fits the integer count of goals scored perfectly. Recent matches are more relevant to assessing team form, so a half-life of 90 days was used in calculating the weights each match contributed to the overall scores.
