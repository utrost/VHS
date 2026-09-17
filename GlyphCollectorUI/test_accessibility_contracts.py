import re
from pathlib import Path

HTML = Path(__file__).with_name("GlyphCollectorUI.html").read_text(encoding="utf-8")


def _tag_for_id(control_id: str) -> str:
    match = re.search(rf"<(?P<tag>input|select|textarea|button)\b(?=[^>]*\bid=\"{re.escape(control_id)}\")[^>]*>", HTML, re.S)
    assert match, f"missing control #{control_id}"
    return match.group(0)


def test_collector_static_controls_have_programmatic_labels():
    for control_id in [
        "charInput", "queueInput", "coveragePreset", "coverageCustom",
        "previewServer", "previewFont", "cfgFontFamily", "cfgCount", "cfgWidth",
        "cfgHeight", "cfgBaseline", "cfgXHeight", "cfgDisplayScale",
        "cfgTemplateFont", "cfgTemplateOpacity", "cfgNormStrength",
    ]:
        tag = _tag_for_id(control_id)
        has_label = re.search(rf"<label\b[^>]*\bfor=\"{re.escape(control_id)}\"", HTML)
        has_aria = re.search(r"\baria-label=\"[^\"]+\"|\baria-labelledby=\"[^\"]+\"", tag)
        assert has_label or has_aria, f"#{control_id} needs a programmatic label"


def test_collector_icon_and_toggle_buttons_have_accessible_names_and_state():
    for button_id, label in [
        ("smoothToggle", "Toggle smooth preview"),
        ("bezierToggle", "Toggle Bezier curve fitting"),
        ("normalizeToggle", "Toggle stroke normalization"),
        ("templateToggle", "Toggle template overlay"),
        ("folderBtn", "Connect font folder"),
    ]:
        tag = _tag_for_id(button_id)
        assert f'aria-label="{label}"' in tag, button_id
    for button_id in ["smoothToggle", "bezierToggle", "normalizeToggle", "templateToggle"]:
        tag = _tag_for_id(button_id)
        assert 'aria-pressed="' in tag, button_id
    assert 'aria-label="Open settings"' in HTML
    assert 'aria-label="Open font coverage dashboard"' in HTML
    assert 'aria-label="Open live Assembler preview"' in HTML
    assert 'aria-label="Close font coverage dashboard"' in HTML


def test_collector_generated_canvases_and_slot_controls_are_named_and_keyboard_reachable():
    for required in [
        "canvas.tabIndex = 0",
        "canvas.setAttribute('role', 'img')",
        "updateCanvasAccessibility(slotData)",
        "function updateCanvasAccessibility(slot)",
        "Variant ${slot.id + 1} drawing area",
        "Freehand drawing uses pointer or stylus input",
        "clearBtn.setAttribute('aria-label'",
        "Clear variant ${i + 1}",
        "focus:opacity-100",
    ]:
        assert required in HTML, f"collector accessibility contract missing {required}"
    assert "opacity-0 group-hover:opacity-100 transition" not in HTML


def test_collector_slot_mutation_paths_refresh_canvas_accessibility():
    for fn in ["clearSlot", "clearAll", "undo", "redo", "loadExistingGlyph", "autoRestore"]:
        match = re.search(rf"function\s+{fn}\s*\([^)]*\)\s*\{{(?P<body>.*?)\n\s*function\s+", HTML, re.S)
        assert match, f"missing {fn}"
        assert "updateCanvasAccessibility" in match.group("body"), f"{fn} must refresh canvas ARIA labels after mutations"


def test_collector_preview_panel_close_button_has_close_name():
    assert 'aria-label="Close live Assembler preview"' in HTML


def test_collector_toggle_state_updates_keep_aria_pressed_in_sync():
    for fn, button_id in [
        ("toggleSmooth", "smoothToggle"),
        ("toggleBezier", "bezierToggle"),
        ("toggleNormalize", "normalizeToggle"),
        ("toggleTemplate", "templateToggle"),
    ]:
        match = re.search(rf"function\s+{fn}\s*\([^)]*\)\s*\{{(?P<body>.*?)\n\s*function\s+", HTML, re.S)
        assert match, f"missing {fn}"
        body = match.group("body")
        assert f"getElementById('{button_id}')" in body or f'getElementById("{button_id}")' in body
        assert "setAttribute('aria-pressed'" in body or 'setAttribute("aria-pressed"' in body
