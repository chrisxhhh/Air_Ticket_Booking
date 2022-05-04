from flask import Flask, session, redirect, url_for
import pymysql.cursors


app = Flask(__name__)


app.config.from_mapping(
    SECRET_KEY='dev',
)


db_conn = pymysql.connect(host='localhost',
                             user='root',
                             password='65410173asdf',
                             db='ticket_sys',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

from . import auth, route_main, internal
app.register_blueprint(auth.bp)
app.register_blueprint(internal.bp)








