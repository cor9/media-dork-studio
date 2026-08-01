import pytest

from media_dork_studio.smart_advisor import SmartAdvisor, UnsafeGoalError


def test_recommends_government_dataset_strategy() -> None:
    strategy = SmartAdvisor.suggest("find public government wildfire datasets")

    assert strategy.method == "Generic"
    assert strategy.site == ".gov"
    assert strategy.keywords == "wildfire"
    assert {"csv", "json", "xlsx"}.issubset(strategy.extensions)
    assert "open data" in strategy.alternatives


def test_recommends_lossless_audio_and_open_directories() -> None:
    strategy = SmartAdvisor.suggest("high quality lossless live jazz recordings")

    assert strategy.method == "Open Directory"
    assert strategy.extensions[:2] == ("flac", "wav")
    assert "jazz" in strategy.keywords


def test_selects_named_cloud_provider() -> None:
    strategy = SmartAdvisor.suggest("AWS S3 public climate datasets")

    assert strategy.method == "Cloud / CDN"
    assert strategy.cloud_targets == ("AWS S3",)
    assert "csv" in strategy.extensions


@pytest.mark.parametrize(
    "goal",
    [
        "find exposed passwords",
        "locate private API keys",
        "search for .env files",
        "discover social security numbers",
    ],
)
def test_refuses_sensitive_data_goals(goal: str) -> None:
    with pytest.raises(UnsafeGoalError):
        SmartAdvisor.suggest(goal)
