import subprocess

import pytest


# Store some global settings for a given test run. don't have a good place to put this
current_test_settings = {
    'db_allowed': False
}


@pytest.fixture(autouse=True)
def db_fixture_check(request):
    """
    Check for db fixture fixture, store this data in a global thing
    """
    db_allowed = 'db' in request.fixturenames
    current_test_settings['db_allowed'] = db_allowed

    yield

    current_test_settings['db_allowed'] = False


@pytest.fixture(scope='session')
def testdatabase_factory(request):
    """
    This is a factory function for making a "testdatabase" fixture to set up testing database.

    Usage:
    @pytest.fixture(scope='session')
    def testdatabase(testdatabase_factory):
        _testdatabase = testdatabase_factory(base, config.DATABASE_URL)
        yield from _testdatabase

     References
    - https://github.com/jeancochrane/pytest-flask-sqlalchemy/blob/master/pytest_flask_sqlalchemy/fixtures.py
    - https://gist.github.com/zzzeek/8443477
    """
    # Inline imports so this plugin can work if you don't have sqlalchemy and don't need this fixture
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.orm import sessionmaker, scoped_session

    def _testdatabase_factory(base, database_url, setup_global_test_fixtures=None):
        """
        Params:
        - base: Python module that contains Session, Base
        - database_url: The main DATABASE_URL
        - setup_global_test_fixtures: Callback to set up global fixtures
        """

        def testdatabase():
            """
            Set up session-wide test database
            Returns a dictionary, db_params, with engine and connection
            """
            reset_db = request.config.getoption("--reset-db")
            Base = base.Base

            db_params = {}
            engine = base.engine

            # Using the original DATABASE_URL, make a new TEST_DATABASE_URL for the test database
            # (same server but just different db name)
            url_parsed = make_url(database_url)

            # Just get the "base" Postgres URL without a database name
            BASE_DB_SERVER_URL = 'postgres://{}:{}@{}:{}'.format(
                url_parsed.username, url_parsed.password_original, url_parsed.host, url_parsed.port or 5432
            )
            # Assume there is a basic database called Postgres (we always have to connect to some database)
            DB_SERVER_URL = '{}/postgres'.format(BASE_DB_SERVER_URL)

            # Construct a separate URL for the test db (same server but separate test database name)
            test_db_name = '{}_test'.format(url_parsed.database)
            TEST_DB_URL = '{}/{}'.format(BASE_DB_SERVER_URL, test_db_name)

            temp_engine = create_engine(DB_SERVER_URL)
            temp_conn = temp_engine.connect()   # todo add code to wait for Postgres to be running
            temp_conn.execute('commit')    # end the already open transaction

            check_existing_db_query = (
                "SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower('{}')".format(
                    test_db_name
                )
            )
            res = temp_conn.execute(check_existing_db_query)
            existing_database_found = False
            tables_exist = None

            if len(list(res)) > 0:
                existing_database_found = True
                print('Test database already exists')
            else:
                temp_conn.execute('create database {}'.format(test_db_name))
                print('Creating test database:', test_db_name)
                tables_exist = False

            temp_conn.close()

            # Clear tables to reset schema, if requested
            if existing_database_found and reset_db:
                # Do dropdb instead of Base.metadata.drop_all_engine() because sometimes cascade-deletes fails
                # with FKs, if we are removing a table / changing the schema a lot
                print('Dropping/creating test database')
                subprocess.run('dropdb {}'.format(test_db_name), shell=True, check=True)
                subprocess.run('createdb {}'.format(test_db_name), shell=True, check=True)
                tables_exist = False

            base.initialize_database(TEST_DB_URL)
            engine = base.engine
            connection = engine.connect()

            if tables_exist is None:
                # Find out if tables exist
                num_tables = list(
                    connection.execute("select count(*) from information_schema.tables where table_schema='public'")
                )[0][0]
                tables_exist = num_tables > 0

            # Recreate sessions to bind to this new connection
            session_factory = sessionmaker(bind=connection)
            Session = scoped_session(session_factory)
            base.Session = Session

            Base.metadata.create_all(engine)
            print('Created all tables')

            if tables_exist is False and setup_global_test_fixtures is not None:
                # Set up global fixture if it's first time making DB (easier doing this vs trying to set up
                # another nested transaction
                setup_global_test_fixtures()

            session = Session

            db_params['engine'] = engine
            db_params['connection'] = connection
            db_params['session'] = session

            # Allow for nested transactions inside tests
            @event.listens_for(session, "after_transaction_end")
            def restart_savepoint(session, transaction):
                if transaction.nested and not transaction._parent.nested:
                    session.expire_all()
                    session.begin_nested()

            @event.listens_for(session, 'before_commit')
            def check_before_commit(session):
                if not current_test_settings['db_allowed']:
                    raise Exception("Test tried to access the database without declaring 'db' fixture")

            yield db_params

            connection.close()

        return testdatabase()

    return _testdatabase_factory


@pytest.fixture(scope='function')
def db(testdatabase):

    connection = testdatabase['connection']
    session = testdatabase['session']

    # Start a transaction for the test
    transaction = connection.begin()
    session.begin_nested()

    yield

    session.remove()
    transaction.rollback()
