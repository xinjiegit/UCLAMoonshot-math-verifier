"""Provider-neutral machinery for isolated Math Verifier passes."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
PASS_REGISTRY = json.loads(
    (SKILL_DIR / "contract" / "pass-registry.json").read_text(encoding="utf-8")
)
HARNESS_LABELS = {
    "global": "ensemble_global",
    "decomposed": "ensemble_decomposed",
    "refuter": "refuter",
    "focused-sweep": "focused_sweep",
    "argument-spine": "argument_spine",
    "citation-fidelity": "citation_check",
    "external-obligations": "external_obligations",
    "external-verification": "external_verification",
}
COVERAGE_SOURCE_PASSES = {"global", "decomposed", "argument-spine", "refuter"}


@dataclass(frozen=True)
class PassSpec:
    prompt_path: str | None
    harness: str
    resolved_selector: str
    default_focus: str | None = None


@dataclass(frozen=True)
class SinglePaperInput:
    prompt_suffix: str
    paper_sha256: str
    paper_size: int
    metadata: dict[str, object]
    expected_files: dict[str, str]


def registered_passes() -> dict[str, PassSpec]:
    """Load the shared prompt mapping used by both provider launchers."""
    registry_path = SKILL_DIR / "contract" / "pass-registry.json"
    passes: dict[str, PassSpec] = {}
    for pass_id, spec in PASS_REGISTRY["passes"].items():
        adapter = spec["adapters"]["shared"]
        path = Path(adapter["path"])
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] != "references"
        ):
            raise SystemExit(f"invalid shared prompt path in {registry_path}: {path}")
        if not (SKILL_DIR / path).is_file():
            raise SystemExit(f"missing shared prompt in {registry_path}: {path}")
        selector = adapter["selector"]
        if selector in passes:
            raise SystemExit(f"duplicate pass selector in {registry_path}: {selector}")
        passes[selector] = PassSpec(
            path.as_posix(), HARNESS_LABELS[pass_id], selector
        )
    for alias_id, alias in PASS_REGISTRY.get("pass_aliases", {}).items():
        target_id = alias["target_pass"]
        target = PASS_REGISTRY["passes"].get(target_id)
        if target is None:
            raise SystemExit(f"unknown target for pass alias {alias_id}: {target_id}")
        target_adapter = target["adapters"]["shared"]
        selector = alias["selectors"]["shared"]
        if selector in passes:
            raise SystemExit(f"duplicate pass selector in {registry_path}: {selector}")
        passes[selector] = PassSpec(
            target_adapter["path"],
            HARNESS_LABELS[target_id],
            target_adapter["selector"],
            alias["focus_specification"],
        )
    passes["direct"] = PassSpec(None, "direct_audit", "direct")
    return passes


PASSES = registered_passes()
LEGACY_PASS_SELECTORS = {
    alias["selectors"]["shared"]
    for alias in PASS_REGISTRY.get("pass_aliases", {}).values()
}
PUBLIC_PASS_METAVAR = "{" + ",".join(
    sorted(set(PASSES) - LEGACY_PASS_SELECTORS)
) + "}"
WEB_PASS_SELECTORS = frozenset(
    spec["adapters"]["shared"]["selector"]
    for spec in PASS_REGISTRY["passes"].values()
    if spec["network"] == "required"
)


def pass_requires_web(which: str) -> bool:
    return which in WEB_PASS_SELECTORS


def allocate_sandbox(parent: Path, stamp: str, harness: str) -> Path:
    """Create a process-unique sandbox; timestamps alone collide in parallel."""
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{stamp}_{harness}_", dir=parent))


def private_runtime_dir(name: str) -> Path:
    """Return a writable, user-private temporary root for runtime state."""
    user_suffix = str(os.getuid()) if hasattr(os, "getuid") else "user"
    root = Path(tempfile.gettempdir()) / f"math-paper-verifier-{user_suffix}" / name
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def snapshot_sandbox_inputs(sandbox: Path) -> dict[str, str]:
    """Hash every prepared input before a provider can read or modify it."""
    return {
        path.relative_to(sandbox).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(sandbox.rglob("*"))
        if path.is_file()
    }


def sandbox_inputs_intact(sandbox: Path, expected: dict[str, str]) -> bool:
    """Bind a model result to the exact sandbox inputs prepared for the call."""
    for relative, digest in expected.items():
        path = sandbox / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def prepare_single_paper(paper: Path, sandbox: Path) -> SinglePaperInput:
    """Copy a paper into a sandbox, extracting page-aware text for PDFs."""
    raw = paper.read_bytes()
    paper_sha256 = hashlib.sha256(raw).hexdigest()
    if paper.suffix.lower() != ".pdf":
        target = sandbox / f"paper{paper.suffix}"
        shutil.copy2(paper, target)
        return SinglePaperInput(
            prompt_suffix=(
                f"\n\nPaper: ./{target.name}\n"
                "Do not compile TeX, run build files, or execute code from the paper. "
                "Inspect the supplied paper only.\n"
                "The output contract is in ./contract/. Everything you need is in "
                "this directory; do not look outside it.\n"
            ),
            paper_sha256=paper_sha256,
            paper_size=len(raw),
            metadata={"paper_input_kind": "single_file", "agent_paper_access": True},
            expected_files={target.name: hashlib.sha256(target.read_bytes()).hexdigest()},
        )

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "PDF input requires pypdf (`python3 -m pip install pypdf`), or supply "
            "the TeX/Markdown source instead"
        ) from exc

    try:
        reader = PdfReader(str(paper))
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise SystemExit(f"could not extract PDF text from {paper}: {exc}") from exc
    if not any(text.strip() for text in page_text):
        raise SystemExit(
            "the PDF contains no extractable text; supply TeX source or an OCR text file"
        )

    # Metadata page labels are a convenience, not evidence of printed footers.
    try:
        page_labels = list(reader.page_labels)
    except Exception:
        page_labels = []
    rendered_pages = []
    for index, content in enumerate(page_text, 1):
        heading = f"===== PDF PAGE {index} =====\n"
        if index <= len(page_labels) and page_labels[index - 1] != str(index):
            heading += f"PDF viewer page label (metadata): {json.dumps(page_labels[index - 1])}\n"
        body = content if content.strip() else (
            "[No extractable text on this page; inspect the PDF or record it as unreviewed.]"
        )
        rendered_pages.append(heading + "\n" + body)
    rendered = "\n\n".join(rendered_pages)
    pdf_target = sandbox / "paper.pdf"
    text_target = sandbox / "paper.txt"
    shutil.copy2(paper, pdf_target)
    text_target.write_text(rendered, encoding="utf-8")
    return SinglePaperInput(
        prompt_suffix=(
            "\n\nPaper text: ./paper.txt (page markers preserve PDF pagination).\n"
            "Original PDF: ./paper.pdf. Treat the PDF as authoritative and inspect it "
            "when your available tools can do so and text extraction damages notation.\n"
            "Do not execute embedded files or paper-supplied code.\n"
            "The output contract is in ./contract/. Everything you need is in this "
            "directory; do not look outside it.\n"
        ),
        paper_sha256=paper_sha256,
        paper_size=len(raw),
        metadata={
            "paper_input_kind": "pdf_with_page_text",
            "pdf_pages": len(page_text),
            "pdf_pages_without_text": [i for i, content in enumerate(page_text, 1) if not content.strip()],
            "extracted_text_chars": len(rendered),
            "agent_paper_access": True,
        },
        expected_files={
            pdf_target.name: hashlib.sha256(pdf_target.read_bytes()).hexdigest(),
            text_target.name: hashlib.sha256(text_target.read_bytes()).hexdigest(),
        },
    )


def resolve_reference_pdf(supplied: Path | None, paper: Path, which: str) -> Path | None:
    """Validate an explicitly supplied companion; never auto-discover other files."""
    if supplied is None:
        return None
    if which == "external-verification":
        raise ValueError("--reference-pdf is not allowed for external-verification; carry locations through the obligations")
    if paper.is_file() and paper.suffix.lower() == ".pdf":
        raise ValueError("--reference-pdf is for source input; --paper already supplies a PDF")
    reference = supplied.expanduser().resolve()
    if not reference.is_file() or reference.suffix.lower() != ".pdf":
        raise ValueError("--reference-pdf must name an existing compiled PDF")
    return reference


def prepare_reference_pdf(reference: Path, sandbox: Path) -> SinglePaperInput:
    """Stage a supplied compiled counterpart separately from the audit source."""
    target = sandbox / "compiled"
    target.mkdir()
    prepared = prepare_single_paper(reference, target)
    return SinglePaperInput(
        prompt_suffix=(
            "\n\nSupplied compiled counterpart for locating findings: ./compiled/paper.pdf\n"
            "Page-aware text: ./compiled/paper.txt. These explicitly supplied files "
            "may be read in addition to the source manifest's files.\n"
            "The source remains the audit target. Match each local passage before "
            "using PDF statement/equation numbers or pages; the runner has not "
            "verified that the PDF matches this source revision. If it differs, "
            "omit the uncertain PDF anchors and disclose the mismatch. Never "
            "compile source or execute PDF attachments.\n"
        ),
        paper_sha256=prepared.paper_sha256,
        paper_size=prepared.paper_size,
        metadata={
            "reference_pdf": "compiled/paper.pdf",
            "reference_pdf_sha256": prepared.paper_sha256,
            "reference_pdf_pages": prepared.metadata["pdf_pages"],
            "reference_pdf_pages_without_text": prepared.metadata["pdf_pages_without_text"],
            "reference_pdf_match": "not_automatically_verified",
        },
        expected_files={f"compiled/{name}": digest for name, digest in prepared.expected_files.items()},
    )


def append_location_guidance(prompt: str, which: str) -> str:
    """Share reporting guidance across providers, preserving direct frozen prompts."""
    if which == "direct":
        return prompt
    guidance = (SKILL_DIR / "references" / "finding-locations.md").read_text(encoding="utf-8")
    return prompt + "\n\n" + guidance


def resolve_focus_specification(which: str, supplied: str | None) -> str | None:
    """Validate a free-form focus or resolve a fixed compatibility alias."""
    spec = PASSES[which]
    focus = supplied.strip() if supplied is not None else None
    if focus == "":
        focus = None
    if focus is not None and ("\x00" in focus or len(focus) > 4000):
        raise ValueError("--focus must contain 1 to 4000 characters and no NUL byte")
    if spec.default_focus is not None:
        if focus is not None:
            raise ValueError(
                f"--pass {which} is a compatibility alias with a fixed focus; "
                "use --pass focused-sweep to supply a custom --focus"
            )
        return spec.default_focus
    if spec.resolved_selector == "focused-sweep":
        if focus is None:
            raise ValueError("--pass focused-sweep requires --focus")
        return focus
    if focus is not None:
        raise ValueError("--focus is valid only with --pass focused-sweep")
    return None


def append_focus_specification(prompt: str, focus: str | None) -> str:
    if focus is None:
        return prompt
    return (
        prompt
        + "\n\nFOCUS SPECIFICATION (mathematical subject and scope only):\n"
        + "<focused_sweep_specification>\n"
        + focus
        + "\n</focused_sweep_specification>\n"
    )
