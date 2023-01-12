from itsdangerous import URLSafeTimedSerializer

from .. import app
from flask import current_app

with app.app_context():
    ts = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])