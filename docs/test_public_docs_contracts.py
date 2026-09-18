from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
COLLECTOR = (ROOT / "GlyphCollectorUI" / "GlyphCollectorUI.html").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github" / "workflows" / "deploy-pages.yml").read_text(encoding="utf-8")


def test_readme_labels_hosted_pages_as_collector_only_and_local_gui_as_assembler():
    assert "Hosted collector demo" in README
    assert "collector-only" in README.lower()
    assert "Local Assembler GUI" in README
    assert "server-backed assembly" in README.lower()


def test_collector_header_navigation_stays_inside_project_or_explains_local_gui():
    assert 'href="/"' not in COLLECTOR
    assert 'data-demo-note="collector-only"' in COLLECTOR
    assert "Local Assembler GUI" in COLLECTOR


def test_pages_workflow_declares_collector_only_static_artifact():
    assert "collector-only" in DEPLOY.lower()
    assert "GlyphCollectorUI/GlyphCollectorUI.html" in DEPLOY
    assert "_site/index.html" in DEPLOY


def test_readme_does_not_present_tracer_as_in_repo_component():
    assert "`TracerUI/`" not in README
    assert "docs/GUIDE_TRACER.md" not in README
    assert "docs/ARCHITECTURE_TRACER.md" not in README
    assert "Tracer has moved" in README


def test_tracer_docs_are_explicit_migration_notes_not_runnable_instructions():
    for path in [ROOT / "docs" / "GUIDE_TRACER.md", ROOT / "docs" / "ARCHITECTURE_TRACER.md"]:
        text = path.read_text(encoding="utf-8")
        assert "moved" in text.lower() or "archived" in text.lower()
        assert "dedicated Tracer" in text
        assert "https://github.com/utrost/" in text
        assert "Open `TracerUI/TracerUI.html`" not in text


def test_validation_scripts_use_shipped_sample_font_not_private_font():
    validation_root = ROOT / "Validation Scripts"
    offenders = []
    for path in validation_root.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "utrost" in text or "glyphs/utrost" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "validation scripts must use shipped font1, not private utrost font: " + ", ".join(offenders)


def test_screenshot_regeneration_playwright_dependency_is_declared_and_documented():
    req = (ROOT / "requirements-docs.txt").read_text(encoding="utf-8")
    assert "playwright" in req.lower()
    for path in [
        ROOT / "docs" / "GUIDE_ASSEMBLER_GUI.md",
        ROOT / "docs" / "GUIDE_ASSEMBLER_CLI.md",
        ROOT / "docs" / "GUIDE_GLYPHCOLLECTOR.md",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "requirements-docs.txt" in text
        assert "playwright install chromium" in text


def test_contributing_quickstart_matches_python310_and_runnable_commands():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Python 3.10+" in text
    assert "Python 3.8+" not in text
    assert "./vhs-gui.sh" in text
    assert "vhs-gui.bat" in text
    assert "python assembler.py" not in text
    assert "python3 assembler.py" in text
    assert "--font font1" in text


def test_docs_describe_current_project_review_hardening():
    readme = README
    gui = (ROOT / "docs" / "GUIDE_ASSEMBLER_GUI.md").read_text(encoding="utf-8")
    collector = (ROOT / "docs" / "GUIDE_GLYPHCOLLECTOR.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "malformed SVG conversion requests return JSON `400`" in readme
    assert "all validation scripts use the shipped `glyphs/font1`" in readme
    assert "returns a JSON `400` error" in gui
    assert "arrow keys for 1 mm steps" in gui
    assert "Ignored while typing in inputs" in collector
    assert "### Fixed" in changelog
    assert "Playwright dependency" in changelog
