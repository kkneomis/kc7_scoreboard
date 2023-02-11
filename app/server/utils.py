# Import internal modules
from app.server.models import db
from app.server.models import GameSessions, Solves, Challenges, Users
from app import cache
import requests

# Import external modules
from fileinput import filename
import random
from faker import Faker
from faker.providers import internet, lorem, file
from sqlalchemy.sql.expression import union_all
from itsdangerous import base64_encode
import string
from functools import wraps
from time import time

# instantiate faker
fake = Faker()
fake.add_provider(internet)
fake.add_provider(file)
fake.add_provider(lorem)



def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time()
        result = f(*args, **kw)
        te = time()
        print(f"function {f.__name__} took: {te-ts}")
        # print 'func:%r args:[%r, %r] took: %2.4f sec' % (f.__name__, args, kw, te-ts)
        return result
    return wrap

def ordinalize(n):
    """
    http://codegolf.stackexchange.com/a/4712
    """
    k = n % 10
    return "%d%s" % (n, "tsnrhtdd"[(n // 10 % 10 != 1) * (k < 4) * k :: 4])


@cache.memoize(timeout=60)
def get_user_standings(game_session_id):
    scores = (
        db.session.query(
            Solves.user_id.label("user_id"),
            db.func.sum(Challenges.value).label("score"),
            db.func.max(Solves.id).label("id")
            # db.func.max(Solves.date).label("date"),
        )
        .join(Challenges)
        .join(GameSessions)
        .filter(GameSessions.id == game_session_id)
        .filter(Challenges.value != 0)
        .filter(Solves.user_id != 1)
        .group_by(Solves.user_id)
        .subquery()
    )

    standings_query = (
            db.session.query(
                Users.id.label("user_id"),
                Users.username.label("name"),
                scores.columns.score
            )
            .join(scores, Users.id == scores.columns.user_id)
            .order_by(scores.columns.score.desc(), scores.columns.id)
        )

    standings = standings_query.all()

    return standings


def generate_password(length=8):
    chars = string.ascii_letters + string.digits 
    return ''.join(random.choice(chars) for _ in range(length))


 # Get files to load from json
def load_json_from_github(path):
    url = f"https://raw.githubusercontent.com/kkneomis/kc7_data/d6b756b367b03910db0ce3a0d8e9ef5b8c35b458/Questions/{path}"
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to load JSON from GitHub ({response.status_code})")