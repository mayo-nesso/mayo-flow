"""Season-start reminders for members with an active booking."""
from allotment.core import members, plots


def send_season_start(conn, payload, outbox):
    """Queue one reminder per active booking of payload["season"]."""
    rows = conn.execute("SELECT * FROM bookings WHERE season = ? AND "
                        "status = 'active' ORDER BY id", (payload["season"],))
    sent = 0
    for row in rows:
        member = members.get(conn, row["member_id"])
        if not member.email:
            continue
        plot = plots.get(conn, row["plot_id"])
        outbox.append({
            "to": member.email,
            "template": "season_start",
            "vars": {"name": member.name, "plot": plot.code,
                     "season": payload["season"]},
        })
        sent += 1
    return sent
