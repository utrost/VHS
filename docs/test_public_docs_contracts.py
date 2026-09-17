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
