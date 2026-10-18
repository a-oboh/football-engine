from math import exp

import pytest

from football_analytics.analytics.poisson import (
    ExpectedGoals,
    SequentialPoissonModel,
    poisson_probability,
)


def test_poisson_probability_matches_the_formula() -> None:
    probability = poisson_probability(goals=2, expected_goals=1.5)

    assert probability == pytest.approx(exp(-1.5) * 1.5**2 / 2)


def test_score_probability_matrix_has_expected_shape_and_probabilities() -> None:
    expected_goals = ExpectedGoals(home=1.2, away=0.8)

    matrix = expected_goals.score_probability_matrix(max_goals=2)

    assert matrix.shape == (3, 3)
    assert len(matrix.probabilities) == 3
    assert all(len(row) == 3 for row in matrix.probabilities)
    assert matrix.probability(1, 0) == pytest.approx(
        poisson_probability(1, 1.2) * poisson_probability(0, 0.8)
    )
    assert matrix.probabilities[1][0] == matrix.probability(1, 0)


def test_score_probability_matrix_aggregates_home_draw_away_probabilities() -> None:
    expected_goals = ExpectedGoals(home=1.2, away=0.8)
    matrix = expected_goals.score_probability_matrix(max_goals=1)

    outcomes = matrix.outcome_probabilities()

    expected_home_win = matrix.probability(1, 0)
    expected_draw = matrix.probability(0, 0) + matrix.probability(1, 1)
    expected_away_win = matrix.probability(0, 1)
    assert outcomes.home_win == pytest.approx(expected_home_win)
    assert outcomes.draw == pytest.approx(expected_draw)
    assert outcomes.away_win == pytest.approx(expected_away_win)
    assert outcomes.total_probability_mass == pytest.approx(
        expected_home_win + expected_draw + expected_away_win
    )


def test_score_probability_matrix_validates_inputs() -> None:
    with pytest.raises(ValueError, match="Expected goals must not be negative"):
        ExpectedGoals(home=-0.1, away=1.0)

    with pytest.raises(ValueError, match="Expected goals must be finite"):
        ExpectedGoals(home=float("inf"), away=1.0)

    with pytest.raises(ValueError, match="max_goals must be an integer"):
        ExpectedGoals(home=1.0, away=1.0).score_probability_matrix(max_goals=1.5)

    with pytest.raises(ValueError, match="max_goals must not be negative"):
        ExpectedGoals(home=1.0, away=1.0).score_probability_matrix(max_goals=-1)

    matrix = ExpectedGoals(home=1.0, away=1.0).score_probability_matrix(max_goals=1)

    with pytest.raises(ValueError, match="home_goals must be within"):
        matrix.probability(2, 0)

    with pytest.raises(ValueError, match="away_goals must not be negative"):
        matrix.probability(0, -1)


def test_finite_score_probability_mass_is_truncated_and_monotonic() -> None:
    expected_goals = ExpectedGoals(home=1.5, away=1.1)

    small_matrix = expected_goals.score_probability_matrix(max_goals=1)
    larger_matrix = expected_goals.score_probability_matrix(max_goals=8)

    assert 0 < small_matrix.total_probability_mass < 1
    assert small_matrix.total_probability_mass < larger_matrix.total_probability_mass
    assert larger_matrix.total_probability_mass < 1
    retained_mass = larger_matrix.outcome_probabilities().total_probability_mass
    assert retained_mass == pytest.approx(larger_matrix.total_probability_mass)


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
