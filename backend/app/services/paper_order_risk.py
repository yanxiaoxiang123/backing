"""Mandatory risk evidence and current-state checks at each order transition."""

from datetime import date, datetime
import hashlib
import json

from app.agent_runtime.artifacts import filename_of, read_artifact
from app.domain.risk import PortfolioRiskRequest
from app.models.agent_runtime import ArtifactRecord
from app.services.market_data import digest, naive_utc
from app.services.paper_risk_assessment import assess_paper_risk


def validate_order_risk(db, *, run_id: str, risk_artifact_id: int | None,
                        stock_code: str, side: str, quantity: int, at: datetime,
                        stage: str, limit_price: float | None = None,
                        order_id: str | None = None, trade_date: date | None = None,
                        fill_price: float | None = None) -> dict:
    if risk_artifact_id is None:
        raise ValueError("订单缺少风险评估证据；请先提交明确目标并评估")
    artifact = db.get(ArtifactRecord, risk_artifact_id)
    if artifact is None or artifact.run_id != run_id or artifact.artifact_type != "portfolio_risk_assessment":
        raise ValueError("风险证据不存在或不属于当前研究运行")
    content = read_artifact(run_id, filename_of(artifact.uri))
    if content is None or hashlib.sha256(content.encode()).hexdigest() != artifact.checksum:
        raise ValueError("风险证据文件缺失或校验失败")
    saved = json.loads(content)
    if (saved.get("engine_version") != "portfolio-risk-v1" or saved.get("run_id") != run_id
            or saved.get("proposal", {}).get("rejected", True)
            or digest(saved.get("evidence")) != saved.get("evidence_sha256")):
        raise ValueError("风险评估未通过或证据指纹无效")
    age = (naive_utc(at) - naive_utc(datetime.fromisoformat(saved["as_of"]))).total_seconds()
    if age < 0 or (stage == "propose" and age > 300):
        raise ValueError("风险评估已过期或来自未来，请重新评估")
    allowed = next((row for row in saved.get("orders", [])
                    if row["stock_code"] == stock_code and row["side"] == side), None)
    if allowed is None or not 0 < quantity <= allowed["quantity"]:
        raise ValueError("订单证券、方向或数量超出已评估范围")
    request = PortfolioRiskRequest.model_validate(saved["evidence"]["request"])
    report = assess_paper_risk(
        db, run_id, request, at=at, persist=False, exclude_order_id=order_id, trade_date=trade_date,
        exact_order={"stock_code": stock_code, "side": side, "quantity": quantity,
                     "limit_price": limit_price, "reference_price": fill_price},
    )
    if report["proposal"]["rejected"]:
        raise ValueError("订单风险复核未通过：" + "；".join(report["proposal"]["rejection_reasons"]))
    if report["account_id"] != saved["account_id"]:
        raise ValueError("风险评估账户与当前账本不一致")
    return {"risk_artifact_id": risk_artifact_id, "stage": stage,
            "assessment": report, "original_evidence_sha256": saved["evidence_sha256"]}
