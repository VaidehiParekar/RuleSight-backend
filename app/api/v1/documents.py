import hashlib
import os
import re
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.actor import ActorInfo, get_actor, record_audit
from app.db.queries import get_document_sql, list_documents_sql
from app.db.session import get_session
from app.schemas.domain import SourceDocument

router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

CLAUSE_REGEX = re.compile(
    r"^(?:Section\s+\d+|[0-9]+[A-Z]?(?:\.[0-9]+)*|Paragraph\s+\d+|para\s+\d+)",
    re.IGNORECASE,
)


@router.get("", response_model=list[SourceDocument])
def list_documents(session: Session = Depends(get_session)) -> list[SourceDocument]:
    """Lists all ingested regulatory and institutional source documents."""
    return list_documents_sql(session)


@router.get("/{id}", response_model=SourceDocument)
def get_document(id: str, session: Session = Depends(get_session)) -> SourceDocument:
    doc = get_document_sql(session, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("", response_model=SourceDocument)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    title: str = Form(...),
    regulator: str | None = Form(None),
    version_label: str = Form("Unversioned"),
    supersedes_id: str | None = Form(None),
    actor: ActorInfo = Depends(get_actor),
    session: Session = Depends(get_session),
) -> SourceDocument:
    """Handles multipart upload, SHA256 deduplication, storage, clause chunking, and audit logging."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds maximum allowable limit of 10 MB.")

    sha256_hash = hashlib.sha256(content).hexdigest()

    # Check for existing document with same hash
    existing = session.execute(
        text("SELECT id FROM documents WHERE sha256 = :sha256 LIMIT 1"),
        {"sha256": sha256_hash},
    ).mappings().first()
    if existing:
        doc = get_document_sql(session, existing["id"])
        if doc:
            return doc

    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    file_name = file.filename or "uploaded_file"
    file_path = str(STORAGE_DIR / f"{doc_id}_{file_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    is_synthetic = doc_type != "regulation"

    with session.begin():
        # Insert document
        insert_doc_query = text("""
            INSERT INTO documents (
                id, doc_type, title, reference, regulator, version_label, supersedes_id,
                is_synthetic, file_path, sha256, status, withdrawn_note, created_at
            ) VALUES (
                :id, :doc_type, :title, :reference, :regulator, :version_label, :supersedes_id,
                :is_synthetic, :file_path, :sha256, 'ready', NULL, now()
            )
        """)
        session.execute(
            insert_doc_query,
            {
                "id": doc_id,
                "doc_type": doc_type,
                "title": title,
                "reference": file_name,
                "regulator": regulator,
                "version_label": version_label,
                "supersedes_id": supersedes_id,
                "is_synthetic": is_synthetic,
                "file_path": file_path,
                "sha256": sha256_hash,
            },
        )

        # Parse text chunks if readable plain text
        try:
            text_content = content.decode("utf-8", errors="ignore")
            lines = text_content.splitlines()
            current_ref = "1"
            current_chunk = []
            chunk_index = 1

            for line in lines:
                stripped = line.strip()
                match = CLAUSE_REGEX.match(stripped)
                if match:
                    if current_chunk:
                        chunk_text = "\n".join(current_chunk).strip()
                        if chunk_text:
                            session.execute(
                                text("""
                                    INSERT INTO chunks (id, document_id, clause_ref, page, text, created_at)
                                    VALUES (:id, :doc_id, :clause_ref, 1, :text, now())
                                """),
                                {
                                    "id": f"chk-{doc_id}-{chunk_index}",
                                    "doc_id": doc_id,
                                    "clause_ref": current_ref,
                                    "text": chunk_text,
                                },
                            )
                            chunk_index += 1
                        current_chunk = []
                    current_ref = match.group(0)
                current_chunk.append(line)

            if current_chunk:
                chunk_text = "\n".join(current_chunk).strip()
                if chunk_text:
                    session.execute(
                        text("""
                            INSERT INTO chunks (id, document_id, clause_ref, page, text, created_at)
                            VALUES (:id, :doc_id, :clause_ref, 1, :text, now())
                        """),
                        {
                            "id": f"chk-{doc_id}-{chunk_index}",
                            "doc_id": doc_id,
                            "clause_ref": current_ref,
                            "text": chunk_text,
                        },
                    )
        except Exception:
            pass  # Non-fatal chunk parsing for binary files

        record_audit(
            session,
            actor=actor,
            action="Uploaded document",
            entity_type="document",
            entity_code=title,
            before=None,
            after={"status": "ready", "file": file_name},
        )

    saved_doc = get_document_sql(session, doc_id)
    if not saved_doc:
        raise HTTPException(status_code=500, detail="Failed to retrieve uploaded document")
    return saved_doc
