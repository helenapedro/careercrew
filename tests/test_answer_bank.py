"""Tests for the verified answer bank lookup."""

from __future__ import annotations

from careercrew.document_tools import query_answer_bank


def test_answer_bank_finds_work_authorization():
    result = query_answer_bank("Are you legally authorized to work in the US?")
    assert result["found"] is True
    assert result["source"] == "answer_bank"
    assert "authorized" in result["answer"].lower()


def test_answer_bank_finds_notice_period():
    result = query_answer_bank("What is your notice period?")
    assert result["found"] is True
    assert result["key"] == "notice_period"


def test_answer_bank_finds_relocation():
    result = query_answer_bank("Are you willing to relocate?")
    assert result["found"] is True
    assert result["key"] == "willing_to_relocate"


def test_answer_bank_unknown_question_is_not_found():
    result = query_answer_bank("What is your favorite programming font?")
    assert result["found"] is False
    assert result["status"] == "not_found"


def test_answer_bank_empty_question_is_error():
    result = query_answer_bank("   ")
    assert result["found"] is False
    assert result["status"] == "error"


def test_answer_bank_never_returns_unverified(tmp_path, monkeypatch):
    import yaml

    from careercrew import config, document_tools

    bank = {
        "answers": [
            {
                "key": "secret",
                "question": "secret question",
                "answer": "unverified answer",
                "labels": ["secret"],
                "verified": False,
            }
        ]
    }
    path = tmp_path / "answer_bank.yaml"
    path.write_text(yaml.safe_dump(bank), encoding="utf-8")
    monkeypatch.setattr(document_tools, "ANSWER_BANK_PATH", path)
    document_tools.reset_answer_bank_cache()
    try:
        result = query_answer_bank("secret question")
        assert result["found"] is False
    finally:
        document_tools.reset_answer_bank_cache()
        config.reset_settings_cache()
