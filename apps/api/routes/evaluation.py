"""Evaluation endpoint (§31, §54): WER/CER vs ground truth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db_session
from apps.api.schemas import EvaluationRequest, EvaluationResultOut
from database import models
from training.evaluation import evaluate

router = APIRouter(prefix="/api", tags=["evaluation"])


@router.post("/evaluation", response_model=EvaluationResultOut)
def run_evaluation(
    body: EvaluationRequest,
    db: Session = Depends(get_db_session),
) -> EvaluationResultOut:
    if len(body.predictions) != len(body.references):
        raise HTTPException(
            status_code=400, detail="predictions and references must have the same length."
        )
    if not body.references:
        raise HTTPException(status_code=400, detail="At least one reference is required.")

    result = evaluate(body.predictions, body.references)
    row = models.EvaluationRun(
        name=body.name, wer=result.wer, cer=result.cer,
        sentence_accuracy=result.sentence_accuracy,
        details={"per_sample": result.per_sample}, model_version=body.model_version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EvaluationResultOut(
        id=row.id, name=body.name, wer=result.wer, cer=result.cer,
        sentence_accuracy=result.sentence_accuracy, n=result.n,
        details={"per_sample": result.per_sample},
    )
