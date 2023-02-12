import os

# to set vars automatically in dev
# source ./set_config.py 


# in production check this out
# https://devcenter.heroku.com/articles/config-vars#managing-config-vars

def get_env_variable(name):
    try:
        return os.environ[name]
    except KeyError:
        message = "Expected env variable '{}' not set.".format(name)
        raise Exception(message)
    
class BaseConfig(object):
    DEBUG = False
    TESTING = False
    
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_CONNECT_OPTIONS = {}

    # Application threads. A common general assumption is
    # using 2 per available processor cores - to handle
    # incoming requests using one and performing background
    # operations using the other.
    THREADS_PER_PAGE = 2

    SQLALCHEMY_DATABASE_URI = 'sqlite:///flaskr.db'
    
    # Secret key for signing cookie. You should replace this
    SECRET_KEY = 'y?,???\???Z#?*t^_mzal(t@o01v3fee27g%rg18fc5d@'


    MAIL_USERNAME = "example@gmail.com"
    

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = True

    ADX_DEBUG_MODE=True   # Set to True if you don't want to write to Azure

    SQLALCHEMY_DATABASE_URI = 'sqlite:///flaskr.db'


class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True


    
class ProductionConfig(BaseConfig):
    DEBUG = False

    # Set the variables
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://{dbuser}:{dbpass}@{dbhost}:5432/{dbname}'.format(
        dbuser=os.environ['DBUSER'],
        dbpass=os.environ['DBPASS'],
        dbhost=os.environ['DBHOST'] + ".postgres.database.azure.com",
        dbname=os.environ['DBNAME']
    )

    MAIL_USERNAME= os.environ['MAIL_USERNAME']
