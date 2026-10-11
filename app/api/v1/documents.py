import hashlib
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, record_audit
from app.core.config import get_settings
from app.core.deps import get_current_actor, require_permission
from app.db.queries import get_document_sql, list_documents_sql
from app.db.session import get_session, write_transaction
from app.schemas.domain import DocType, SourceDocument, UserResponse
from app.services.evidence_import import EvidenceFormatError, import_evidence
from app.services.rcm_import import RcmFormatError, import_controls, parse_rcm

router = APIRouter(prefix="/documents", tags=["documents"])

# Bytes read from the upload per step while hashing and writing it to storage.
_READ_CHUNK_BYTES = 1024 * 1024

CLAUSE_REGEX = re.compile(
    r"^(?:Section\s+\d+|[0-9]+[A-Z]?(?:\.[0-9]+)*|Paragraph\s+\d+|para\s+\d+)",
    re.IGNORECASE,
)

_INSERT_CHUNK = text("""
    INSERT INTO chunks (id, document_id, clause_ref, page, text, created_at)
    VALUES (:id, :doc_id, :clause_ref, 1, :text, now())
""")


@router.get("", response_model=list[SourceDocument])
def list_documents(
    _user: UserResponse = Depends(require_permission("documents:read")),
    session: Session = Depends(get_session),
) -> list[SourceDocument]:
    """Lists all ingested regulatory and institutional source documents."""
    return list_documents_sql(session)


@router.get("/{id}", response_model=SourceDocument)
def get_document(
    id: str,
    _user: UserResponse = Depends(require_permission("documents:read")),
    session: Session = Depends(get_session),
) -> SourceDocument:
    doc = get_document_sql(session, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _clause_chunks(content: bytes) -> list[tuple[str, str]]:
    """Splits a UTF-8 text file into (clause_ref, text) chunks. Other files give no chunks."""
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        return []  # Binary (e.g. PDF): parsed later by the pipeline, not here.
    if "\x00" in text_content:
        return []

    chunks: list[tuple[str, str]] = []
    current_ref = "1"
    current_lines: list[str] = []
    for line in text_content.splitlines():
        match = CLAUSE_REGEX.match(line.strip())
        if match:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                chunks.append((current_ref, chunk_text))
            current_lines = []
            current_ref = match.group(0)
        current_lines.append(line)
    chunk_text = "\n".join(current_lines).strip()
    if chunk_text:
        chunks.append((current_ref, chunk_text))
    return chunks


def _save_upload(file: UploadFile, target: Path, max_bytes: int) -> tuple[bytes, str]:
    """Streams the upload to ``target`` in chunks. Returns (content, sha256); 413 when too big."""
    digest = hashlib.sha256()
    parts: list[bytes] = []
    size = 0
    try:
        with open(target, "wb") as out:
            while chunk := file.file.read(_READ_CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                    )
                digest.update(chunk)
                parts.append(chunk)
                out.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return b"".join(parts), digest.hexdigest()


def _import_bank_data(
    session: Session, doc_type: str, content: bytes, file_name: str, title: str, doc_id: str
) -> dict[str, str]:
    """A control matrix becomes controls and an evidence table becomes evidence, in the same
    transaction as the document, so a file that cannot be read is rejected as a whole."""
    is_csv = file_name.lower().endswith(".csv")
    try:
        if doc_type == "rcm":
            if not is_csv:
                raise RcmFormatError("Upload the control matrix as a CSV file.")
            count = import_controls(session, parse_rcm(content))
            return {"controls_imported": str(count)}
        if doc_type == "evidence" and is_csv:
            code = import_evidence(
                session, content=content, file_name=file_name, title=title, fallback_code=doc_id
            )
            return {"evidence": code}
    except (RcmFormatError, EvidenceFormatError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None
    return {}


@router.post("", response_model=SourceDocument)
def upload_document(
    file: UploadFile = File(...),
    doc_type: DocType = Form(...),
    title: str = Form(..., min_length=1, max_length=255),
    regulator: str | None = Form(None),
    version_label: str = Form("Unversioned"),
    supersedes_id: str | None = Form(None),
    _user: UserResponse = Depends(require_permission("documents:upload")),
    actor: ActorInfo = Depends(get_current_actor),
    session: Session = Depends(get_session),
) -> SourceDocument:
    """Multipart upload with size limit, SHA-256 dedupe, storage, clause chunking and audit."""
    settings = get_settings()
    storage_dir = settings.storage_dir.resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    version_label = version_label.strip() or "Unversioned"
    supersedes_id = (supersedes_id or "").strip() or None
    regulator = (regulator or "").strip() or None
    if supersedes_id and not get_document_sql(session, supersedes_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"supersedes_id '{supersedes_id}' does not match a document.",
        )

    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    # The client's filename is untrusted: keep only a safe base name so it cannot leave storage.
    file_name = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(file.filename or "").name).strip(" .")
    file_name = file_name[:120] or "uploaded_file"
    target = (storage_dir / f"{doc_id}_{file_name}").resolve()
    if target.parent != storage_dir:
        raise HTTPException(status_code=400, detail="Invalid file name.")
    # Written under a temporary name and renamed only once the database rows are in place.
    partial = target.with_name(target.name + ".part")

    content, sha256_hash = _save_upload(file, partial, settings.max_upload_mb * 1024 * 1024)

    existing = (
        session.execute(
            text("SELECT id FROM documents WHERE sha256 = :sha256 LIMIT 1"),
            {"sha256": sha256_hash},
        )
        .mappings()
        .first()
    )
    if existing:
        partial.unlink(missing_ok=True)
        doc = get_document_sql(session, existing["id"])
        if doc:
            return doc

    try:
        with write_transaction(session):
            session.execute(
                text("""
                    INSERT INTO documents (
                        id, doc_type, title, reference, regulator, version_label, supersedes_id,
                        is_synthetic, file_path, sha256, status, withdrawn_note, created_at
                    ) VALUES (
                        :id, :doc_type, :title, :reference, :regulator, :version_label,
                        :supersedes_id, :is_synthetic, :file_path, :sha256, 'ready', NULL, now()
                    )
                """),
                {
                    "id": doc_id,
                    "doc_type": doc_type,
                    "title": title,
                    "reference": file_name,
                    "regulator": regulator,
                    "version_label": version_label,
                    "supersedes_id": supersedes_id,
                    "is_synthetic": doc_type != "regulation",
                    "file_path": str(target),
                    "sha256": sha256_hash,
                },
            )
            for index, (clause_ref, chunk_text) in enumerate(_clause_chunks(content), start=1):
                session.execute(
                    _INSERT_CHUNK,
                    {
                        "id": f"chk-{doc_id}-{index}",
                        "doc_id": doc_id,
                        "clause_ref": clause_ref,
                        "text": chunk_text,
                    },
                )
            imported = _import_bank_data(session, doc_type, content, file_name, title, doc_id)
            record_audit(
                session,
                actor=actor,
                action="Uploaded document",
                entity_type="document",
                entity_code=title,
                before=None,
                after={"status": "ready", "file": file_name, **imported},
            )
            os.replace(partial, target)
    except BaseException:
        # Nothing was committed, so no file may stay behind.
        partial.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise

    saved_doc = get_document_sql(session, doc_id)
    if not saved_doc:
        raise HTTPException(status_code=500, detail="Failed to retrieve uploaded document")
    return saved_doc
