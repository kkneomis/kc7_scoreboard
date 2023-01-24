# Import internal modules
from app.server.models import db
from app.server.models import GameSessions, Solves, Challenges, Users
from app import cache

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