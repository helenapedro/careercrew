"""CLI entrypoint.

    python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt
    python main.py --resume-text "..." --jd "We need a Python engineer."
    python main.py --resume samples/sample_resume.txt --jd-url https://example.com/job

Needs OPENAI_API_KEY for the full crew; without it the deterministic MCP
fallback still runs. See .env.example.
"""

from __future__ import annotations

import argparse
import os
import shutil

from dotenv import load_dotenv

from careercrew.guardrails import check_upload, redact_pii
from careercrew.pipeline import AnalysisRequest, make_package_id, run_analysis


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CareerCrew: multi-agent resume coach")
    parser.add_argument("--resume", help="Path to a resume file (PDF, DOCX, or TXT)")
    parser.add_argument("--resume-text", help="Pasted resume text (alternative to --resume)")
    parser.add_argument("--jd", help="Path to a JD text file or the pasted JD text")
    parser.add_argument("--jd-url", help="An https URL to fetch the JD from")
    parser.add_argument(
        "--screening",
        action="append",
        default=[],
        help="A screening question (repeat the flag for each question)",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    if not args.resume and not args.resume_text:
        raise SystemExit("Provide --resume <file> or --resume-text <text>.")
    if not args.jd and not args.jd_url:
        raise SystemExit("Provide --jd <file|text> or --jd-url <https url>.")

    upload_dir = os.environ.get("CAREERCREW_UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    resume_path: str | None = None
    if args.resume:
        check_upload(args.resume)  # input guardrail: type + size
        resume_path = os.path.join(upload_dir, os.path.basename(args.resume))
        shutil.copyfile(args.resume, resume_path)
        resume_path = os.path.basename(resume_path)

    jd_source = args.jd_url or args.jd or ""
    if args.jd and os.path.isfile(args.jd):
        with open(args.jd, encoding="utf-8") as handle:
            jd_source = handle.read()
    jd_source = redact_pii(jd_source)  # input guardrail: PII out before LLM calls

    request = AnalysisRequest(
        package_id=make_package_id(),
        resume_path=resume_path,
        resume_text=redact_pii(args.resume_text) if args.resume_text else None,
        jd_source=jd_source,
        screening_questions=args.screening,
    )

    result = run_analysis(request)
    print(result.package.model_dump_json(indent=2))
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
