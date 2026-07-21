from bussola.data.connection import connect

from .conftest import requires_db


@requires_db
def test_owner_can_connect():
    with connect("owner") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
