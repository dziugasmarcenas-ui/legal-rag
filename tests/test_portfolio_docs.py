from pathlib import Path


ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"
PORTFOLIO_FILES = (
    ROOT / "docs" / "portfolio" / "CASE_STUDY.md",
    ROOT / "docs" / "portfolio" / "DEMO.md",
    ROOT / "docs" / "portfolio" / "APPLICATION_BULLETS.md",
)


def test_readme_presents_a_completed_v1_with_verified_metrics():
    text = README.read_text(encoding="utf-8")

    assert "Status: V1 shipped" in text
    assert "build sprint in progress" not in text
    assert text.count("## Methodology and integrity notes") == 1
    assert "Recall@1" in text and "0.720" in text and "0.880" in text
    assert "Recall@3" in text and "0.840" in text and "0.920" in text


def test_readme_links_to_each_presentation_artifact():
    text = README.read_text(encoding="utf-8")

    for path in PORTFOLIO_FILES:
        assert path.exists(), f"missing {path.relative_to(ROOT)}"
        relative = path.relative_to(ROOT).as_posix()
        assert relative in text, f"README does not link to {relative}"


def test_presentation_scope_contains_no_v2_roadmap():
    text = README.read_text(encoding="utf-8")

    assert not (ROOT / "V2_PLAN.md").exists()
    assert "V2_PLAN.md" not in text
