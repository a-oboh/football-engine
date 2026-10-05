from math import exp

import pytest

from football_analytics.analytics.poisson import (
    SequentialPoissonModel,
    poisson_probability,
)


def test_poisson_probability_matches_the_formula() -> None:
    probability = poisson_probability(goals=2, expected_goals=1.5)

    assert probability == pytest.approx(exp(-1.5) * 1.5**2 / 2)


def test_initial_state_uses_configured_league_rates_and_neutral_strengths() -> None:
    model = SequentialPoissonModel(initial_home_goals=1.5, initial_away_goals=1.2)

    expected = model.predict("A", "B")

    assert expected.home == 1.5
    assert expected.away == 1.2


def test_prediction_uses_home_and_away_strengths_from_prior_results() -> None:
    model = SequentialPoissonModel(initial_home_goals=1.5, initial_away_goals=1.2)
    model.record_result("A", "B", home_goals=3, away_goals=1)
    model.record_result("C", "A", home_goals=0, away_goals=2)

    expected = model.predict("A", "B")

    assert expected.home == pytest.approx(6.0)
    assert expected.away == pytest.approx(2 / 3)


def test_predicting_before_recording_prevents_current_match_leakage() -> None:
    model = SequentialPoissonModel(initial_home_goals=1.5, initial_away_goals=1.2)

    before_result = model.predict("A", "B")
    model.record_result("A", "B", home_goals=2, away_goals=1)
    after_result = model.predict("A", "B")

    assert before_result.home == 1.5
    assert before_result.away == 1.2
    assert after_result.home == 2.0
    assert after_result.away == 1.0


def test_future_result_cannot_change_an_earlier_prediction() -> None:
    model = SequentialPoissonModel(initial_home_goals=1.5, initial_away_goals=1.2)
    model.record_result("A", "B", home_goals=2, away_goals=1)

    prediction_for_second_match = model.predict("B", "A")
    model.record_result("B", "A", home_goals=9, away_goals=0)

    assert prediction_for_second_match.home == 2.0
    assert prediction_for_second_match.away == 1.0
