from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.services.pdf_resume_compiler import (
    PdfCompilerUnavailable,
    PdfOutputTooLarge,
    compile_latex_to_pdf,
)

MINIMAL_LATEX = r"""
\documentclass{article}
\begin{document}
ResumePilot
\end{document}
"""


def test_compile_latex_to_pdf_uses_tectonic_untrusted(monkeypatch):
    run_call: dict[str, object] = {}

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/tectonic" if name == "tectonic" else None

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        run_call["command"] = command
        run_call["kwargs"] = kwargs
        Path(kwargs["cwd"], "resume.pdf").write_bytes(b"%PDF-1.7\n")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("app.services.pdf_resume_compiler.shutil.which", fake_which)
    monkeypatch.setattr("app.services.pdf_resume_compiler.subprocess.run", fake_run)

    pdf = compile_latex_to_pdf(
        MINIMAL_LATEX,
        timeout_seconds=7,
        max_output_bytes=1024,
    )

    command = run_call["command"]
    kwargs = run_call["kwargs"]
    assert pdf.startswith(b"%PDF")
    assert isinstance(command, list)
    assert command[:2] == ["/usr/local/bin/tectonic", "--untrusted"]
    assert "--outdir" in command
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["timeout"] == 7
    assert "shell" not in kwargs


def test_compile_latex_to_pdf_falls_back_to_pdflatex_no_shell_escape(monkeypatch):
    run_call: dict[str, object] = {}

    def fake_which(name: str) -> str | None:
        if name == "pdflatex":
            return "/usr/local/bin/pdflatex"
        return None

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        run_call["command"] = command
        run_call["kwargs"] = kwargs
        Path(kwargs["cwd"], "resume.pdf").write_bytes(b"%PDF-1.7\n")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("app.services.pdf_resume_compiler.shutil.which", fake_which)
    monkeypatch.setattr("app.services.pdf_resume_compiler.subprocess.run", fake_run)

    pdf = compile_latex_to_pdf(
        MINIMAL_LATEX,
        timeout_seconds=7,
        max_output_bytes=1024,
    )

    command = run_call["command"]
    assert pdf.startswith(b"%PDF")
    assert command[0] == "/usr/local/bin/pdflatex"
    assert "-halt-on-error" in command
    assert "-no-shell-escape" in command
    assert "shell" not in run_call["kwargs"]


def test_compile_latex_to_pdf_requires_supported_compiler(monkeypatch):
    monkeypatch.setattr("app.services.pdf_resume_compiler.shutil.which", lambda _name: None)

    with pytest.raises(PdfCompilerUnavailable):
        compile_latex_to_pdf(
            MINIMAL_LATEX,
            timeout_seconds=7,
            max_output_bytes=1024,
        )


def test_compile_latex_to_pdf_enforces_output_size(monkeypatch):
    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/tectonic" if name == "tectonic" else None

    def fake_run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        Path(kwargs["cwd"], "resume.pdf").write_bytes(b"%PDF-1.7 oversized\n")
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr("app.services.pdf_resume_compiler.shutil.which", fake_which)
    monkeypatch.setattr("app.services.pdf_resume_compiler.subprocess.run", fake_run)

    with pytest.raises(PdfOutputTooLarge):
        compile_latex_to_pdf(
            MINIMAL_LATEX,
            timeout_seconds=7,
            max_output_bytes=5,
        )
