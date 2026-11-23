"""Members of the garden association."""
import re

from allotment.core.errors import Invalid, NotFound
from allotment.core.models import Member

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def add(conn, name, concession=False, email=None):
    if not name.strip():
        raise Invalid("name is required")
    if email is not None and not EMAIL_RE.match(email):
        raise Invalid("bad email")
    cur = conn.execute(
        "INSERT INTO members (name, concession, email) VALUES (?, ?, ?)",
        (name.strip(), int(concession), email))
    return get(conn, cur.lastrowid)


def get(conn, member_id):
    row = conn.execute("SELECT * FROM members WHERE id = ?",
                       (member_id,)).fetchone()
    if row is None:
        raise NotFound(f"member {member_id}")
    return Member.from_row(row)


def set_email(conn, member_id, email):
    if not EMAIL_RE.match(email):
        raise Invalid("bad email")
    get(conn, member_id)
    conn.execute("UPDATE members SET email = ? WHERE id = ?",
                 (email, member_id))
