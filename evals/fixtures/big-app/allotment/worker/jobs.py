"""Job registry: queue kind -> handler(conn, payload, outbox)."""
from allotment.worker import reminders

JOBS = {
    "reminders.season_start": reminders.send_season_start,
}
