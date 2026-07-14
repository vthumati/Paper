from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    DataRoomCtx,
    EntityCtx,
    QuestionCtx,
    dataroom_ctx,
    entity_ctx,
    get_current_user,
    question_ctx,
    require_write,
)
from ..models.dataroom import DataRoom, DataRoomAccessGrant, DataRoomItem, DataRoomQuestion
from ..models.document import Document
from ..models.identity import User
from ..schemas import (
    AnswerIn,
    DataRoomIn,
    DataRoomItemIn,
    DataRoomOut,
    EngagementOut,
    GrantIn,
    QuestionIn,
    QuestionOut,
)
from ..services import dataroom as svc
from ..services.document import document_view

router = APIRouter(tags=["data-room"])


@router.post("/entities/{entity_id}/data-rooms", response_model=DataRoomOut, status_code=201)
def create_room(
    body: DataRoomIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    room = DataRoom(entity_id=ctx.entity.id, name=body.name, scope=body.scope, created_by=user.id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return svc.data_room_view(db, room)


@router.get("/entities/{entity_id}/data-rooms", response_model=list[DataRoomOut])
def list_rooms(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    rooms = db.query(DataRoom).filter_by(entity_id=ctx.entity.id).all()
    return [svc.data_room_view(db, r) for r in rooms]


@router.get("/data-rooms/{dataroom_id}", response_model=DataRoomOut)
def get_room(ctx: DataRoomCtx = Depends(dataroom_ctx), db: Session = Depends(get_db)):
    return svc.data_room_view(db, ctx.room)


@router.post("/data-rooms/{dataroom_id}/items", response_model=DataRoomOut, status_code=201)
def add_item(
    body: DataRoomItemIn,
    ctx: DataRoomCtx = Depends(dataroom_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = db.get(Document, body.document_id)
    if doc is None or doc.entity_id != ctx.room.entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Document not in this entity")
    db.add(
        DataRoomItem(
            data_room_id=ctx.room.id,
            document_id=body.document_id,
            folder=body.folder,
            order_index=body.order_index,
        )
    )
    db.commit()
    db.refresh(ctx.room)
    return svc.data_room_view(db, ctx.room)


@router.post("/data-rooms/{dataroom_id}/grants", response_model=DataRoomOut, status_code=201)
def add_grant(
    body: GrantIn,
    ctx: DataRoomCtx = Depends(dataroom_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    db.add(
        DataRoomAccessGrant(
            data_room_id=ctx.room.id,
            email=body.email,
            permissions=body.permissions,
            expiry=body.expiry,
        )
    )
    db.commit()
    db.refresh(ctx.room)
    return svc.data_room_view(db, ctx.room)


@router.post("/data-rooms/{dataroom_id}/items/{item_id}/view")
def view_item(
    item_id: str,
    ctx: DataRoomCtx = Depends(dataroom_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(DataRoomItem, item_id)
    if item is None or item.data_room_id != ctx.room.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    svc.log_engagement(db, ctx.room.id, item.document_id, user.email, "view")
    doc = db.get(Document, item.document_id)
    view = document_view(db, doc)
    # text watermark: stamp the viewer + room on the returned copy (FR-I-1)
    stamp = f"CONFIDENTIAL — {ctx.room.name} — viewed by {user.email}\n\n"
    view["content"] = stamp + (view["content"] or "")
    return view


# --- diligence Q&A (FR-I-4) ---
@router.post("/data-rooms/{dataroom_id}/questions", response_model=QuestionOut, status_code=201)
def ask_question(
    body: QuestionIn,
    ctx: DataRoomCtx = Depends(dataroom_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = DataRoomQuestion(data_room_id=ctx.room.id, asker=user.email, question=body.question)
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.get("/data-rooms/{dataroom_id}/questions", response_model=list[QuestionOut])
def list_questions(ctx: DataRoomCtx = Depends(dataroom_ctx), db: Session = Depends(get_db)):
    return db.query(DataRoomQuestion).filter_by(data_room_id=ctx.room.id).all()


@router.post("/data-room-questions/{question_id}/answer", response_model=QuestionOut)
def answer_question(
    body: AnswerIn,
    ctx: QuestionCtx = Depends(question_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    ctx.question.answer = body.answer
    ctx.question.answered_by = user.email
    db.commit()
    db.refresh(ctx.question)
    return ctx.question


@router.get("/data-rooms/{dataroom_id}/engagement", response_model=list[EngagementOut])
def engagement(ctx: DataRoomCtx = Depends(dataroom_ctx), db: Session = Depends(get_db)):
    return svc.engagement_summary(db, ctx.room.id)
