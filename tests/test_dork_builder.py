from media_dork_studio.dork_builder import DorkBuilder, DorkConfig


def test_open_directory_query_contains_selected_parts() -> None:
    query = DorkBuilder.build(
        DorkConfig(
            extensions=["mp4", ".MKV"],
            method="Open Directory",
            keywords="nature documentary",
            keyword_alternatives="film, wildlife footage, film",
            exact_phrase=True,
            site="site:.edu",
            exclude_terms="html, php",
            after_date="2025-01-01",
            before_date="2026-01-01",
            size_hint="700 MB",
        )
    )

    assert 'intitle:"index of"' in query
    assert '"nature documentary"' in query
    assert '(film OR "wildlife footage")' in query
    assert "(filetype:mp4 OR filetype:mkv)" in query
    assert "site:.edu" in query
    assert "-html -php" in query
    assert "after:2025-01-01 before:2026-01-01" in query
    assert '"700 MB"' in query


def test_cloud_targets_and_custom_extensions_are_constrained() -> None:
    query = DorkBuilder.build(
        DorkConfig(
            method="Cloud / CDN",
            cloud_targets=["AWS S3", "Azure Blob", "Not Real"],
            custom_extensions=".csv | JSON; ../../bad (evil)",
        )
    )

    assert "site:s3.amazonaws.com" in query
    assert "site:blob.core.windows.net" in query
    assert "Not Real" not in query
    assert "filetype:csv" in query
    assert "filetype:json" in query
    assert "../../bad" not in query


def test_sanitizes_query_control_characters_and_bad_dates() -> None:
    query = DorkBuilder.build(
        DorkConfig(
            method="Generic",
            keywords='report" OR site:example.com',
            exact_phrase=True,
            site="https://EXAMPLE.com/path?q=1",
            exclude_terms="-html, site:evil.test, ok_term",
            after_date="not-a-date",
        )
    )

    assert '"report OR site example.com"' in query
    assert "site:example.com" in query
    assert "site:evil.test" not in query
    assert "-html" in query
    assert "-ok_term" in query
    assert "after:" not in query


def test_cloud_method_defaults_to_all_providers() -> None:
    query = DorkBuilder.build(DorkConfig(method="Cloud / CDN"))
    for hostname in DorkBuilder.CLOUD_TARGETS.values():
        assert f"site:{hostname}" in query
