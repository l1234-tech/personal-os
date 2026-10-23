from datetime import UTC
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.finance_schemas import FinanceSummary, FinanceTransactionCreate, FinanceTransactionRead
from app.models import User
from app.models_finance import FinanceTransaction

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/transactions", response_model=list[FinanceTransactionRead])
def list_transactions(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[FinanceTransaction]:
    query = (
        select(FinanceTransaction)
        .where(FinanceTransaction.user_id == user.id)
        .order_by(FinanceTransaction.occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(query).all())


@router.post(
    "/transactions",
    response_model=FinanceTransactionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: FinanceTransactionCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> FinanceTransaction:
    item = FinanceTransaction(
        user_id=user.id,
        kind=payload.kind,
        amount=payload.amount,
        currency_code=payload.currency_code,
        category=payload.category,
        description=payload.description,
        occurred_at=payload.occurred_at.astimezone(UTC),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: UUID,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    query = select(FinanceTransaction).where(
        FinanceTransaction.id == transaction_id,
        FinanceTransaction.user_id == user.id,
    )
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail="Finance transaction not found")
    db.delete(item)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/summary", response_model=list[FinanceSummary])
def finance_summary(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[FinanceSummary]:
    query = (
        select(
            FinanceTransaction.currency_code,
            FinanceTransaction.kind,
            func.coalesce(func.sum(FinanceTransaction.amount), 0),
            func.count(FinanceTransaction.id),
        )
        .where(FinanceTransaction.user_id == user.id)
        .group_by(FinanceTransaction.currency_code, FinanceTransaction.kind)
    )
    rows = db.execute(query).all()
    totals: dict[str, dict[str, Decimal | int]] = {}
    for currency, kind, amount, count in rows:
        totals.setdefault(
            currency,
            {"income": Decimal("0"), "expenses": Decimal("0"), "transaction_count": 0},
        )
        key = "income" if kind == "income" else "expenses"
        totals[currency][key] = Decimal(str(totals[currency][key])) + Decimal(str(amount))
        totals[currency]["transaction_count"] = (
            int(totals[currency]["transaction_count"]) + int(count)
        )

    summaries: list[FinanceSummary] = []
    for currency, values in sorted(totals.items()):
        income = Decimal(str(values["income"]))
        expenses = Decimal(str(values["expenses"]))
        summaries.append(
            FinanceSummary(
                currency_code=currency,
                income=income,
                expenses=expenses,
                balance=income - expenses,
                transaction_count=int(values["transaction_count"]),
            )
        )
    return summaries
