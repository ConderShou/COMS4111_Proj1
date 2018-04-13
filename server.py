#!/usr/bin/env python2.7

"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver

To run locally:

    python server.py

Go to http://localhost:8111 in your browser.

A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, flash, request, session, render_template, g, redirect, Response, url_for

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@35.227.79.146/proj1part2
#
# For example, if you had username gravano and password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://gravano:foobar@35.227.79.146/proj1part2"
#
DATABASEURI = "postgresql://cs3544:4651@35.227.79.146/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
# engine.execute("""CREATE TABLE IF NOT EXISTS test (
#   id serial,
#   name text
# );""")
# engine.execute("""INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace');""")


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request.

  The variable g is globally accessible.
  """
  try:
    g.conn = engine.connect()
    print("Connected to database.")
  except:
    print("uh oh, problem connecting to database")
    import traceback; traceback.print_exc()
    g.conn = None


@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't, the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#

@app.route('/')
def index():
  """
  request is a special object that Flask provides to access web request information:

  request.method:   "GET" or "POST"
  request.form:     if the browser submitted a form, this contains the data in the form
  request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

  See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
  """

  logged_in = {}
  logged_in["color"] = "primary"
  logged_in["msg"] = "Log In"

  loggedIn = False
  if "logged_in" in session:
    logged_in["color"] = "success"
    logged_in["msg"] = "Logged In: %s" % session["uni"]
    loggedIn = True
  

  # ORDER BY day, month, year ASC (once Alex update info in table)
  #
  queryImageUrls = "SELECT image_url, id, age_limit FROM events ORDER BY year, month, day" 

  cursor = g.conn.execute(queryImageUrls)

  image_urls = []
  for result in cursor:
    event = {}
    event['image_url'] = result['image_url']
    event['id'] = result['id']

    image_urls.append(event) 

  cursor.close()
  # Adding events that the user can attend for later viewing
  if (loggedIn and ("age" in session) and (session["checked_attend"] == False)):
    query = "SELECT image_url, id, age_limit FROM events E WHERE E.age_limit <= %d" % session["age"]
    cursor = g.conn.execute(query)

    for result in cursor:
      query = "INSERT INTO can_attend(id, uni) VALUES (%d, '%s')" % (result.id, session["uni"])
      try:
        g.conn.execute(query)
      except:
        pass
    session["checked_attend"] = True

    cursor.close()

  context = dict(data = image_urls, logged_in = logged_in)
  return render_template("index.html", **context)


@app.route('/event/<int:event_id>')
def show_event(event_id):
  queryEvent = "SELECT * FROM events E WHERE E.id = '%d'" % int(event_id)
  cursor = g.conn.execute(queryEvent)

  # QUERIED FOR PRIMARY EVENT INFO
  
  event = cursor.fetchone()

  # QUERYING FOR INTEREST 
  
  # Check if user is logged in, if so execute query for checking if user is interested in event
  interested = {}
  interested["color"] = "secondary"
  interested["msg"] = "Not Interested"

  can_attend = "Not logged in"

  if "logged_in" in session:

    # Check if user has already indicated interest in this event
    #   Get uni from global storage

    uni = session["uni"]

    query = "SELECT * FROM interested_in II WHERE (II.uni LIKE '%s') AND (II.id = %d)" % (uni, event_id)

    cursor = g.conn.execute(query)

    interest = cursor.fetchone()

    if interest is not None:
      interested["color"] = "info"
      interested["msg"] = "Interested"


    # QUERYING IF CAN ATTEND
    query = "SELECT COUNT(*) AS count_rows FROM can_attend CA WHERE (CA.uni LIKE '%s') AND (CA.id = %d)" % (uni, event_id)
    cursor = g.conn.execute(query)
    count = cursor.fetchone()
    print("COUNT ROWS: ", count, count.count_rows)

    can_attend = "True" if int(count.count_rows) else "False"

  cursor.close()

  context = dict(event = event, interested = interested, can_attend = can_attend)
  return render_template("event.html", **context)


@app.route('/addInterested/<int:event_id>/<can_attend>')
def add_interested(event_id, can_attend):

  if "logged_in" not in session:
    flash("Not logged in", "danger")
    return redirect(url_for('show_event', event_id=event_id))
  elif can_attend == "False":
    flash("Can only show interest if you're able to attend", "danger")
    return redirect(url_for('show_event', event_id=event_id))

  uni = session["uni"]

  query = "INSERT INTO interested_in(id, uni) VALUES (%d, '%s')" % (event_id, uni)

  try:
    g.conn.execute(query)
    flash("Added event as interested", "success")
    query = "UPDATE events SET num_interested = num_interested + 1 WHERE events.id = %d" % event_id
    g.conn.execute(query)
  except:
    query = "DELETE FROM interested_in II WHERE (II.uni LIKE '%s') AND (II.id = %d)" % (uni, event_id)
    g.conn.execute(query)
    flash("Event removed from interested", "danger")
    query = "UPDATE events SET num_interested = num_interested - 1 WHERE events.id = %d" % event_id
    g.conn.execute(query) 

  return redirect(url_for('show_event', event_id=event_id))

@app.route('/interested')
def show_interested():
  if "logged_in" not in session:
    flash("Not logged in", "danger")
    return redirect(url_for('index'))

  query = "SELECT id, image_url FROM (interested_in NATURAL JOIN events) AS IE WHERE IE.uni LIKE '%s'" % session["uni"]
  cursor = g.conn.execute(query)

  image_urls = []
  for result in cursor:
    event = {}
    event['image_url'] = result['image_url']
    event['id'] = result['id']

    image_urls.append(event) 

  context = dict(data = image_urls)
  return render_template("interested.html", **context)

@app.route('/recommended')
def show_recommended():
  if "logged_in" not in session:
    flash("Not logged in", "danger")
    return redirect(url_for('index'))

  uni = session["uni"]
  query = "SELECT image_url, id, type FROM events E WHERE (E.type IN (SELECT (type) FROM (interested_in NATURAL JOIN events) AS IE WHERE (IE.uni LIKE '%s')) AND (E.id NOT IN (SELECT (id) FROM (interested_in NATURAL JOIN events) AS IE WHERE (IE.uni LIKE '%s'))));" % (uni, uni)

  cursor = g.conn.execute(query)

  image_urls = []
  types = set()
  for result in cursor:
    event = {}
    event['image_url'] = result['image_url']
    event['id'] = result['id']

    image_urls.append(event) 
    types.add(result["type"])

  context = dict(data = image_urls, types = types)
  return render_template("recommended.html", **context)

@app.route('/filter')
def filter():
  
  # Get all building names currently used
  query = "SELECT building_name FROM locations" #CONFIRM THIS IS CORRECT

  cursor = g.conn.execute(query)

  bnames = []
  for result in cursor:
    bnames.append(result.building_name)

  cursor.close()
  context = dict(bnames = bnames)
  return render_template("filter.html", **context)


@app.route('/filter/results', methods=['POST'])
def filter_results():
  print("REQUEST: ", request.form)

  location = request.form['location']

  month = request.form['month']
  day = request.form['day']
  year = request.form['year']

  start_upper = request.form['start-upper']
  start_lower = request.form['start-lower']

  end_upper = request.form['end-upper']
  end_lower = request.form['end-lower']

  # Query for events with corresopnding attributes  
  

  cursor.close()
  context = dict(data = {})
  return render_template('filter-results.html', **context)


@app.route('/login')
def login():
  if "logged_in" in session:
    del session["logged_in"]
    return redirect(url_for('index'))

  return render_template("login.html")


@app.route('/user', methods=['POST'])
def user():
  uni = request.form['uni']

  query = "SELECT uni, age FROM users U WHERE U.uni LIKE '%s'" % str(uni)
  cursor = g.conn.execute(query)

  # Check if cursor is pointing to a record
  user = cursor.fetchone()

  if (user is None):
    flash("User Not Found", "danger")
    return redirect('/new/user')

  session["logged_in"] = True
  session["uni"] = user.uni
  session["age"] = user.age
  session["checked_attend"] = False

  flash("Successfully logged in", "success")

  cursor.close()
  return redirect('/')


@app.route('/new/user')
def new_user():
  return render_template('new_user.html')


@app.route('/create/user', methods=['POST'])
def create_user():

  uni = str(request.form['uni'])
  school = str(request.form['school'])
  age = int(request.form['age']) 

  query = "INSERT INTO users(uni, school, age) VALUES ('%s', '%s', %d)" % (uni, school, age)

  g.conn.execute(query)

  return redirect('/login')



app.secret_key = 'a mysterious key unbeknowst to man'

if __name__ == "__main__":
  import click

  @click.command()
  @click.option('--debug', is_flag=True)
  @click.option('--threaded', is_flag=True)
  @click.argument('HOST', default='0.0.0.0')
  @click.argument('PORT', default=8111, type=int)
  def run(debug, threaded, host, port):
    """
    This function handles command line parameters.
    Run the server using:

        python server.py

    Show the help text using:

        python server.py --help

    """

    HOST, PORT = host, port
    print("running on %s:%d" % (HOST, PORT))
    app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


  run()
