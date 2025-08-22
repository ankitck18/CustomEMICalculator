from fastapi import FastAPI
from pydantic import BaseModel
import datetime as dt
from decimal import Decimal
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from emi_calculator import EMI_Calculator


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoanRequest(BaseModel):
    principal: float
    annual_rate: float
    years: int
    start_date: str  # YYYY-MM-DD
    frequency: str   # W, BW, M, Q, S, A
    convention: str  # 30/360, Actual/360, Actual/365, Actual/Actual


@app.post("/calculate-loan")
def calculate_loan(req: LoanRequest):
    start_date = dt.datetime.strptime(req.start_date, "%Y-%m-%d").date()

    calc = EMI_Calculator(
        principal=Decimal(str(req.principal)),
        annual_rate=Decimal(str(req.annual_rate)),
        start_date=start_date,
        years=req.years,
        convention=req.convention,
        frequency=req.frequency
    )

    schedule = calc.get_schedule()

    return {
        "emi": float(calc.emi),
        "schedule": schedule,
        "summary": {
            "total_principal": float(sum(r["Principal"] for r in schedule)),
            "total_interest": float(sum(r["Interest"] for r in schedule)),
            "total_payments": float(sum(r["Principal"] + r["Interest"] for r in schedule))
        }
    }
