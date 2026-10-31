from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_integrations import TaskBlock
from app.models_tasks import Task
from app.task_block_schemas import TaskBlockCreate, TaskBlockRead, TaskBlockUpdate

router = APIRouter(prefix="/task-blocks", tags=["task scheduling"])


def _owned_block(db: Session, user_id: UUID, block_id: UUID) -> TaskBlock:
    block = db.scalar(
        select(TaskBlock).where(TaskBlock.id == block_id, TaskBlock.user_id == user_id)
    )
    if block is None:
        raise HTTPException(status_code=404, detail="Scheduled task block not found")
    return block


@router.get("", response_model=list[TaskBlockRead])
def list_task_blocks(
    start_at: datetime = Query(...),
    end_at: datetime = Query(...),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TaskBlock]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    return list(
        db.scalars(
            select(TaskBlock)
            .where(
                TaskBlock.user_id == user.id,
                TaskBlock.start_at < end_at,
                TaskBlock.end_at > start_at,
            )
            .order_by(TaskBlock.start_at.asc())
        ).all()
    )


@router.post("", response_model=TaskBlockRead, status_code=status.HTTP_201_CREATED)
def create_task_block(
    payload: TaskBlockCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskBlock:
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("done", "cancelled"):
        raise HTTPException(status_code=409, detail="Completed or cancelled tasks cannot be scheduled")
    block = TaskBlock(
        user_id=user.id,
        task_id=task.id,
        title=task.title,
        start_at=payload.start_at,
        end_at=payload.end_at,
        idempotency_key=uuid4(),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.patch("/{block_id}", response_model=TaskBlockRead)
def update_task_block(
    block_id: UUID,
    payload: TaskBlockUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskBlock:
    block = _owned_block(db, user.id, block_id)
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="Timestamps cannot be null")
    start_at = changes.get("start_at", block.start_at)
    end_at = changes.get("end_at", block.end_at)
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    for field, value in changes.items():
        setattr(block, field, value)
    db.commit()
    db.refresh(block)
    return block


@router.delete("/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_block(
    block_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    block = _owned_block(db, user.id, block_id)
    db.delete(block)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
