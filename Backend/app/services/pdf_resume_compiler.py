from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from functools import wraps
from pathlib import Path

INPUT_FILENAME = "resume.tex"
OUTPUT_FILENAME = "resume.pdf"
MAX_LOG_EXCERPT_CHARS = 4000
SOURCE_DATE_EPOCH = "1704067200"
PDF_COMPILE_ACQUIRE_TIMEOUT_SECONDS = 1.0
_PDF_COMPILE_SLOT = threading.BoundedSemaphore(value=1)


class PdfCompilationError(RuntimeError):
    """Base error for controlled LaTeX-to-PDF compilation failures."""

    def __init__(self, message: str, *, log_excerpt: str | None = None) -> None:
        super().__init__(message)
        self.log_excerpt = log_excerpt


class PdfCompilerUnavailable(PdfCompilationError):
    """Raised when no supported local LaTeX compiler is available."""


class PdfCompilationFailed(PdfCompilationError):
    """Raised when the compiler rejects the generated LaTeX source."""


class PdfCompilationTimedOut(PdfCompilationError):
    """Raised when PDF compilation exceeds the configured timeout."""


class PdfOutputTooLarge(PdfCompilationError):
    """Raised when the generated PDF exceeds the configured size limit."""


class PdfCompilerBusy(PdfCompilationError):
    """Raised when the bounded local compiler slot is already occupied."""


@dataclass(frozen=True)
class CompilerSpec:
    name: str
    executable: str


def _bounded_pdf_compilation(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        acquired = _PDF_COMPILE_SLOT.acquire(timeout=PDF_COMPILE_ACQUIRE_TIMEOUT_SECONDS)
        if not acquired:
            raise PdfCompilerBusy("PDF compiler is busy. Retry the export shortly.")
        try:
            return function(*args, **kwargs)
        finally:
            _PDF_COMPILE_SLOT.release()

    return guarded


@_bounded_pdf_compilation
def compile_latex_to_pdf(
    latex_source: str,
    *,
    timeout_seconds: int,
    max_output_bytes: int,
) -> bytes:
    """Compile generated LaTeX into a PDF using a local guarded compiler invocation."""

    if not latex_source.strip():
        raise PdfCompilationFailed("Generated LaTeX source is empty.")

    compiler = _resolve_compiler()
    with tempfile.TemporaryDirectory(prefix="resumepilot-pdf-") as workspace:
        workspace_path = Path(workspace)
        tex_path = workspace_path / INPUT_FILENAME
        pdf_path = workspace_path / OUTPUT_FILENAME
        tex_path.write_text(latex_source, encoding="utf-8")

        command = _compiler_command(compiler, tex_path, workspace_path)
        try:
            completed = subprocess.run(
                command,
                cwd=workspace_path,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=_compiler_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfCompilationTimedOut(
                f"PDF compilation timed out after {timeout_seconds} seconds."
            ) from exc

        if completed.returncode != 0:
            raise PdfCompilationFailed(
                "Generated LaTeX could not be compiled into PDF.",
                log_excerpt=_log_excerpt(completed, workspace_path),
            )
        if not pdf_path.exists():
            raise PdfCompilationFailed(
                "PDF compiler completed without producing an output file.",
                log_excerpt=_log_excerpt(completed, workspace_path),
            )

        output_size = pdf_path.stat().st_size
        if output_size > max_output_bytes:
            raise PdfOutputTooLarge(
                f"Generated PDF exceeded {max_output_bytes} bytes.",
                log_excerpt=f"Generated PDF size: {output_size} bytes.",
            )

        pdf_bytes = pdf_path.read_bytes()
        if len(pdf_bytes) > max_output_bytes:
            raise PdfOutputTooLarge(f"Generated PDF exceeded {max_output_bytes} bytes.")
        return pdf_bytes


def _resolve_compiler() -> CompilerSpec:
    tectonic = shutil.which("tectonic")
    if tectonic:
        return CompilerSpec(name="tectonic", executable=tectonic)

    pdflatex = shutil.which("pdflatex")
    if pdflatex:
        return CompilerSpec(name="pdflatex", executable=pdflatex)

    raise PdfCompilerUnavailable("Install tectonic or pdflatex to enable PDF export.")


def _compiler_command(compiler: CompilerSpec, tex_path: Path, outdir: Path) -> list[str]:
    if compiler.name == "tectonic":
        return [
            compiler.executable,
            "--untrusted",
            "--keep-logs",
            "--outdir",
            str(outdir),
            str(tex_path),
        ]

    return [
        compiler.executable,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-no-shell-escape",
        f"-output-directory={outdir}",
        str(tex_path),
    ]


def _compiler_env() -> dict[str, str]:
    allowed_keys = {
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "SSL_CERT_FILE",
        "TECTONIC_CACHE_DIR",
        "TMPDIR",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed_keys and value}
    env["SOURCE_DATE_EPOCH"] = SOURCE_DATE_EPOCH
    return env


def _log_excerpt(completed: subprocess.CompletedProcess[str], workspace: Path) -> str:
    fragments = [completed.stdout, completed.stderr]
    log_path = workspace / "resume.log"
    if log_path.exists():
        fragments.append(log_path.read_text(encoding="utf-8", errors="replace"))
    combined = "\n".join(fragment for fragment in fragments if fragment)
    return combined[-MAX_LOG_EXCERPT_CHARS:]
