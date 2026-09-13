import os
import psycopg2
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from alembic.config import Config
from alembic import command
app=Flask('voice_pilot_migration')
app.config['SQLALCHEMY_DATABASE_URI']=os.environ['DATABASE_URL']
db=SQLAlchemy(app)
Migrate(app,db)
configuration=Config()
configuration.set_main_option('script_location',os.environ.get('VOICE_MIGRATION_DIR','/app/alembic_migrations'))
lock=psycopg2.connect(os.environ['DATABASE_URL'])
lock.autocommit=True
try:
 cursor=lock.cursor()
 cursor.execute('SELECT pg_advisory_lock(883741)')
 with app.app_context():
  command.upgrade(configuration,'20260913_operator_request_audit')
 cursor.close()
finally:
 lock.close()
print('migration complete')
