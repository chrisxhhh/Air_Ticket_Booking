from functools import wraps
from flask import render_template, Blueprint, request, session, redirect, url_for, flash, g
import hashlib
from datetime import datetime

from air_system import db_conn

bp = Blueprint('auth', __name__, url_prefix="/auth")

def customer_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.type != "customer":
            flash("Please log in as a customer to access this page")
            return redirect(url_for('hello'))
        return f(*args, **kwargs)
    return decorated_function

def staff_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.type != "staff":
            flash("Please log in as a staff to access internal control")
            return redirect(url_for('hello'))
        return f(*args, **kwargs)
    return decorated_function

@bp.before_app_request
def load_user():
    print("running bp.before_app_request")
    username = session.get('username')
    user_type = session.get('type')
    user_email = session.get('user_email')
    airline = session.get('airline')
    if username is None:
        g.username = None
        g.type = None
        g.user_email = None
    else:
        g.username = username
        g.type = user_type
        if user_type == "customer":
            g.user_email = user_email
        elif user_type == "staff":
            g.airline = airline


@bp.route('/register', methods = ["POST", "GET"])
def register():
    if request.method == "GET":
        return render_template('auth/register.html')
    email = request.form['email']
    name = request.form['username']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()
    phone_num = request.form['phone_num']
    passport_num = request.form['passport_num']
    passport_expir_date = request.form['passport_expir_date']
    passport_country = request.form['passport_country']
    DOB = request.form['DOB']
    building_num = request.form['building_num']
    street = request.form['street']
    city = request.form['city']
    state = request.form['state']

    today = datetime.today().date()
    if datetime.strptime(DOB, "%Y-%m-%d").date() >= today:
        error = "Illegal DOB"
        return render_template('auth/register.html', error=error)


    cursor = db_conn.cursor()
    query = 'SELECT * FROM customer WHERE email = %s'
    cursor.execute(query, (email))
    data = cursor.fetchone()

    if data:
        error = "User already exists"
        cursor.close()
        return render_template('auth/register.html', error=error)
    else:
        action = 'INSERT INTO customer(email, name, password, phone_num, passport_num, passport_expir_date, ' \
                 'passport_country, DOB, building_num, street, city, state) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(action, (email, name, password, phone_num, passport_num, passport_expir_date, passport_country, DOB, building_num, street, city, state))
        db_conn.commit()
        cursor.close()
        flash("now you can log in your new account!")
        return redirect(url_for('auth.login'))

@bp.route('/login', methods = ["POST", "GET"])
def login():
    if request.method == "GET":
        if g.type:
            flash("welcome back {}".format(g.username))
            if g.type == "customer":
                return redirect(url_for('hello'))
            elif g.type == "staff":
                return redirect(url_for('internal.main_control'))
        return render_template('auth/login.html')
    email = request.form['email']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()

    cursor = db_conn.cursor()
    query = 'SELECT * FROM customer WHERE email = %s and password = %s'
    cursor.execute(query, (email, password))
    data = cursor.fetchone()
    cursor.close()
    if data:
        session.clear()
        session['user_email'] = email
        session['username'] = data['name']
        session['type'] = "customer"
        flash("you just logged in, {}".format(data['name']))
        return redirect(url_for('hello'))
    else:
        error = "wrong password or email does not exist, you can register first"
        return render_template('auth/login.html', error=error)


@bp.route('logout')
def logout():
    session.clear()
    flash("you just logged out")
    return redirect(url_for("hello"))


@bp.route('staff_login' , methods = ["POST", "GET"])
def staff_login():
    if request.method == "GET":
        if g.type:
            if g.type == "customer":
                flash("{}, please log out as user first".format(session['username']))
                return redirect(url_for('hello'))
            elif g.type == "staff":
                return redirect(url_for('internal.main_control'))
        return render_template('auth/staff_login.html')
    username = request.form['username']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()

    cursor = db_conn.cursor()
    query = 'SELECT * FROM airline_staff WHERE user_name = %s and password = %s'
    cursor.execute(query, (username, password))
    data = cursor.fetchone()
    cursor.close()

    if data:
        session.clear()
        session['username'] = username
        session['type'] = "staff"
        session['airline'] = data['airline']
        flash("you just logged in, {}".format(data['user_name']))
        return redirect(url_for('internal.main_control'))
    else:
        error = "wrong password or email does not exist, you can register first"
        return render_template('auth/staff_login.html', error=error)


@bp.route('staff_register', methods = ["POST", "GET"])
def staff_register():
    if request.method == "GET":
        return render_template('auth/staff_register.html')
    airline = request.form['airline']
    user_name = request.form['username']
    password = hashlib.md5(request.form['password'].encode()).hexdigest()
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    DOB = request.form['DOB']
    phone = request.form['phone']
    phone_lst = phone.split('\r\n')

    today = datetime.today().date()
    if datetime.strptime(DOB, "%Y-%m-%d").date() >= today:
        error = "Illegal DOB"
        return render_template('auth/staff_register.html', error=error)

    cursor = db_conn.cursor()
    query = 'SELECT * FROM airline WHERE name=%s'
    cursor.execute(query, (airline))
    data = cursor.fetchone()
    if not data:
        error = "Airline does not exist"
        cursor.close()
        return render_template('auth/staff_register.html', error=error)

    query = 'SELECT * FROM airline_staff WHERE user_name = %s'
    cursor.execute(query, (user_name))
    data = cursor.fetchone()
    if data:
        error = "Staff already exists"
        cursor.close()
        return render_template('auth/staff_register.html', error=error)

    for item in phone_lst:
        if len(item) > 15:
            cursor.close()
            error = "Phone number exceeds 15 digits"
            return render_template('auth/staff_register.html', error=error)

        query = 'SELECT * FROM phone_num WHERE number=%s'
        cursor.execute(query, (item))
        data = cursor.fetchone()
        if data:
            error = "Phone number already exists"
            cursor.close()
            return render_template('auth/staff_register.html', error=error)



    action = 'INSERT INTO airline_staff(airline,user_name, password, firt_name, last_name, DOB) VALUES(%s, %s, %s, %s, %s, %s)'
    cursor.execute(action, (airline,user_name, password, first_name, last_name, DOB))
    db_conn.commit()


    for item in phone_lst:
        action = 'INSERT INTO phone_num(number, user_name) values(%s,%s)'
        cursor.execute(action, (item, user_name))
        db_conn.commit()
    cursor.close()
    flash("registered successfully, now you can log in")
    return redirect(url_for('auth.staff_login'))




