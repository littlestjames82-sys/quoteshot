"""Photos, privacy, escaping, and the no-network / no-AI gate."""
import json
import re
from pathlib import Path

from conftest import (SRC, add_item, init_job, make_png, out_text, render,
                      run_cli)


def test_add_photo_records_png_dimensions_and_no_invented_exif(tmp_path):
    photo = make_png(tmp_path / "site.png", width=4, height=3)
    job = init_job(tmp_path)
    proc = run_cli(["add-photo", job, photo])
    assert proc.returncode == 0, out_text(proc)
    data = json.loads((job / "job.json").read_text())
    (rec,) = data["photos"]
    assert rec["format"] == "png"
    assert (rec["width"], rec["height"]) == (4, 3)
    assert rec["captured_at"] is None and rec["camera_make"] is None
    assert rec["has_gps"] is False
    assert (job / "photos" / "site.png").is_file()
    _html, txt = render(job)
    assert "site.png" in txt


def test_non_image_is_rejected_by_name(tmp_path):
    bad = tmp_path / "notes.txt"
    bad.write_text("not a photo")
    job = init_job(tmp_path)
    proc = run_cli(["add-photo", job, bad])
    assert proc.returncode != 0
    assert "notes.txt" in out_text(proc)
    data = json.loads((job / "job.json").read_text())
    assert data["photos"] == []


def test_rendered_quote_never_prints_gps_coordinates(tmp_path):
    job_dir = init_job(tmp_path)
    data = json.loads((job_dir / "job.json").read_text())
    data["photos"].append({
        "filename": "site.png", "stored_as": "photos/site.png",
        "size_bytes": 68, "sha256": "0" * 64, "format": "png",
        "width": 1, "height": 1, "captured_at": None,
        "camera_make": None, "camera_model": None,
        "has_gps": True, "gps_lat": 36.1234567, "gps_lon": -84.7654321,
        "has_exif": True})
    (job_dir / "job.json").write_text(json.dumps(data))
    html, txt = render(job_dir)
    for text in (html, txt):
        assert "36.123" not in text and "-84.765" not in text
        assert "site.png" in text  # listed by filename, coordinates withheld


def test_html_escapes_user_text_text_output_is_verbatim(tmp_path):
    job = init_job(tmp_path, customer="<script>alert(1)</script>")
    add_item(job, "--name", "Work <b>bold</b>", "--price", "10.00", "--qty", "1")
    html, txt = render(job)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in txt  # plain text is verbatim


def test_no_network_or_ai_client_in_source():
    banned = re.compile(
        r"^\s*(?:import|from)\s+(urllib|requests|socket|http\.client|"
        r"httpx|openai|anthropic|aiohttp)\b", re.MULTILINE)
    offenders = []
    for py in sorted((SRC / "quoteshot").rglob("*.py")):
        if banned.search(py.read_text()):
            offenders.append(str(py.relative_to(SRC)))
    assert offenders == [], f"network/AI imports found: {offenders}"
