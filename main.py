"""CLI entrypoint.

    python main.py --resume samples/sample_resume.txt --jd samples/sample_jd.txt
    python main.py --resume uploads/my_resume.pdf --jd "https://example.com/job"

Needs OPENAI_API_KEY in the environment (see .env.example).
"""

import argparse
import os
import shutil

from dotenv import load_dotenv

from careercrew.crew import CareerCrew
from careercrew.guardrails import check_upload, redact_pii


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="CareerCrew: multi-agent resume coach")
    parser.add_argument("--resume", required=True, help="Path to a resume file (PDF or TXT)")
    parser.add_argument("--jd", required=True, help="Path to a JD text file or an https URL")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set. Copy .env.example to .env first.")

    check_upload(args.resume)  # input guardrail: type + size

    upload_dir = os.environ.get("CAREERCREW_UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    resume_path = os.path.join(upload_dir, os.path.basename(args.resume))
    shutil.copyfile(args.resume, resume_path)

    jd_source = args.jd
    if os.path.isfile(args.jd):
        with open(args.jd, encoding="utf-8") as f:
            jd_source = f.read()
    jd_source = redact_pii(jd_source)  # input guardrail: PII out before LLM calls

    crew = CareerCrew().crew()
    result = crew.kickoff(inputs={"resume_path": resume_path, "jd_source": jd_source})
    print(result)


if __name__ == "__main__":
    main()
