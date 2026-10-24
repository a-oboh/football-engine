from datetime import date

import pytest

from football_analytics.analytics.experiments import run_poisson_experiment
from football_analytics.db.repository import CompletedMatch


class _RepositoryStub:
    def __init__(self, matches: list[CompletedMatch]) -> None:
        self.matches = matches
        self.request: tuple[str, tuple[str, ...] | None] | None = None

    def get_completed_matches(
        self,
        *,
        competition_code: str,
        season_names: tuple[str, ...] | None = None,
    ) -> list[CompletedMatch]:
        self.request = (competition_code, season_names)
        return [
            match
            for match in self.matches
            if season_names is None or match.season_name in season_names
        ]


def test_experiment_warms_up_on_prior_seasons_and_scores_target_season() -> None:
    repository = _RepositoryStub(
        [
            _match("2024-25", date(2024, 8, 1), "A", "B", 2, 1, "H"),
            _match("2025-26", date(2025, 8, 1), "B", "A", 0, 2, "A"),
        ]
    )

    experiment = run_poisson_experiment(
        repository,
        competition_code="EPL",
        warmup_season_names=["2024-25"],
        evaluation_season_names=["2025-26"],
    )

    assert repository.request == ("EPL", ("2024-25", "2025-26"))
    assert experiment.predictions["season_name"].tolist() == ["2025-26"]
    assert experiment.predictions["expected_home_goals"].tolist() == [2.0]
    assert experiment.predictions["expected_away_goals"].tolist() == [1.0]
    assert experiment.evaluation.matches == 1


def test_experiment_rejects_overlapping_seasons() -> None:
    repository = _RepositoryStub([])

    with pytest.raises(ValueError, match="must not overlap"):
        run_poisson_experiment(
            repository,
            competition_code="EPL",
            warmup_season_names=["2024-25"],
            evaluation_season_names=["2024-25"],
        )


def test_experiment_rejects_missing_evaluation_matches() -> None:
    repository = _RepositoryStub(
        [_match("2024-25", date(2024, 8, 1), "A", "B", 2, 1, "H")]
    )

    with pytest.raises(ValueError, match="evaluation seasons"):
        run_poisson_experiment(
            repository,
            competition_code="EPL",
            warmup_season_names=["2024-25"],
            evaluation_season_names=["2025-26"],
        )


def _match(
    season_name: str,
    match_date: date,
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
    result: str,
) -> CompletedMatch:
    return CompletedMatch(
        competition_code="EPL",
        season_name=season_name,
        match_date=match_date,
        kickoff_time=None,
        home_team=home_team,
        away_team=away_team,
        home_goals=home_goals,
        away_goals=away_goals,
        result=result,
    )
