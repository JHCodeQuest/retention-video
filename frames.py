"""Renders one 16:9 video frame per script segment from the PDF: the page
on a dark background, zoomed towards the focused text with a highlight box,
plus a burned-in caption of the narration."""
import textwrap
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1920, 1080
CAPTION_HEIGHT = 200
RENDER_SCALE = 4  # PDF points -> pixels
BACKGROUND = (18, 22, 30)
HIGHLIGHT = (255, 190, 40)


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def find_text_box(textpage, page_height_pt: float, needle: str):
    """Bounding box of `needle` in rendered-pixel coords, or None. For a
    table row the box is widened to the full content width so the whole
    row gets highlighted, not just the client name."""
    searcher = textpage.search(needle, match_case=True)
    match = searcher.get_next()
    if match is None:
        return None
    start, count = match
    boxes = [textpage.get_charbox(i) for i in range(start, start + count)]
    left = min(b[0] for b in boxes)
    right = max(b[2] for b in boxes)
    bottom = min(b[1] for b in boxes)
    top = max(b[3] for b in boxes)
    # PDF origin is bottom-left; image origin is top-left
    return (left * RENDER_SCALE, (page_height_pt - top) * RENDER_SCALE,
            right * RENDER_SCALE, (page_height_pt - bottom) * RENDER_SCALE)


def _content_bbox(page_img: Image.Image) -> tuple[int, int, int, int]:
    """Extent of non-white pixels: used to frame shots and stretch row highlights."""
    bbox = Image.eval(page_img.convert("L"), lambda v: 255 - v).getbbox()
    return bbox or (0, 0, page_img.width, page_img.height)


def _crop_for(content, box, view_h: int):
    """Choose a crop matching the view's aspect ratio, always wide enough to
    show the full content width: the whole report for full-page shots, or a
    tighter band centred on `box`. May extend past the page edge; the caller
    fills that with white."""
    aspect = WIDTH / view_h
    pad = 12 * RENDER_SCALE
    left, top, right, bottom = content
    cx = (left + right) / 2
    if box is None:
        crop_h = (bottom - top) + 2 * pad
        crop_w = max(crop_h * aspect, (right - left) + 2 * pad)
        crop_h = crop_w / aspect
        cy = (top + bottom) / 2
    else:
        crop_w = (right - left) + 2 * pad
        crop_h = crop_w / aspect
        cy = (box[1] + box[3]) / 2
        # stay within the report: no empty space above or below it
        cy = min(cy, bottom + pad - crop_h / 2)
        cy = max(cy, top - pad + crop_h / 2)
    x0, y0 = cx - crop_w / 2, cy - crop_h / 2
    return (x0, y0, x0 + crop_w, y0 + crop_h)


def _crop_on_white(img: Image.Image, region) -> Image.Image:
    x0, y0, x1, y1 = (int(round(v)) for v in region)
    out = Image.new("RGB", (x1 - x0, y1 - y0), (255, 255, 255))
    out.paste(img, (-x0, -y0))
    return out


def render_frames(pdf_path: Path, segments, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[0]
    page_h_pt = page.get_height()
    page_img = page.render(scale=RENDER_SCALE).to_pil().convert("RGB")
    textpage = page.get_textpage()
    content = _content_bbox(page_img)
    content_left, content_right = content[0], content[2]

    caption_font = _font(44)
    view_h = HEIGHT - CAPTION_HEIGHT
    paths = []

    for i, seg in enumerate(segments):
        box = find_text_box(textpage, page_h_pt, seg.focus) if seg.focus else None
        page_copy = page_img.copy()
        if box is not None:
            pad = 6 * RENDER_SCALE
            row = (content_left - pad, box[1] - pad, content_right + pad, box[3] + pad)
            draw = ImageDraw.Draw(page_copy)
            draw.rectangle(row, outline=HIGHLIGHT, width=3 * RENDER_SCALE)

        crop = _crop_on_white(page_copy, _crop_for(content, box, view_h))
        crop.thumbnail((WIDTH - 160, view_h - 60), Image.LANCZOS)

        frame = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
        frame.paste(crop, ((WIDTH - crop.width) // 2, (view_h - crop.height) // 2 + 20))

        draw = ImageDraw.Draw(frame)
        lines = textwrap.wrap(seg.text, width=70)[:3]
        line_h = 56
        y = view_h + (CAPTION_HEIGHT - line_h * len(lines)) // 2
        for line in lines:
            w = draw.textlength(line, font=caption_font)
            draw.text(((WIDTH - w) / 2, y), line, font=caption_font, fill=(240, 240, 240))
            y += line_h

        path = out_dir / f"frame_{i:02d}.png"
        frame.save(path)
        paths.append(path)

    textpage.close()
    pdf.close()
    return paths
