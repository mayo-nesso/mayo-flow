from allotment.core import members
from allotment.core.errors import Invalid
from tests.helpers import DbCase


class MembersTest(DbCase):
    def test_add(self):
        m = self.member("  Ines  ", concession=True)
        self.assertEqual((m.name, m.concession), ("Ines", True))

    def test_name_required(self):
        with self.assertRaises(Invalid):
            members.add(self.conn, " ")

    def test_email_checked(self):
        with self.assertRaises(Invalid):
            members.add(self.conn, "Bo", email="not-an-email")
        m = members.add(self.conn, "Bo")
        members.set_email(self.conn, m.id, "bo@example.org")
        self.assertEqual(members.get(self.conn, m.id).email, "bo@example.org")
