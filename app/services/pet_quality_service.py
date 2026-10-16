from .. import pet_quality
from ..db import get_db


def init_schema():
    get_db().executescript(pet_quality.SCHEMA)


def state(task):
    return pet_quality.state(get_db(), task)


def require(task, through):
    pet_quality.require(get_db(), task, through)


def ready(task):
    try:
        require(task, 'motion')
        return True
    except ValueError:
        return False
