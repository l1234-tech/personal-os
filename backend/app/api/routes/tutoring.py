from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_tutoring import (
    Homework,
    Lesson,
    LessonStatusHistory,
    LessonTopic,
    Payment,
    PaymentAllocation,
    Student,
    StudentProgress,
)
from app.tutoring_schemas import (
    AllocationCreate,
    HomeworkCreate,
    HomeworkRead,
    HomeworkUpdate,
    LessonCreate,
    LessonRead,
    LessonTopicCreate,
    LessonUpdate,
    PaymentCreate,
    PaymentRead,
    ProgressCreate,
    ProgressRead,
    StudentCreate,
    StudentRead,
    StudentUpdate,
    TutoringSummary,
)

router = APIRouter(tags=["tutoring"])


def owned_student(db: Session, user_id: UUID, student_id: UUID) -> Student:
    student = db.scalar(
        select(Student).where(Student.id == student_id, Student.user_id == user_id)
    )
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def owned_lesson(db: Session, user_id: UUID, lesson_id: UUID) -> Lesson:
    lesson = db.scalar(
        select(Lesson).where(Lesson.id == lesson_id, Lesson.user_id == user_id)
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/students", response_model=list[StudentRead])
def list_students(
    include_archived: bool = False,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Student]:
    query = select(Student).where(Student.user_id == user.id)
    if not include_archived:
        query = query.where(Student.status != "archived")
    return list(db.scalars(query.order_by(Student.name.asc())).all())


@router.post("/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Student:
    data = payload.model_dump()
    data["name"] = data["name"].strip()
    data["subject"] = data["subject"].strip()
    if not data["name"] or not data["subject"]:
        raise HTTPException(status_code=422, detail="Name and subject cannot be blank")
    student = Student(user_id=user.id, **data)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}", response_model=StudentRead)
def update_student(
    student_id: UUID,
    payload: StudentUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Student:
    student = owned_student(db, user.id, student_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
    if "subject" in changes and changes["subject"] is not None:
        changes["subject"] = changes["subject"].strip()
        if not changes["subject"]:
            raise HTTPException(status_code=422, detail="Subject cannot be blank")
    if "currency_code" in changes and changes["currency_code"] is not None:
        currency = changes["currency_code"].upper()
        if currency != student.currency_code and db.scalar(
            select(Lesson.id).where(Lesson.student_id == student.id).limit(1)
        ):
            raise HTTPException(status_code=409, detail="Currency cannot change after lessons exist")
        changes["currency_code"] = currency
    for key, value in changes.items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return student


@router.get("/students/{student_id}/lessons", response_model=list[LessonRead])
def list_lessons(
    student_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Lesson]:
    owned_student(db, user.id, student_id)
    return list(
        db.scalars(
            select(Lesson)
            .where(Lesson.user_id == user.id, Lesson.student_id == student_id)
            .order_by(Lesson.scheduled_start.desc())
            .limit(limit)
        ).all()
    )


@router.post(
    "/students/{student_id}/lessons",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_lesson(
    student_id: UUID,
    payload: LessonCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Lesson:
    student = owned_student(db, user.id, student_id)
    if student.status != "active":
        raise HTTPException(status_code=409, detail="Student is not active")
    currency = (payload.currency_code or student.currency_code).upper()
    if currency != student.currency_code:
        raise HTTPException(status_code=422, detail="Lesson currency must match student currency")
    lesson = Lesson(
        user_id=user.id,
        student_id=student.id,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        price_amount=payload.price_amount if payload.price_amount is not None else student.rate_amount,
        currency_code=currency,
        status="scheduled",
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=LessonRead)
def update_lesson(
    lesson_id: UUID,
    payload: LessonUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Lesson:
    lesson = owned_lesson(db, user.id, lesson_id)
    changes = payload.model_dump(exclude_unset=True)
    start = changes.get("scheduled_start", lesson.scheduled_start)
    end = changes.get("scheduled_end", lesson.scheduled_end)
    if end <= start:
        raise HTTPException(status_code=422, detail="scheduled_end must be later than scheduled_start")
    actual_start = changes.get("actual_start", lesson.actual_start)
    actual_end = changes.get("actual_end", lesson.actual_end)
    if actual_start is not None and actual_end is not None and actual_end <= actual_start:
        raise HTTPException(status_code=422, detail="actual_end must be later than actual_start")
    if "currency_code" in changes and changes["currency_code"] is not None:
        student = owned_student(db, user.id, lesson.student_id)
        if changes["currency_code"].upper() != student.currency_code:
            raise HTTPException(status_code=422, detail="Lesson currency must match student currency")
        changes["currency_code"] = student.currency_code
    old_status = lesson.status
    if "cancellation_reason" in changes and changes["cancellation_reason"] is not None:
        changes["cancellation_reason"] = changes["cancellation_reason"].strip() or None
    for key, value in changes.items():
        setattr(lesson, key, value)
    if lesson.status != old_status:
        db.add(
            LessonStatusHistory(
                user_id=user.id,
                lesson_id=lesson.id,
                old_status=old_status,
                new_status=lesson.status,
                reason=lesson.cancellation_reason,
            )
        )
    db.commit()
    db.refresh(lesson)
    return lesson


@router.post("/lessons/{lesson_id}/topics", status_code=status.HTTP_201_CREATED)
def add_lesson_topic(
    lesson_id: UUID,
    payload: LessonTopicCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    lesson = owned_lesson(db, user.id, lesson_id)
    topic_name = payload.topic.strip()
    if not topic_name:
        raise HTTPException(status_code=422, detail="Topic cannot be blank")
    topic = LessonTopic(lesson_id=lesson.id, topic=topic_name, notes=payload.notes)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": str(topic.id), "topic": topic.topic}


@router.get("/students/{student_id}/homework", response_model=list[HomeworkRead])
def list_homework(
    student_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Homework]:
    owned_student(db, user.id, student_id)
    return list(
        db.scalars(
            select(Homework)
            .where(Homework.user_id == user.id, Homework.student_id == student_id)
            .order_by(Homework.due_at.asc().nulls_last())
        ).all()
    )


@router.post(
    "/students/{student_id}/homework",
    response_model=HomeworkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_homework(
    student_id: UUID,
    payload: HomeworkCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Homework:
    owned_student(db, user.id, student_id)
    if payload.lesson_id is not None:
        lesson = owned_lesson(db, user.id, payload.lesson_id)
        if lesson.student_id != student_id:
            raise HTTPException(status_code=422, detail="Lesson belongs to another student")
    homework = Homework(user_id=user.id, student_id=student_id, **payload.model_dump())
    homework.title = homework.title.strip()
    if not homework.title:
        raise HTTPException(status_code=422, detail="Homework title cannot be blank")
    db.add(homework)
    db.commit()
    db.refresh(homework)
    return homework


@router.patch("/homework/{homework_id}", response_model=HomeworkRead)
def update_homework(
    homework_id: UUID,
    payload: HomeworkUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Homework:
    homework = db.scalar(
        select(Homework).where(Homework.id == homework_id, Homework.user_id == user.id)
    )
    if homework is None:
        raise HTTPException(status_code=404, detail="Homework not found")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Homework title cannot be blank")
    for key, value in changes.items():
        setattr(homework, key, value)
    db.commit()
    db.refresh(homework)
    return homework


@router.get("/students/{student_id}/progress", response_model=list[ProgressRead])
def list_progress(
    student_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[StudentProgress]:
    owned_student(db, user.id, student_id)
    return list(
        db.scalars(
            select(StudentProgress)
            .where(StudentProgress.user_id == user.id, StudentProgress.student_id == student_id)
            .order_by(StudentProgress.topic.asc())
        ).all()
    )


@router.put("/students/{student_id}/progress", response_model=ProgressRead)
def upsert_progress(
    student_id: UUID,
    payload: ProgressCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> StudentProgress:
    owned_student(db, user.id, student_id)
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Topic cannot be blank")
    row = db.scalar(
        select(StudentProgress).where(
            StudentProgress.user_id == user.id,
            StudentProgress.student_id == student_id,
            StudentProgress.topic == topic,
        )
    )
    if row is None:
        row = StudentProgress(user_id=user.id, student_id=student_id, topic=topic)
        db.add(row)
    row.mastery_status = payload.mastery_status
    row.notes = payload.notes
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


@router.get("/payments", response_model=list[PaymentRead])
def list_payments(
    student_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Payment]:
    query = select(Payment).where(Payment.user_id == user.id)
    if student_id is not None:
        owned_student(db, user.id, student_id)
        query = query.where(Payment.student_id == student_id)
    return list(db.scalars(query.order_by(Payment.paid_at.desc()).limit(limit)).all())


@router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Payment:
    student = owned_student(db, user.id, payload.student_id)
    if payload.currency_code != student.currency_code:
        raise HTTPException(status_code=422, detail="Payment currency must match student currency")
    payment = Payment(user_id=user.id, **payload.model_dump())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.post("/payments/{payment_id}/allocations", status_code=status.HTTP_201_CREATED)
def allocate_payment(
    payment_id: UUID,
    payload: AllocationCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> dict[str, str]:
    payment = db.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.user_id == user.id)
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    lesson = owned_lesson(db, user.id, payload.lesson_id)
    if payment.student_id != lesson.student_id or payment.currency_code != lesson.currency_code:
        raise HTTPException(status_code=422, detail="Payment and lesson must match student and currency")
    payment_used = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.payment_id == payment.id
        )
    )
    lesson_paid = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
            PaymentAllocation.lesson_id == lesson.id
        )
    )
    if Decimal(payment_used or 0) + payload.amount > payment.amount:
        raise HTTPException(status_code=409, detail="Allocation exceeds payment balance")
    if Decimal(lesson_paid or 0) + payload.amount > lesson.price_amount:
        raise HTTPException(status_code=409, detail="Allocation exceeds lesson price")
    allocation = PaymentAllocation(
        user_id=user.id,
        payment_id=payment.id,
        lesson_id=lesson.id,
        amount=payload.amount,
    )
    db.add(allocation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Allocation conflicts with existing record") from exc
    return {"status": "allocated"}


@router.get("/students/{student_id}/summary", response_model=TutoringSummary)
def tutoring_summary(
    student_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TutoringSummary:
    student = owned_student(db, user.id, student_id)
    accrued = db.scalar(
        select(func.coalesce(func.sum(Lesson.price_amount), 0)).where(
            Lesson.user_id == user.id,
            Lesson.student_id == student_id,
            Lesson.status == "completed",
        )
    )
    received = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.user_id == user.id, Payment.student_id == student_id
        )
    )
    allocated = db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .join(Lesson, Lesson.id == PaymentAllocation.lesson_id)
        .where(
            PaymentAllocation.user_id == user.id,
            Lesson.user_id == user.id,
            Lesson.student_id == student_id,
            Lesson.status == "completed",
        )
    )
    count = db.scalar(
        select(func.count(Lesson.id)).where(
            Lesson.user_id == user.id,
            Lesson.student_id == student_id,
            Lesson.status == "completed",
        )
    )
    accrued_value = Decimal(accrued or 0)
    received_value = Decimal(received or 0)
    allocated_value = Decimal(allocated or 0)
    return TutoringSummary(
        student_id=student.id,
        currency_code=student.currency_code,
        accrued=accrued_value,
        received=received_value,
        allocated=allocated_value,
        debt=max(accrued_value - allocated_value, Decimal("0.00")),
        completed_lessons=int(count or 0),
    )
