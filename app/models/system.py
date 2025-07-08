"""
System models.

This module contains models for system-level functionality:
- ScheduledEmail: Email scheduling for automated communications
"""

from datetime import datetime

from sqlalchemy import func

from . import db


class ScheduledEmail(db.Model):
    """Model to track scheduled emails for Pro subscription automation"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    email_type = db.Column(db.String, nullable=False)  # 'welcome_pro', 'trial_reminder'
    scheduled_for = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    template_id = db.Column(db.String, nullable=False)
    dynamic_template_data = db.Column(db.JSON, nullable=True)
    created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated = db.Column(
        db.DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.current_timestamp(),
    )

    user = db.relationship("User", backref="scheduled_emails")

    def get_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "email_type": self.email_type,
            "scheduled_for": self.scheduled_for.isoformat() if self.scheduled_for else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "template_id": self.template_id,
            "dynamic_template_data": self.dynamic_template_data,
            "created": self.created.isoformat() if self.created else None,
        }
