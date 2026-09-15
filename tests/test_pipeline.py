import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import frames
import report
import script
import tts
import video

CLIENTS = [
    {"name": "Alpha Ltd", "monthly_revenue_gbp": 10000, "monthly_cost_gbp": 5000},
    {"name": "Beta Ltd", "monthly_revenue_gbp": 3000, "monthly_cost_gbp": 2900},
    {"name": "Gamma Ltd", "monthly_revenue_gbp": 1000, "monthly_cost_gbp": 1200},
]


@pytest.fixture
def built(tmp_path):
    results, pdf, urgency = report.build_report(CLIENTS, tmp_path / "report.pdf")
    segments = script.build_script(results, urgency, report.format_gbp, month="January 2026")
    return results, pdf, segments


def test_script_covers_every_recommendation(built):
    _, _, segments = built
    keys = [s.key for s in segments]
    assert keys == ["intro", "headline", "retain_top", "review:Beta Ltd", "drop:Gamma Ltd", "outro"]
    assert "£5,000 profit, a 50 percent margin" in segments[2].text
    assert "costing £200 more" in segments[4].text
    assert segments[-1].text.startswith("That's 1 to retain, 1 to review, and 1 to drop")


def test_spoken_text_says_pounds_not_symbols():
    assert script.spoken_text("profit of £12,450 and -£150") == (
        "profit of twelve thousand, four hundred and fifty pounds and minus a hundred and fifty pounds")
    assert script.spoken_text("just £1") == "just one pound"
    assert "£" not in script.spoken_text("costing £400 more")


@pytest.mark.parametrize("n, words", [
    (7, "seven"), (40, "forty"), (99, "ninety-nine"), (100, "a hundred"), (150, "a hundred and fifty"),
    (950, "nine hundred and fifty"), (1000, "a thousand"), (1100, "a thousand, one hundred"),
    (5020, "five thousand and twenty"), (12450, "twelve thousand, four hundred and fifty"),
    (6500, "six thousand, five hundred"), (1_250_000, "a million, two hundred and fifty thousand"),
])
def test_number_words(n, words):
    assert script.number_words(n) == words


def test_every_focus_is_found_on_the_pdf(built):
    _, pdf, segments = built
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    page = doc[0]
    textpage = page.get_textpage()
    for seg in segments:
        if seg.focus:
            assert frames.find_text_box(textpage, page.get_height(), seg.focus) is not None, seg.focus
    textpage.close()
    doc.close()


def test_end_to_end_offline_render(built, tmp_path):
    _, pdf, segments = built
    frame_paths = frames.render_frames(pdf, segments, tmp_path / "frames")
    audios = [tts.synthesize(s.spoken, tmp_path / "cache", api_key="") for s in segments]
    out = video.assemble(frame_paths, audios, tmp_path / "out.mp4", tmp_path / "clips")
    expected = sum(video.audio_seconds(a) + video.PAUSE_SECONDS for a in audios)
    assert video.audio_seconds(out) == pytest.approx(expected, abs=0.5)


def test_elevenlabs_request_and_cache(tmp_path, monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        content = b"ID3fake-mp3"

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResp()

    monkeypatch.setattr(tts.requests, "post", fake_post)
    first = tts.synthesize("Hello", tmp_path, api_key="k", voice_id="v1", model_id="m1")
    second = tts.synthesize("Hello", tmp_path, api_key="k", voice_id="v1", model_id="m1")

    assert first == second and first.read_bytes() == b"ID3fake-mp3"
    assert len(calls) == 1  # second call served from cache
    url, kwargs = calls[0]
    assert url.endswith("/v1/text-to-speech/v1")
    assert kwargs["headers"]["xi-api-key"] == "k"
    assert kwargs["json"] == {"text": "Hello", "model_id": "m1"}
