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
def list_transactions(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[FinanceTransaction]:
    return list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.user_id == user.id).order_by(FinanceTransaction.occurred_at.desc()).limit(limit)).all())


@router.post("/transactions", response_model=FinanceTransactionRead, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: FinanceTransactionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> FinanceTransaction:
    item = FinanceTransaction(user_id=user.id, kind=payload.kind, amount=payload.amount, currency_code=payload.currency_code, category=payload.category, description=payload.description, occurred_at=payload.occurred_at.astimezone(UTC))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: UUID, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    item = db.scalar(select(FinanceTransaction).where(FinanceTransaction.id == transaction_id, FinanceTransaction.user_id == user.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Finance transaction not found")
    db.delete(item)
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/summary", response_model=list[FinanceSummary])
def finance_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[FinanceSummary]:
    rows = db.execute(select(FinanceTransaction.currency_code, FinanceTransaction.kind, func.coalesce(func.sum(FinanceTransaction.amount), 0), func.count(FinanceTransaction.id)).where(FinanceTransaction.user_id == user.id).group_by(FinanceTransaction.currency_code, FinanceTransaction.kind)).all()
    totals: dict[str, dict[str, Decimal | int]] = {}
    for currency, kind, amount, count in rows:
        totals.setdefault(currency, {"income": Decimal("0"), "expenses": Decimal("0"), "transaction_count": 0})
        key = "income" if kind == "income" else "expenses"
        totals[currency][key] = Decimal(str(totals[currency][key])) + Decimal(str(amount))
        totals[currency]["transaction_count"] = int(totals[currency]["transaction_count"]) + int(count)
    return [FinanceSummary(currency_code=currency, income=values["income"], expenses=values["expenses"], balance=Decimal(str(values["income"])) - Decimal(str(values["expenses"])), transaction_count=int(values["transaction_count"])) for currency, values in sorted(totals.items())]
