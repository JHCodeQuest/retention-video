"""Generate a narrated walkthrough video of a client retention report.

    python main.py                          # mock clients, ElevenLabs if key set
    python main.py --clients sample.json    # your own fictional client list
    python main.py --script-only            # print the narration, no rendering
"""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

import pipeline
import report
import script

ROOT = Path(__file__).resolve().parent


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clients", type=Path, help="JSON list of {name, monthly_revenue_gbp, monthly_cost_gbp}")
    parser.add_argument("--template", type=Path, default=script.TEMPLATE_PATH, help="narration wording")
    parser.add_argument("--out", type=Path, help="output MP4 path (default: output/<timestamp>/report.mp4)")
    parser.add_argument("--script-only", action="store_true", help="print the narration and exit")
    args = parser.parse_args()

    run_dir = (args.out.parent if args.out else ROOT / "output" / time.strftime("%Y%m%d-%H%M%S"))
    out_mp4 = args.out or run_dir / "report.mp4"

    clients = report.load_clients(args.clients)
    results, pdf_path, urgency = report.build_report(clients, run_dir / "client-retention-report.pdf")

    if args.script_only:
        for seg in script.build_script(results, urgency, report.format_gbp, args.template):
            print(f"[{seg.focus or 'full page'}] {seg.text}")
        return

    print(f"PDF:      {pdf_path}")
    voiced = bool(os.environ.get("ELEVENLABS_API_KEY"))
    print(f"Audio:    {'ElevenLabs' if voiced else 'silent placeholders (no ELEVENLABS_API_KEY)'}")

    mp4, segments = pipeline.render_video(results, urgency, pdf_path, out_mp4,
                                          work_dir=run_dir, template=args.template)
    (run_dir / "script.json").write_text(
        json.dumps([seg.__dict__ for seg in segments], indent=2), encoding="utf-8")
    print(f"Frames:   {len(segments)}")
    print(f"Video:    {mp4}")


if __name__ == "__main__":
    main()
