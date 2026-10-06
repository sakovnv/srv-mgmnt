import sqlite3

from microfleet.database import Database
from microfleet.models import Microservice, Server


def test_server_and_service_roundtrip(tmp_path):
    db = Database(tmp_path / "test.db")
    server = db.save_server(
        Server(
            name="prod-1", host="10.0.0.1", ssh_user="deploy", run_as_user="apps",
            management_script_path="/opt/apps/manage.sh",
        )
    )
    assert server.id is not None
    service = db.save_service(
        Microservice(server_id=server.id, name="orders")
    )
    assert db.list_servers()[0].name == "prod-1"
    assert db.list_servers()[0].management_script_path == "/opt/apps/manage.sh"
    assert db.list_services(server.id)[0] == service

    db.delete_server(server.id)
    assert db.list_services(server.id) == []


def test_existing_database_migrates_without_losing_services(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE servers (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, host TEXT NOT NULL,
                port INTEGER NOT NULL, ssh_user TEXT NOT NULL,
                run_as_user TEXT NOT NULL, auth_type TEXT NOT NULL,
                key_path TEXT NOT NULL, group_name TEXT NOT NULL, notes TEXT NOT NULL
            );
            CREATE TABLE microservices (
                id INTEGER PRIMARY KEY, server_id INTEGER NOT NULL,
                name TEXT NOT NULL, script_path TEXT NOT NULL,
                description TEXT NOT NULL, sort_order INTEGER NOT NULL
            );
            INSERT INTO servers VALUES (1, 'prod', '10.0.0.1', 22, 'deploy',
                'apps', 'key', '', '', '');
            INSERT INTO microservices VALUES (1, 1, 'orders',
                '/old/service.sh', 'Orders API', 0);
            """
        )

    db = Database(path)
    server = db.list_servers()[0]
    assert server.management_script_path == ""
    assert db.list_services(server.id)[0].name == "orders"
    server.management_script_path = "/opt/manage.sh"
    db.save_server(server)
    assert db.list_servers()[0].management_script_path == "/opt/manage.sh"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT script_path FROM microservices").fetchone()[0] == "/old/service.sh"
