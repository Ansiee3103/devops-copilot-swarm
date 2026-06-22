import json
from sqlalchemy.orm import Session
from backend.models.review import DeploymentReview
from backend.core.logger import get_logger
from datetime import datetime, timezone, timedelta

logger = get_logger("collaboration")
IST    = timezone(timedelta(hours=5, minutes=30))

class CollaborationService:

    def create_review(self, db: Session, deployment_id: int,
                      requester: str, service_name: str) -> dict:
        review = DeploymentReview(
            deployment_id = deployment_id,
            service_name  = service_name,
            requester     = requester,
            status        = "pending",
            approvals     = "[]",
            rejections    = "[]",
            comments      = "[]"
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return self._to_dict(review)

    def approve(self, db: Session, deployment_id: int,
                approver: str, comment: str = "") -> dict:
        review = db.query(DeploymentReview).filter(
            DeploymentReview.deployment_id == deployment_id
        ).first()

        if not review:
            return {"error": "Review not found"}

        approvals = json.loads(review.approvals)
        if not any(a["user"] == approver for a in approvals):
            approvals.append({
                "user":       approver,
                "comment":    comment,
                "approved_at": datetime.now(IST).isoformat()
            })
            review.approvals  = json.dumps(approvals)
            review.updated_at = datetime.now(IST)

        if len(approvals) >= review.required_approvals:
            review.status = "approved"

        db.commit()
        return self._to_dict(review)

    def reject(self, db: Session, deployment_id: int,
               rejector: str, reason: str) -> dict:
        review = db.query(DeploymentReview).filter(
            DeploymentReview.deployment_id == deployment_id
        ).first()

        if not review:
            return {"error": "Review not found"}

        rejections = json.loads(review.rejections)
        rejections.append({
            "user":        rejector,
            "reason":      reason,
            "rejected_at": datetime.now(IST).isoformat()
        })
        review.rejections = json.dumps(rejections)
        review.status     = "rejected"
        review.updated_at = datetime.now(IST)
        db.commit()
        return self._to_dict(review)

    def add_comment(self, db: Session, deployment_id: int,
                    user: str, comment: str) -> dict:
        review = db.query(DeploymentReview).filter(
            DeploymentReview.deployment_id == deployment_id
        ).first()

        if review:
            comments = json.loads(review.comments)
            comments.append({
                "user":       user,
                "comment":    comment,
                "created_at": datetime.now(IST).isoformat()
            })
            review.comments   = json.dumps(comments)
            review.updated_at = datetime.now(IST)
            db.commit()
        return self._to_dict(review) if review else {"error": "Not found"}

    def get_review(self, db: Session, deployment_id: int) -> dict:
        review = db.query(DeploymentReview).filter(
            DeploymentReview.deployment_id == deployment_id
        ).first()
        return self._to_dict(review) if review else {"error": "Not found"}

    def _to_dict(self, review: DeploymentReview) -> dict:
        return {
            "id":                 review.id,
            "deployment_id":      review.deployment_id,
            "service_name":       review.service_name,
            "requester":          review.requester,
            "status":             review.status,
            "required_approvals": review.required_approvals,
            "approvals":          json.loads(review.approvals),
            "rejections":         json.loads(review.rejections),
            "comments":           json.loads(review.comments),
            "created_at":         str(review.created_at)
        }

collaboration_service = CollaborationService()