from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_webengine_reports_javascript_source_and_line():
    source = (ROOT / 'mary' / 'desktop' / 'window.py').read_text(encoding='utf-8')
    assert 'class MaryWebEnginePage(QWebEnginePage):' in source
    assert 'javaScriptConsoleMessage' in source
    assert '[MaryDesktop][JS]' in source
    assert 'source_id' in source
    assert 'line_number' in source
    assert 'self.web.setPage(MaryWebEnginePage(self.web))' in source
