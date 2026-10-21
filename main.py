"""Run an analysis from the command line.

What it does: reads a resume and a job description, then runs the pipeline.
Who calls it: `python main.py` during a demo without the browser.
What it returns: prints the prep bundle and the prep plan as JSON.
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
    parser.add_argument("--jd", help="Job description text (or a .txt file path)")
    parser.add_argument(
        "--jd-file",
        help="Path to a JD file to upload (PDF, DOCX, or TXT)",
    )
    parser.add_argument(
        "--seniority",
        default="",
        help=(
            "Optional override for the target experience band "
            "(2-3 years, 5-10 years, or 10+ years). "
            "When omitted, seniority is inferred from the job description."
        ),
    )
    return parser


def main() -> None:
    load_dotenv()
    args = _build_parser().parse_args()

    if not args.resume and not args.resume_text:
        raise SystemExit("Provide --resume <file> or --resume-text <text>.")
    if not args.jd and not args.jd_file:
        raise SystemExit("Provide --jd <text|file> or --jd-file <file>.")

    upload_dir = os.environ.get("CAREERCREW_UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    resume_path: str | None = None
    if args.resume:
        check_upload(args.resume)  # input guardrail: type + size
        resume_path = os.path.join(upload_dir, os.path.basename(args.resume))
        shutil.copyfile(args.resume, resume_path)
        resume_path = os.path.basename(resume_path)

    jd_path: str | None = None
    jd_text: str | None = None
    if args.jd_file:
        check_upload(args.jd_file)
        jd_path = os.path.join(upload_dir, os.path.basename(args.jd_file))
        shutil.copyfile(args.jd_file, jd_path)
        jd_path = os.path.basename(jd_path)
    else:
        jd_text = args.jd or ""
        if args.jd and os.path.isfile(args.jd):
            with open(args.jd, encoding="utf-8") as handle:
                jd_text = handle.read()
        jd_text = redact_pii(jd_text)  # input guardrail: PII out before LLM calls

    request = AnalysisRequest(
        package_id=make_package_id(),
        resume_path=resume_path,
        resume_text=redact_pii(args.resume_text) if args.resume_text else None,
        jd_path=jd_path,
        jd_text=jd_text,
        seniority=args.seniority,
    )

    result = run_analysis(request)
    print(result.package.model_dump_json(indent=2))
    print("\nInterview prep plan:")
    print(result.prep_plan.model_dump_json(indent=2))
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
