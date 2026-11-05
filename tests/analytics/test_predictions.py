from datetime import date

import pytest

from football_analytics.analytics.predictions import predict_fixture
from football_analytics.db.repository import CompletedMatch


class _RepositoryStub:
    def __init__(self, matches: list[CompletedMatch]) -> None:
        self.matches = matches

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: tuple[str, ...] | None = None,
    ) -> list[CompletedMatch]:
        return self.matches


def test_predict_fixture_replays_completed_history() -> None:
    repository = _RepositoryStub(
        [
            CompletedMatch(
                competition_code="EPL",
                season_name="2025-26",
                match_date=date(2025, 8, 1),
                kickoff_time=None,
                home_team="A",
                away_team="B",
                home_goals=2,
                away_goals=1,
                result="H",
                home_half_time_goals=1,
                away_half_time_goals=0,
            )
        ]
    )

    prediction = predict_fixture(
        repository,
        competition_code="EPL",
        season_names=["2025-26"],
        home_team="B",
        away_team="A",
    )

    assert prediction.expected_goals.home == 2.0
    assert prediction.expected_goals.away == 1.0
    outcome_sum = (
        prediction.outcomes.home_win
        + prediction.outcomes.draw
        + prediction.outcomes.away_win
    )
    assert outcome_sum == pytest.approx(prediction.outcomes.total_probability_mass)
    assert prediction.full_time_score.probability == pytest.approx(
        max(
            probability
            for row in prediction.score_probabilities.probabilities
            for probability in row
        )
    )
    assert prediction.half_time.expected_goals.home == 1.0
    assert prediction.half_time.expected_goals.away == 0.0
    assert prediction.markets.home_win.fair_odds == pytest.approx(
        1 / prediction.markets.home_win.probability
    )
    assert prediction.markets.over_2_5_goals.probability == pytest.approx(
        1 - prediction.markets.under_2_5_goals.probability
    )
    assert prediction.markets.both_teams_to_score_yes.probability == pytest.approx(
        1 - prediction.markets.both_teams_to_score_no.probability
    )


def test_predict_fixture_rejects_teams_absent_from_history() -> None:
    repository = _RepositoryStub(
        [
            CompletedMatch(
                competition_code="EPL",
                season_name="2025-26",
                match_date=date(2025, 8, 1),
                kickoff_time=None,
                home_team="A",
                away_team="B",
                home_goals=2,
                away_goals=1,
                result="H",
                home_half_time_goals=1,
                away_half_time_goals=0,
            )
        ]
    )

    with pytest.raises(ValueError, match="absent from match history"):
        predict_fixture(
            repository,
            competition_code="EPL",
            season_names=["2025-26"],
            home_team="A",
            away_team="C",
        )
