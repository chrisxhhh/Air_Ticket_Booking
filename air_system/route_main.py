from flask import render_template, request, session, redirect, url_for, g, flash
from air_system import db_conn, app
from air_system.auth import customer_login_required
from air_system.utility import process_time
from datetime import datetime, timedelta, date
from dateutil.relativedelta import *
import math

@app.route('/')
def hello():
    if g.type:
        if g.type == "staff":
            return redirect(url_for('internal.main_control'))
        name = session['username']
        # print(username)
        return render_template('index.html', login=True, username=name)
    else:
        return render_template('index.html', login=False)


@app.route('/search', methods=["POST", "GET"])
def search():
    if request.method == "GET":
        return render_template('search.html')
    depart_place = request.form['from']
    arr_place = request.form['to']
    depart_date = request.form['departureDate']
    if datetime.strptime(depart_date, "%Y-%m-%d" ).date() < datetime.today().date():
        flash('departure date can only be in future')
        return redirect(url_for('search'))
    if 'returnDate' in request.form:
        round_trip = True
        return_date = request.form['returnDate']
        if datetime.strptime(return_date, "%Y-%m-%d").date() < datetime.strptime(depart_date, "%Y-%m-%d" ).date():
            flash("return date must be after departure date")
            return redirect(url_for('search'))
    else:
        round_trip = False

    cursor = db_conn.cursor()
    query = 'SELECT * FROM flight WHERE dept_airport = %s and arr_airport = %s and dept_date= %s'
    cursor.execute(query, (depart_place, arr_place, depart_date))
    depart_data = cursor.fetchall()

    i = 0
    session['search_res'] = []
    if depart_data:

        for item in depart_data:
            item['dept_date'] = str(item['dept_date'])
            item['dept_time'] = process_time(item['dept_time'])

            item['arr_date'] = str(item['arr_date'])
            item['arr_time'] = process_time(item['arr_time'])


            item['base_price'] = int(item['base_price'])
            item['search_order'] = i
            session['search_res'].append(item)
            i += 1

    return_data = None
    if round_trip:
        cursor.execute(query, (arr_place, depart_place, return_date))
        return_data = cursor.fetchall()

        if return_data:

            for item in return_data:

                item['dept_date'] = str(item['dept_date'])
                item['dept_time'] = process_time(item['dept_time'])

                item['arr_date'] = str(item['arr_date'])
                item['arr_time'] = process_time(item['arr_time'])

                item['base_price'] = int(item['base_price'])
                item['search_order'] = i
                session['search_res'].append(item)
                i += 1


    cursor.close()
    return render_template('result.html', depart_data=depart_data, return_data=return_data)


@app.route('/search/buy-<num>', methods=["POST","GET"])
@customer_login_required
def buy(num):
    flight = session['search_res'][int(num)]
    cursor = db_conn.cursor()
    query = 'SELECT num_seat FROM airplane WHERE airline = %s and ID = %s'
    cursor.execute(query, (flight['airplane_airline'], flight['airplane_id']))
    max_capacity = cursor.fetchone()
    max_capacity = max_capacity['num_seat']

    query = 'SELECT travel_class, COUNT(ID) as num FROM ticket WHERE airline = %s and flight_num = %s and dept_time = %s ' \
            'and dept_date = %s GROUP BY travel_class'
    cursor.execute(query, (flight['airline'], flight['flight_num'], flight['dept_time'], flight['dept_date']))
    tickets = cursor.fetchall()
    sold_ticket = [0, 0, 0]

    for ticket in tickets:
        if ticket["travel_class"] == "Economy":
            sold_ticket[0] = ticket['num']
        elif ticket["travel_class"] == "Business":
            sold_ticket[1] = ticket['num']
        else:
            sold_ticket[2] = ticket['num']

    max_cap = [
        math.floor(max_capacity * 0.85),
        math.floor(max_capacity * 0.1),
        max_capacity - math.floor(max_capacity * 0.85) - math.floor(max_capacity * 0.1)
    ]
    flight['capacity_class'] = [
        str(sold_ticket[0]) + ' / ' + str(max_cap[0]),
        str(sold_ticket[1]) + ' / ' + str(max_cap[1]),
        str(sold_ticket[2]) + ' / ' + str(max_cap[2])
    ]

    flight['price'] = [
        math.floor(flight['base_price'] if sold_ticket[0] < max_cap[0]*0.75 else flight['base_price']*1.25),
        math.floor(flight['base_price']*2 if sold_ticket[1] < max_cap[1]*0.75 else flight['base_price']*2*1.25),
        math.floor(flight['base_price']*3 if sold_ticket[2] < max_cap[2]*0.75 else flight['base_price']*3*1.25)
    ]

    flight['can_buy'] = []
    if sold_ticket[0] < max_cap[0]:
        flight['can_buy'].append("Economy")
    if sold_ticket[1] < max_cap[1]:
        flight['can_buy'].append("Business")
    if sold_ticket[2] < max_cap[2]:
        flight['can_buy'].append("First")
    if request.method == "GET":
        return render_template("customer/buy.html", item=flight)
    elif request.method == "POST":
        airline = flight['airline']
        flight_num = flight['flight_num']
        dept_date = flight['dept_date']
        dept_time = flight['dept_time']
        travel_class = request.form['class']
        card_type = request.form['card_type']
        card_num = request.form['card_num']
        name_on_card = request.form['name_on_card']
        expir_date = request.form['month'] + '/' + request.form['year']
        email = g.user_email
        date = datetime.today().date()
        time = datetime.today().time()
        if travel_class == "Economy":
            sold_price = flight['price'][0]
        elif travel_class == "Business":
            sold_price = flight['price'][1]
        else:
            sold_price = flight['price'][2]

        if int(request.form['month']) > 12 or int(request.form['month']) < 1:
            flash("purchase failed, month need to be within 1 to 12")
            return render_template("customer/buy.html", item=flight)

        cursor = db_conn.cursor()
        action = 'INSERT INTO ticket(airline, flight_num, dept_date, dept_time, travel_class, card_type, card_num, ' \
                 'name_on_card, expir_date, date, time, email, sold_price) VALUE(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(action, (airline, flight_num, dept_date, dept_time, travel_class, card_type, card_num,
                                name_on_card, expir_date, date, time, email, sold_price))
        db_conn.commit()
        cursor.close()
        flash("purchase complete!")
        return redirect(url_for('buy', num=num))



@app.route("/my_flight", methods=["POST", "GET"])
@customer_login_required
def my_flight():
    cursor = db_conn.cursor()

    if request.method == "POST":
        ID = request.form['ID']

        query = 'SELECT dept_date, dept_time FROM ticket WHERE ID=%s'
        cursor.execute(query,(ID))
        data= cursor.fetchone()
        print(data)
        dept_time = data['dept_time']
        dept_date = data['dept_date']
        dept = str(dept_date) +' '+ str(dept_time)

        #if datetime.today()
        dept = datetime.strptime(dept, '%Y-%m-%d %H:%M:%S')
        if dept - datetime.today() < timedelta(days=1):
            flash('Unable to cancel a ticket within 24 hours')
            return redirect(url_for('my_flight'))
        action = 'DELETE FROM ticket WHERE ID=%s'
        cursor.execute(action, (ID))
        db_conn.commit()
        flash('The ticket deleted successfully')
        return redirect(url_for('my_flight'))

    email = g.user_email
    today = datetime.today().date()

    query = 'SELECT * FROM ticket NATURAL JOIN flight WHERE email=%s and dept_date >= %s ORDER BY dept_date, dept_time'
    cursor.execute(query, (email, str(today)))
    future_tickets = cursor.fetchall()



    query = 'SELECT * FROM ticket NATURAL JOIN flight WHERE email=%s and dept_date < %s ORDER BY dept_date, dept_time'
    cursor.execute(query, (email, str(today)))
    history_tickets = cursor.fetchall()


    cursor.close()
    return render_template("customer/my_flight.html", future_tickets=future_tickets, history_tickets=history_tickets)




@app.route('/comment-<ID>', methods=['GET', 'POST'])
@customer_login_required
def comment(ID):
    cursor = db_conn.cursor()
    query = 'SELECT email FROM ticket WHERE ID=%s'
    cursor.execute(query, ID)
    email = cursor.fetchone()['email']

    if g.user_email != email:
        cursor.close()
        flash('you can only comment on your own tickets!')
        return redirect(url_for('hello'))

    if request.method == 'POST':
        rate = request.form['rate']
        comment = request.form['comment']
        action = 'UPDATE ticket SET rate=%s, comment=%s where ID=%s'
        cursor.execute(action, (rate, comment, ID))
        db_conn.commit()
        flash("Comment successfully")
        return redirect(url_for('comment', ID=ID))

    query = 'SELECT * FROM ticket WHERE ID=%s'
    cursor.execute(query, ID)
    ticket = cursor.fetchone()
    rate= ticket['rate']
    comment = ticket['comment']
    cursor.close()
    return render_template('customer/comment.html', rate=rate, comment=comment)


@app.route('/stat')
@customer_login_required
def customer_stat():

        email = g.user_email
        if not request.args.get('start_date'):
            print('yes')
            end_date = datetime.today().date()
            start_date = end_date+relativedelta(months=-6)
        else:
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start_date > datetime.today().date() or start_date > end_date:
                flash('error: please enter valid dates')
                return redirect(url_for('customer_stat'))

        cursor = db_conn.cursor()
        query = 'SELECT SUM(sold_price) as cost FROM ticket where email=%s and date <=%s and date >= %s'
        cursor.execute(query,(email, end_date, start_date))
        total_cost = cursor.fetchone()['cost']

        if total_cost is None:
            total_cost = 0

        if start_date.month != 12:
            month_end = date(start_date.year, start_date.month+1, 1) + timedelta(days=-1)

        else:
            month_end = date(start_date.year+1, 1, 1) + timedelta(days=-1)


        month_start = start_date

        month_cost = []
        while month_end < end_date:
            # get this month cost
            month = month_start.strftime("%B")
            query = 'SELECT SUM(sold_price) as cost FROM ticket where email=%s and date <=%s and date >= %s'
            cursor.execute(query, (email, month_end, month_start))
            cost = cursor.fetchone()['cost']
            if cost is None:
                cost = 0
            month_cost.append((month, cost))

            month_start = month_end+relativedelta(days=+1)
            month_end = month_start + relativedelta(months=+1) + relativedelta(days=-1)

        # get month_start to end_date
        month = month_start.strftime("%B")
        cursor.execute(query, (email, end_date, month_start))
        cost = cursor.fetchone()['cost']
        if cost is None:
            cost = 0
        month_cost.append((month, cost))






        cursor.close()
        return render_template('customer/stat_customer.html', total_cost=total_cost, month_cost=month_cost, start_date=start_date, end_date=end_date)


