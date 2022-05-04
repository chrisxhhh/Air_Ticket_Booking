from flask import render_template, Blueprint, request, session, redirect, url_for, flash, g
from air_system import db_conn
from air_system.auth import staff_login_required
from air_system.utility import process_time

import math, json
from datetime import datetime, date
from dateutil.relativedelta import *

bp = Blueprint('internal', __name__, url_prefix="/internal")

@bp.route('/main')
@staff_login_required
def main_control():
    airline = g.airline
    cursor = db_conn.cursor()
    start_day = datetime.today().date()
    end_day = start_day + relativedelta(days=+30)

    query = ['SELECT * FROM flight WHERE airline = %s and dept_date >= %s and dept_date <= %s']
    args = [airline, str(start_day), str(end_day)]
    end = ' ORDER BY dept_date, dept_time'
    if 'filter' in request.args:
        print('yes')
        if request.args['start_date'] is not '':
            args[1] = request.args.get('start_date')
        else:
            args[1] = '1970-01-01'
        if request.args['end_date'] is not '':
            args[2] = request.args.get('end_date')
        else:
            args[2] = '2100-01-01'
        if request.args['from'] is not '':
            dept_airport = request.args.get('from')
            query.append(' AND dept_airport=%s')
            args.append(dept_airport)
        if request.args['to'] is not '':
            arr_airport = request.args.get('to')
            query.append(' AND arr_airport=%s')
            args.append(arr_airport)
    query.append(end)
    query = ''.join(query)
    cursor.execute(query, tuple(args))
    data = cursor.fetchall()
    search_order = 0

    for item in data:
        query = 'SELECT num_seat FROM airplane WHERE airline = %s and ID = %s'
        cursor.execute(query,(item['airplane_airline'], item['airplane_id']))
        max_capacity= cursor.fetchone()
        max_capacity = max_capacity['num_seat']
        #max_capacity = int(cursor.fetchone()['num_seat'])
        query = 'SELECT travel_class, COUNT(ID) as num FROM ticket WHERE airline = %s and flight_num = %s and dept_time = %s ' \
                'and dept_date = %s GROUP BY travel_class'
        cursor.execute(query, (item['airline'], item['flight_num'], item['dept_time'], item['dept_date']))
        tickets = cursor.fetchall()
        sold_ticket = [0, 0, 0]

        for ticket in tickets:
            if ticket["travel_class"] == "Economy":
                sold_ticket[0] = ticket['num']
            elif ticket["travel_class"] == "Business":
                sold_ticket[1] = ticket['num']
            else:
                sold_ticket[2] = ticket['num']

        item['capacity_class'] = [
            str(sold_ticket[0])+' / '+str(math.floor(max_capacity*0.85)),
            str(sold_ticket[1]) + ' / ' + str(math.floor(max_capacity * 0.1)),
            str(sold_ticket[2]) + ' / ' + str(max_capacity-math.floor(max_capacity*0.85)-math.floor(max_capacity * 0.1))
        ]

        item['search_order'] = search_order
        search_order += 1

        item['dept_date'] = str(item['dept_date'])
        item['dept_time'] = process_time(item['dept_time'])
        item['arr_date'] = str(item['arr_date'])
        item['arr_time'] = process_time(item['arr_time'])

    session['search_res'] = data
    #print(data)
    cursor.close()
    return render_template("internal/main_control.html", username=g.username, data=data)


@bp.route('/create_flight', methods=["GET", "POST"])
@staff_login_required
def create_flight():
    if request.method == "GET":
        return render_template("internal/create_flight.html")
    airline = g.airline

    flight_num = request.form['flight_num']
    dept_date = request.form['dept_date']
    dept_time = request.form['dept_time']
    arr_date = request.form['arr_date']
    arr_time = request.form['arr_time']
    dept_airport = request.form['dept_airport']
    arr_airport = request.form['arr_airport']
    base_price = float(request.form['base_price'])
    status = "on-time"
    airplane_airline = request.form['airplane_airline']
    airplane_id = request.form['airplane_id']

    if base_price < 0:
        flash('illegal price input, please try again')
        return redirect(url_for('internal.create_flight'))

    cursor = db_conn.cursor()

    query = 'SELECT count(code) as num FROM airport WHERE code=%s OR code=%s'
    cursor.execute(query, (dept_airport, arr_airport))
    data = cursor.fetchone()['num']
    if data <2:
        flash("departure or arrival airport does not exist")
        return redirect(url_for('internal.create_flight'))

    query = 'SELECT * FROM airplane WHERE airline=%s and ID=%s'
    cursor.execute(query,(airplane_airline, airplane_id))
    data = cursor.fetchone()
    if not data:
        flash("{} does not have airplane ID {}, please try again".format(airplane_airline, airplane_id))
        return redirect(url_for('internal.create_flight'))

    query = 'SELECT * FROM flight WHERE airline = %s and flight_num = %s and dept_date = %s and dept_time = %s'
    cursor.execute(query, (airline,flight_num,dept_date,dept_time))
    data = cursor.fetchone()
    if data:
        flash("this flight already exists")
        cursor.close()
        return render_template("internal/create_flight.html")
    else:

        action = 'INSERT INTO flight(airline,flight_num, dept_date, dept_time, arr_date, arr_time, dept_airport, arr_airport, base_price, status, airplane_airline, airplane_id) ' \
                 'VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(action, (airline, flight_num, dept_date, dept_time, arr_date, arr_time, dept_airport, arr_airport, base_price, status, airplane_airline, airplane_id))
        db_conn.commit()
        cursor.close()
        flash("new flight is created")
        return redirect(url_for('internal.create_flight'))


@bp.route('/flight-<num>', methods=["POST", "GET"])
@staff_login_required
def show_detail(num):
    for item in session['search_res']:
        if item["search_order"] == int(num):
            target = item

    airline = g.airline
    flight_num = target['flight_num']
    dept_date = target['dept_date']
    dept_time = target['dept_time'] + ":00"
    cursor = db_conn.cursor()
    query = 'SELECT AVG(rate) as avg_rate from ticket where airline=%s and flight_num=%s and dept_date=%s and dept_time=%s'
    cursor.execute(query, (airline, flight_num, dept_date, dept_time))
    avg_rate = cursor.fetchone()['avg_rate']
    if avg_rate is None:
        avg_rate = 'Unknown'
    else:
        avg_rate = round(avg_rate,2)
    query = 'SELECT rate, comment from ticket where airline=%s and flight_num=%s and dept_date=%s and dept_time=%s'
    cursor.execute(query, (airline, flight_num, dept_date, dept_time))
    comment = cursor.fetchall()

    #fetch customer list
    query = 'SELECT distinct email, name FROM ticket NATURAL JOIN customer where airline=%s and flight_num=%s ' \
            'and dept_date=%s and dept_time=%s '
    cursor.execute(query, (airline, flight_num, dept_date, dept_time))
    customer_lst = cursor.fetchall()
    print(customer_lst)
    if request.method == "POST":
        new_status = request.form['new_status']
        if new_status != "canceled":
            new_dept_date = request.form['dept_date']
            new_arr_date = request.form['arr_date']
            new_dept_time = request.form['dept_time']
            new_arr_time = request.form['arr_time']
            action = "UPDATE flight SET status =%s, dept_date=%s, dept_time=%s, arr_date=%s, arr_time=%s WHERE airline=%s and flight_num=%s and dept_date=%s and dept_time=%s"
            cursor.execute(action, (new_status, new_dept_date, new_dept_time, new_arr_date, new_arr_time, airline, flight_num, dept_date, dept_time))
        else:
            action = "UPDATE flight SET status =%s WHERE airline=%s and flight_num=%s and dept_date=%s and dept_time=%s"
            cursor.execute(action, (new_status, airline, flight_num, dept_date, dept_time))

        db_conn.commit()
        cursor.close()
        target['status'] = new_status
        target['dept_date'] = new_dept_date
        target['dept_time'] = new_dept_time
        target['arr_date'] = new_arr_date
        target['arr_time'] = new_arr_time
        flash("status change success")
        return redirect(url_for('internal.show_detail', num=num))
    return render_template("internal/flight_detail.html", item=target, avg_rate=avg_rate, comment=comment, customer_lst=customer_lst)


@bp.route('/airplane', methods=["POST", "GET"])
@staff_login_required
def airplane():
    airline = g.airline
    cursor = db_conn.cursor()
    if request.method == "POST":
        id = request.form['ID']
        manufacturer = request.form['manufacturer']
        seat_num = request.form['seat_number']
        age = request.form['age']
        if seat_num <= 0 or age < 0:
            flash("seat_num or age can not be negative number")
            return redirect(url_for('internal.airplane'))
        query = 'SELECT * FROM airplane WHERE airline=%s and id=%s'
        cursor.execute(query, (airline, id))
        data = cursor.fetchone()
        if data:
            flash("this ID is already taken in {}".format(airline))
            return redirect(url_for('internal.airplane'))
        action = 'INSERT INTO airplane(airline, id, manufacturer, num_seat, age) value (%s, %s, %s, %s, %s)'
        cursor.execute(action,(airline, id, manufacturer, seat_num, age))
        db_conn.commit()
        flash("new airplane is created")
        return redirect(url_for('internal.airplane'))

    query = 'SELECT * FROM airplane WHERE airline = %s'
    cursor.execute(query, (airline))
    data = cursor.fetchall()
    cursor.close()
    return render_template("internal/create_airplane.html", data=data)

@bp.route('/airport', methods=["POST", "GET"])
@staff_login_required
def airport():
    cursor = db_conn.cursor()
    if request.method == "POST":
        code = request.form['code']
        name = request.form['name']
        city = request.form['city']
        country = request.form['country']
        type = request.form['type']
        query = 'SELECT * FROM airport WHERE code=%s'
        cursor.execute(query,(code))
        data = cursor.fetchone()
        if data:
            flash("this code already exists, please enter another one")
            return redirect("internal.airport")

        action = 'INSERT INTO airport(code, name, city, country, type) value (%s, %s, %s, %s, %s)'
        cursor.execute(action, (code, name, city, country, type))
        db_conn.commit()
        flash("new airport is created")
        return redirect("internal.airport")

    query = 'SELECT * FROM airport'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template("internal/create_airport.html", data=data)


@bp.route('/user_stat')
@staff_login_required
def user_stat():
    cursor = db_conn.cursor()
    #max_ticket = 0

    query = 'SELECT email FROM customer'
    cursor.execute(query)
    customer_lst = cursor.fetchall()

    customer_with_flight = []

    for item in customer_lst:
        query = 'SELECT flight_num, dept_date, dept_time, travel_class FROM ticket WHERE email=%s and airline=%s'
        cursor.execute(query,(item['email'], g.airline))
        data = cursor.fetchall()
        if len(data) != 0:
            customer_with_flight.append((item['email'], data))

    query = 'SELECT name, count(ID) as num FROM ticket NATURAL JOIN customer where date>=%s and date <=%s GROUP BY email ORDER BY num DESC'
    today = datetime.today().date()
    year_ago = today+relativedelta(years=-1)
    cursor.execute(query,(year_ago, today))
    loyal = cursor.fetchone()

    cursor.close()
    return render_template('internal/user_stat.html', customer_with_flight=customer_with_flight, loyal=loyal )


@bp.route('/revenue_stat')
@staff_login_required
def revenue_stat():
    airline = g.airline
    if not request.args.get('start_date'):
        end_date = datetime.today().date()
        start_date = end_date+relativedelta(months=-1)
    else:
        end_date = datetime.strptime(request.args['end_date'],"%Y-%m-%d").date()
        start_date = datetime.strptime(request.args['start_date'],"%Y-%m-%d").date()
        if start_date > datetime.today().date() or start_date > end_date:
            flash('error: please enter valid dates')
            return redirect(url_for('internal.revenue_stat'))
    cursor = db_conn.cursor()
    query = "SELECT COUNT(ID) as num, SUM(sold_price) as rev FROM ticket WHERE airline=%s and date <= %s and date >= %s"
    cursor.execute(query, (airline, end_date, start_date))
    data = cursor.fetchone()
    total_ticket = data['num']
    total_revenue = data['rev']
    if total_ticket is None:
        total_ticket = 0
    if total_revenue is None:
        total_revenue = 0

    if start_date.month != 12:
        month_end = date(start_date.year, start_date.month+1, 1) + relativedelta(days=-1)
    else:
        month_end = date(start_date.year+1, 1, 1) + relativedelta(days=-1)


    month_start = start_date
    month_data = []
    query = 'SELECT travel_class, count(ID) as num, sum(sold_price) as profit FROM ticket where airline=%s and date <= %s and date >= %s GROUP BY travel_class'

    total_num_class = [0, 0, 0, 0]
    total_rev_class = [0, 0, 0, 0]
    while month_end < end_date:
        # get this month cost
        month = month_start.strftime("%B")

        cursor.execute(query, (airline, month_end, month_start))
        nums = cursor.fetchall()
        print(nums)
        single_month_num = [0,0,0,0]
        single_month_rev = [0,0,0,0]

        for item in nums:
            if item['travel_class'] == "Economy":
                single_month_num[0] = item['num']
                single_month_rev[0] = item['profit']
                total_num_class[0] += item['num']
                total_rev_class[0] += item['profit']
            elif item['travel_class'] == "Business":
                single_month_num[1] = item['num']
                single_month_rev[1] = item['profit']
                total_num_class[1] += item['num']
                total_rev_class[1] += item['profit']
            elif item['travel_class'] == "First":
                single_month_num[2] = item['num']
                single_month_rev[2] = item['profit']
                total_num_class[2] += item['num']
                total_rev_class[2] += item['profit']
            single_month_num[3] += item['num']
            single_month_rev[3] += item['profit']
            total_num_class[3] += item['num']
            total_rev_class[3] += item['profit']
        month_data.append((month, single_month_num, single_month_rev))
        month_start = month_end + relativedelta(days=+1)
        month_end = month_start + relativedelta(months=+1) + relativedelta(days=-1)

    # get month_start to end_date
    month = month_start.strftime("%B")
    cursor.execute(query, (airline, end_date, month_start))
    nums = cursor.fetchall()
    single_month_num = [0, 0, 0, 0]
    single_month_rev = [0, 0, 0, 0]
    for item in nums:
        if item['travel_class'] == "Economy":
            single_month_num[0] = item['num']
            single_month_rev[0] = item['profit']
            total_num_class[0] += item['num']
            total_rev_class[0] += item['profit']
        elif item['travel_class'] == "Business":
            single_month_num[1] = item['num']
            single_month_rev[1] = item['profit']
            total_num_class[1] += item['num']
            total_rev_class[1] += item['profit']
        elif item['travel_class'] == "First":
            single_month_num[2] = item['num']
            single_month_rev[2] = item['profit']
            total_num_class[2] += item['num']
            total_rev_class[2] += item['profit']
        single_month_num[3] += item['num']
        single_month_rev[3] += item['profit']
        total_num_class[3] += item['num']
        total_rev_class[3] += item['profit']
    month_data.append((month, single_month_num, single_month_rev))
    month_data.append(("Total", total_num_class, total_rev_class))

    # destination
    today = datetime.today().date()
    three_month_ago = today + relativedelta(months=-3)
    year_ago = today + relativedelta(years=-1)
    dest = []
    query = 'SELECT arr_airport, count(ID) as num FROM ticket NATURAL JOIN flight WHERE airline=%s and date>=%s and date <=%s GROUP BY arr_airport ORDER BY num DESC'
    cursor.execute(query, (airline, three_month_ago, today))
    dest.append(cursor.fetchmany(3))

    cursor.execute(query, (airline, year_ago, today))
    dest.append(cursor.fetchmany(3))

    cursor.close()
    return render_template('internal/revenue_stat.html', total_ticket=total_ticket, total_revenue=total_revenue,
                           start_date=start_date, end_date=end_date, month_num=month_data, dest=dest)










