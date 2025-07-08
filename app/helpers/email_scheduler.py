import os
from datetime import datetime, timedelta

import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app import db
from app.models import ScheduledEmail, User


def send_slack_notification(message, channel="#alerts"):
    """Send notification to Slack"""
    webhook_url = os.environ.get("SLACK_WEBHOOK")
    if not webhook_url:
        print(f"Slack notification (no webhook): {message}")
        return

    try:
        payload = {"text": message, "channel": channel}
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")


def schedule_welcome_email(user_id, template_id=None):
    """Schedule a welcome email for a new Pro subscriber"""
    user = User.query.get(user_id)
    if not user:
        return False

    # Use default template ID if not provided
    if not template_id:
        template_id = "d-aa753a1f26d74c13ba14b9910c0c1284"

    # Schedule for immediate sending
    scheduled_email = ScheduledEmail(
        user_id=user_id,
        email_type="welcome_pro",
        scheduled_for=datetime.utcnow(),
        template_id=template_id,
        dynamic_template_data={
            "first_name": user.first_name,
            "email": user.email,
        },
    )

    db.session.add(scheduled_email)
    db.session.commit()

    return scheduled_email


def schedule_trial_reminder_email(user_id, template_id=None):
    """Schedule a trial reminder email for 6 days after Pro subscription"""
    user = User.query.get(user_id)
    if not user:
        return False

    # Use default template ID if not provided
    if not template_id:
        template_id = "d-8eab44c4ce364ae9b4fc45217b4b9a95"

    # Schedule for 6 days from now
    scheduled_for = datetime.utcnow() + timedelta(days=6)

    scheduled_email = ScheduledEmail(
        user_id=user_id,
        email_type="trial_reminder",
        scheduled_for=scheduled_for,
        template_id=template_id,
        dynamic_template_data={
            "first_name": user.first_name,
            "email": user.email,
            "trial_end_date": scheduled_for.strftime("%B %d, %Y"),
        },
    )

    db.session.add(scheduled_email)
    db.session.commit()

    return scheduled_email


def send_scheduled_email(scheduled_email):
    """Send a scheduled email using SendGrid"""
    try:
        user = scheduled_email.user
        if not user:
            return False

        message = Mail(from_email=("hello@zentacle.com", "Zentacle"), to_emails=user.email)
        message.reply_to = "mayank@zentacle.com"
        message.template_id = scheduled_email.template_id
        message.dynamic_template_data = scheduled_email.dynamic_template_data or {}

        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
        sg.send(message)

        # Mark as sent
        scheduled_email.sent_at = datetime.utcnow()
        db.session.commit()

        return True

    except Exception as e:
        error_msg = f"Error sending scheduled email {scheduled_email.id}: {e}"
        print(error_msg)
        send_slack_notification(f"❌ @channel - Email sending failed: {error_msg}")
        return False


def process_due_emails():
    """Process all emails that are due to be sent"""
    now = datetime.utcnow()

    # Get all unsent emails that are due
    due_emails = ScheduledEmail.query.filter(
        ScheduledEmail.sent_at.is_(None), ScheduledEmail.scheduled_for <= now
    ).all()

    sent_count = 0
    failed_count = 0

    for email in due_emails:
        if send_scheduled_email(email):
            sent_count += 1
        else:
            failed_count += 1

    # Send summary to Slack
    if due_emails:
        summary = f"📧 Email processing complete: {sent_count} sent, {failed_count} failed, {len(due_emails)} total"
        send_slack_notification(summary)

    return {"sent": sent_count, "failed": failed_count, "total_processed": len(due_emails)}


def check_scheduler_health():
    """Check if scheduler is running properly by looking for recent activity"""
    now = datetime.utcnow()

    # Check for emails that should have been sent but weren't
    overdue_emails = ScheduledEmail.query.filter(
        ScheduledEmail.sent_at.is_(None), ScheduledEmail.scheduled_for <= now - timedelta(hours=1)  # Overdue by 1 hour
    ).count()

    # Check for recent email processing activity
    recent_activity = ScheduledEmail.query.filter(
        ScheduledEmail.sent_at >= now - timedelta(days=14)  # Activity in last 2 hours
    ).count()

    if overdue_emails > 0:
        send_slack_notification(f"⚠️ Scheduler Health Check: {overdue_emails} emails are overdue by more than 1 hour")

    if recent_activity == 0:
        send_slack_notification("⚠️ Scheduler Health Check: No email activity in the last 2 hours")

    return {
        "overdue_emails": overdue_emails,
        "recent_activity": recent_activity,
        "healthy": overdue_emails == 0 and recent_activity > 0,
    }


def cancel_scheduled_emails(user_id, email_type=None):
    """Cancel scheduled emails for a user, optionally filtered by type"""
    query = ScheduledEmail.query.filter(ScheduledEmail.user_id == user_id, ScheduledEmail.sent_at.is_(None))

    if email_type:
        query = query.filter(ScheduledEmail.email_type == email_type)

    # Delete the scheduled emails
    deleted_count = query.delete()
    db.session.commit()

    return deleted_count
