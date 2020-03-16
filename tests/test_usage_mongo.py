import os
import subprocess

import pytest
import dockerdb.mongo_pytest


BASE_PATH = os.path.dirname(__file__)
DUMP_PATH = os.path.join(BASE_PATH, 'dump')
ERROR_DUMP_PATH = os.path.join(BASE_PATH, 'error_dump')

DATA = {
    'dbname': {
        'user_collection':
            [
                {'user': 'admin', 'password': 'secret'}
            ]
    }
}

# have two different versions of mongo with static data
mongo = dockerdb.mongo_pytest.mongo_fixture(versions=["3.4", "3.5"], data=DATA)

# with data from a mongodump backup
mongo2 = dockerdb.mongo_pytest.mongo_fixture(versions=["3.4"], restore=DUMP_PATH)


def test_package_consistent():
    # ensure restore path does actually exist
    assert os.path.exists(DUMP_PATH)
    assert os.path.exists(ERROR_DUMP_PATH)


def test_mongo_1(mongo):
    # this should be run twice
    client = mongo.pymongo_client()
    users = client['dbname']['user_collection']
    user = users.find_one({'user': 'admin'})
    assert user['password'] == 'secret'

    # changes to db should not persist to next test
    users.update({'user': 'admin'}, {'password': 'public'})


def test_mongo_2(mongo):
    # mongo db should be cleared after test_mongo_1
    client = mongo.pymongo_client()
    users = client['dbname']['user_collection']
    user = users.find_one({'user': 'admin'})
    assert user['password'] == 'secret'
    assert users.find().count() == 1


def test_mongo_restore(mongo2):
    client = mongo2.pymongo_client()
    users = client['test']['user']
    user = users.find_one({'user': 'admin'})
    assert user['password'] == 'reallysecret'

    # Check that loading a broken dump throws an error
    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        dockerdb.mongo_pytest.mongorestore(mongo2, ERROR_DUMP_PATH)

    exception = exc_info.value
    assert exception.cmd[0] == 'mongorestore'
    assert exception.returncode == 1
    assert 'unexpected EOF' in exception.output
