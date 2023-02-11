
from email.errors import CharsetError
import json
import random
import yaml
import csv
import io
from datetime import datetime
from flask_login import login_required, current_user
from flask_security import roles_required

from flask import Blueprint, request, render_template, \
    flash, g, session, redirect, url_for, abort, current_app, jsonify
from sqlalchemy import asc
from sqlalchemy.sql.expression import func, select
from werkzeug.utils import secure_filename
from app.server.uploadLogs import LogUploader


# Import module models (i.e. Company, Employee, Actor, DNSRecord)
from app.server.models import db, Team, Users, Roles, GameSessions, Solves, Challenges, Registrations

from app.server.utils import *


# Define the blueprint: 'main', set its url prefix: app.url/
main = Blueprint('main', __name__)


@main.route("/")
def home():
    print("initialization complete...")
    return redirect(url_for('main.dashboard'))



@main.route("/admin/manage_database")
@roles_required('Admin')
@login_required
def manage_database():
    log_uploader = LogUploader()
    perms = log_uploader.get_user_permissions()
    return render_template("admin/manage_database.html", perms=perms)


@main.route("/admin/teams")
@roles_required('Admin')
@login_required
def manage_teams():
    team_list = Team.query.all()
    return render_template("admin/manage_teams.html",
                           teams=team_list)


@main.route("/admin/users")
@roles_required('Admin')
@login_required
def manage_users():
    user_list = Users.query.all()
    teams = Team.query.all()
    return render_template("admin/manage_users.html",
                           users=user_list,
                           teams=teams)

@main.route("/admin/sessions")
@roles_required('Admin')
@login_required
def manage_sessions():
    sessions = GameSessions.query.all()
    users = Users.query.all()

    def get_user(user_id: int):
        return Users.query.get(user_id)

    return render_template("admin/manage_sessions.html",
                           sessions=sessions,
                           users = users,
                           get_user=get_user)


@main.route("/toggle_admin", methods=['POST'])
@roles_required('Admin')
@login_required
def toggle_admin():
    user_id = request.form['user_id']
    is_admin = request.form.get('is_admin', 'off')
    user = Users.query.get(user_id)
    admin_role = Roles.query.filter_by(name='Admin').first()

    if user.id != current_user.id:
        if is_admin == 'on':
            user.roles.append(admin_role)
        else:
            try:
                user.roles.remove(admin_role)
            except Exception as e:
                flash("This user is not an admin")

        db.session.add(user)
        db.session.commit()
    else:
        flash("You cannot remove the admin role from yourself")

    return redirect(url_for('main.manage_users'))






@main.route("/joinsession", methods=['GET', 'POST'])
@login_required
def join_session():
    if request.method == 'GET':
        return render_template("main/join_session.html")

    session_password = request.form['session_password']
    game_session = GameSessions.query.filter_by(password=session_password).first()

    if game_session:
        # add user to session
        db.session.add(
            Registrations(game_session.id, current_user.id)
        )
        db.session.commit()
        flash(f"Added user to game session {game_session.name}", 'success')
        return redirect(url_for('main.rankings', game_session_id = game_session.id))
    else:
        flash("Sorry we couldn't register you for this game. Make sure this is a valid code and try again!", 'error')
        return redirect(url_for('main.dashboard'))

    


@main.route("/delsession", methods=['POST'])
@login_required
@roles_required('Admin')
def delete_game_session():
    session_id = request.form['session_id']
    # session = GameSessions.query.get(session_id)
    session =  db.session.query(GameSessions).get(session_id)
    db.session.delete(session)
    db.session.commit()

    return redirect(url_for('main.manage_sessions'))


@main.route("/dashboard")
@login_required
def dashboard():
    """
    Dashboard
    """
    # session_ids = Registrations.get_sessions_by_user(user_id=current_user.id)
    # sessions = current_user.game_sessions
    sessions = Users.query.get(current_user.id).game_sessions
    # sessions = [
    #     db.session.query(GameSessions).get(session_id)
    #     for session_id in list(set(session_ids))
    # ]
    return render_template("main/dashboard.html", sessions=sessions)


@login_required
@main.route('/deluser', methods=['GET', 'POST'])
def deluser():
    """
    Delete a user
    """
    try:
        user_id = request.form['user_id']
        user = db.session.query(Users).get(user_id)
        db.session.delete(user)
        db.session.commit()
        flash("User removed!", 'success')
    except Exception as e:
        print("Error: %s" % e)
        flash("Failed to remove user", 'error')
    return redirect(url_for('main.manage_users'))


@main.route("/teams")
@login_required
def teams():
    team_list = Team.query.all()
    return render_template("main/teams.html",
                           teams=team_list)



##################
# Challenge solves
#################
@main.route("/challenges/<int:game_session_id>", defaults={'category': None})
@main.route("/challenges/<int:game_session_id>/<string:category>")
@login_required
def challenges(game_session_id=None, category=None):

    game_session = GameSessions.query.get(game_session_id) or abort(404)
    if current_user.id not in game_session.registrants:
        abort(404)

    try:
        categories = (
            Challenges.query
            .filter_by(
                game_session=game_session
            ).all()
        ) 
    except Exception as e:
        print(f"got no results when trying to get categories {e}")
        categories = []

    categories = list(set([c.category for c in categories]))
    categories.sort()

    if category:
        challenges = (
            Challenges.query
            .filter_by(
                game_session=game_session,
                category=category
            ).all()
        )
        if not challenges:
            abort(404)
    elif len(categories) > 0:
        # just get stuff from the first category
        challenges = (
            Challenges.query
            .filter_by(
                game_session=game_session,
                category=categories[0]
            ).all()
        )
    else:
        challenges = (
            Challenges.query
            .filter_by(
                game_session=game_session
            ).all()
        )

    # Get all users resgistered on this session
    users = (
        db.session.query(Users)
        .join(Registrations, Registrations.user_id == Users.id)
        .filter(Registrations.game_session_id == game_session_id)
        .filter(~Users.id.in_([m.id for m in game_session.managers]))
    ).all()

    questions = load_json_from_github("questions2.json")

    

    return render_template("main/challenges.html", 
                            challenges=challenges, 
                            categories=categories,
                            current_category = category,
                            game_session = game_session,
                            users=users,
                            questions=questions)


@main.route("/rankings/<int:game_session_id>")
def rankings(game_session_id=None):
    game_session = GameSessions.query.get(game_session_id) or abort(404)
    if current_user.id not in game_session.registrants:
        abort(404)

    user_ids = GameSessions.query.get(game_session_id).registrants
    users = Users.query.filter(Users.username!="admin").filter(Users.id.in_(user_ids)).all()

    return render_template("main/rankings.html", users=users, game_session=game_session)



@main.route('/addchallenge', methods=['POST', 'GET'])
@login_required
def create_challenge():
    name =  request.form['challenge_name']
    value = request.form['value']
    description = request.form['description']
    answer = request.form['answer']
    category = request.form['category'] or None
    game_session_id = request.form['game_session_id'] 

    #get game session object
    game_session = db.session.query(GameSessions).get(game_session_id)

    if game_session.is_managed_by(current_user):      
        challenge = Challenges(
            name=name, 
            description=description, 
            answer=answer, 
            value=value, 
            category=category,
            game_session= game_session
        )
        db.session.add(challenge)
        db.session.commit()
        flash(f"Added new challenge: {challenge.name}", "success")
    else:
        flash(f"You aren't allowed to perform this action", "error")

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/clear_all_challenges', methods=['POST'])
@login_required
def clear_all_challenges():
    
    game_session_id = request.form['game_session_id'] 

    #get game session object
    game_session = db.session.query(GameSessions).get(game_session_id)
    
    if game_session.is_managed_by(current_user):  
        print("printing challenges")
        for challenge in game_session.challenges:
            db.session.delete(challenge)
        db.session.commit()
    else:
        flash("You aren't authorized to do this", "error")

    flash("Cleared all challenges", "success")
    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/addchallengebulk', methods=['POST'])
@login_required
def create_challenges_from_file():
    """Take a CSV and use it to  questions"""
    print("received a file")

    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)
    # Get the name of the uploaded file
    file = request.files['file']
    
    # Check if the file is one of the allowed types/extensions
    if file and ".csv" in file.filename:   ### make this better
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)

        # Rows are Name, Value, Description, Answer
        with io.TextIOWrapper(request.files["file"], encoding="utf-8", newline='\n') as text_file:
            reader = csv.reader(text_file, delimiter=',')                
            for row in reader:
                # if isinstance(row, list):
                #     row = row[0].split(",")
                if row[0].lower() in ["name", "Name"]:
                    # this is the header
                    continue
                try:
                    name = row[0]
                    value = row[1]
                    description = row[2]
                    answer = row[3]
                    category = row[4] or "None"

                    challenge = Challenges(
                        name=name, 
                        description=description, 
                        answer=answer, 
                        value=value, 
                        category=category,
                        game_session=game_session
                    )
                    db.session.add(challenge)
                    db.session.commit()
                except Exception as e:
                    print(f"unable to add row due to error: {e}")
                    db.session.rollback()
                    
    else:
        flash("Not a valid file format. Only CSV files are allowed.", "error")
    flash(f"Added new challenges from csv", "success")
    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/create_challenges_from_github', methods=['POST'])
@login_required
def create_challenges_from_github():
    path = request.form['json_path']
    game_session_id= request.form["game_session_id"]
    game_session = GameSessions.query.get(game_session_id)
    questions = load_json_from_github(path)
    print(questions)

    count_of_questions_added = 0
    for question in questions:
        try:
            name = question["Name"]
            description = question["Description"]
            answer = question["Answer"]
            value = question["Value"]
            category = question["Category"]
            
            
            challenge = Challenges(
                name=name, 
                description=description, 
                answer=answer, 
                value=value, 
                category=category,
                game_session=game_session
            )
            db.session.add(challenge)
            db.session.commit()
            count_of_questions_added +=1
        except Exception as e:
            flash("Failed to add questions", "error")
            print(f"unable to add row due to error: {e}")
            db.session.rollback()
    
    flash(f"Added {count_of_questions_added} new questions from github", "info")

    return redirect(url_for('main.challenges', game_session_id=game_session_id))





@main.route('/editchallenge', methods=['POST', 'GET'])
@login_required
def edit_challenge():
    """Edit all the values for a challenge"""
    # get all the values from the form
    challenge_id = request.form['challenge_id']
    name =  request.form['challenge_name']
    value = request.form['value']
    description = request.form['description']
    answer = request.form['answer']
    category = request.form['category']

    # get the game_session_id so we can redirect back to the right session
    game_session_id = request.form['game_session_id']

    # find the challenge db object using its id from the form
    challenge = db.session.query(Challenges).get(challenge_id)

    if not challenge.game_session.is_managed_by(current_user):
        # user is not authorized to do this action
        return redirect(url_for('main.challenges', game_session_id=game_session_id))

    # update all the values
    challenge.name = name
    challenge.value = value
    challenge.description = description
    challenge.answer = answer
    challenge.category = category

    # commit updates to the db
    db.session.add(challenge)
    db.session.commit()
    flash(f"Updated the challenge: {challenge.name}", "success")
    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/deletechallenge', methods=['POST', 'GET'])
@login_required
@roles_required('Admin')
def delete_challenge():
    game_session_id = request.form['game_session_id']
    try:
        challenge_id = request.form['challenge_id']
        challenge = db.session.query(Challenges).get(challenge_id)
        db.session.delete(challenge)
        db.session.commit()
        flash("Challenge removed!", 'success')
    except Exception as e:
        print("Error: %s" % e)
        flash("Failed to remove challenge", 'error')

    return redirect(url_for('main.challenges', game_session_id=game_session_id))
                           

@main.route('/solve', methods=['POST'])
@login_required
def solve_challenge():
    answer = request.form['answer']
    challenge_id = request.form['challenge_id']
    game_session_id = request.form['game_session_id']
    category = request.form['category']
    challenge = db.session.query(Challenges).get(challenge_id)

    if challenge.game_session.uses_timer and \
        challenge.game_session.end_time < datetime.now():
        flash("This session has expired. You can no longer solve challenges.", "error")
        return redirect(url_for('main.challenges', game_session_id=game_session_id))
    
    if answer.lower() in [a.lower() for a in challenge.answer.split(";")]:
        print("answer is correct")
        try:
            solve = Solves(challenge_id=challenge_id, user_id=current_user.id, username=current_user.username)
            db.session.add(solve)
            db.session.commit()
            flash("Correct", "success")
        except Exception as e:
            print(e)
            print("already solved")
            flash("Looks like you already solved this challenge", "error")
    else:
        print("incorrect answer")
        flash(f"Incorrect answer for {challenge.name}, try again", "error")

    return redirect(url_for('main.challenges', 
                        game_session_id=game_session_id,
                        category=category ))


@login_required
@main.route('/delteam', methods=['GET', 'POST'])
def delteam():
    """
    Delete a team
    """
    try:
        team_id = request.form['team_id']
        team = db.session.query(Team).get(team_id)
        db.session.delete(team)
        db.session.commit()
        flash("Team removed!", 'success')
    except Exception as e:
        print("Error: %s" % e)
        flash("Failed to remove team", 'error')
    return redirect(url_for('main.manage_teams'))


@main.route("/create_team", methods=['POST'])
@login_required
@roles_required('Admin')
def create_team():
    try:
        team_name = request.form['team_name']
        team = Team(name=team_name, score=0)
        db.session.add(team)
        db.session.commit()
    except Exception as e:
        print('Failed to create team.', e)
        flash("Could not create this team!", 'error')
    flash("Added a new team", 'success')
    return redirect(url_for('main.manage_teams'))


@main.route("/create_session", methods=['POST'])
@login_required
@roles_required('Admin')
def create_session():
    try:
        session_name = request.form['session_name']
        password = request.form['password']
        try:
            manager_id = request.form['manager_id']
            manager = Users.query.get(manager_id) or current_user
        except:
            manager = current_user

        session = GameSessions(uses_timer=False, name=session_name, password=password)
        session.managers.append(manager)
        db.session.add(session)
        db.session.commit()
        flash("Added a new session", 'success')
    except Exception as e:
        print('Failed to create session.', e)
        flash("Could not create this Session", 'error')
    return redirect(url_for('main.manage_sessions'))


@main.route("/editsession", methods=['POST'])
@login_required
def edit_session():
    session_name = request.form['session_name']
    password = request.form['session_password']
    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)

    if not game_session.is_managed_by(current_user):
        return redirect(url_for('main.challenges', game_session_id=game_session_id))
       
    try:
        game_session.name = session_name
        game_session.password = password

        db.session.add(game_session)
        db.session.commit()
        flash("Updated the session", 'success')
    except Exception as e:
        print('Failed to update session.', e)
        flash("Could not update this Session", 'error')
    return redirect(url_for('main.challenges', game_session_id=game_session_id))

@main.route("/add_session_manager", methods=['POST'])
@login_required
def add_session_manager():
    user_id = request.form['user_id']
    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)

    if not user_id:
        flash("You must select a valid user to add")
        return redirect(url_for('main.challenges', game_session_id=game_session_id))

    if not (game_session.is_managed_by(current_user) or current_user.has_role('Admin')):
        return redirect(url_for('main.challenges', game_session_id=game_session_id))

    user_to_add = Users.query.get(user_id)
    game_session.managers.append(user_to_add)
    db.session.add(game_session)
    db.session.commit()

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route("/removemanager", methods=['POST'])
@login_required
def remove_manager_from_session():
    """
    Function to remove use from a session
    This is shameful function full of hacks
    """
    user_id = request.form['user_id']
    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)

    if not (game_session.is_managed_by(current_user) or current_user.has_role('Admin')):
        return redirect(url_for('main.challenges', game_session_id=game_session_id))
    elif int(user_id) == current_user.id:
        flash("You can't remove yourself as an admin silly :P")
        return redirect(url_for('main.challenges', game_session_id=game_session_id))
    

    # .remove returns an error - probably because of class definition
    # so we are hacking the remove instead
    # yes, this code is bad and I should feel bad
    # TODO: make more elegant
    for index, user in enumerate(game_session.managers):
        if user.id == int(user_id):
            game_session.managers.pop(index)

    db.session.add(game_session)
    db.session.commit()

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route("/update_session_end_time", methods=['POST'])
@login_required
def update_session_end_time():
    end_time = request.form['end_time']
    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)

    if end_time and game_session.is_managed_by(current_user):
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
        game_session.end_time = end_time

        db.session.add(game_session)
        db.session.commit()
        flash("Updated the game time. Use the toggle above to enable the clock", "success")

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route("/enable_session_time", methods=['POST'])
@login_required
def enable_session_time():
    uses_timer = request.form.get('uses_timer', 'off')
    game_session_id = request.form['game_session_id']
    game_session = GameSessions.query.get(game_session_id)

    if uses_timer == "on":
        uses_timer = True
    else:
        uses_timer = False

    if game_session.is_managed_by(current_user):
        game_session.uses_timer = uses_timer

        db.session.add(game_session)
        db.session.commit()
        flash(f"Toggled the game timer to: {uses_timer}", "success")

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route("/api/event_setup", methods=['POST', 'GET'])
def event_setup():
    """
    API endpoint 
    this will take requests from powerautomate form
    create a new sessions and corresponding manager
    populate session will questions based on specifications
    return relevant info to be sent via email to user 
    """
    if request.method == 'GET':
        return "This is the API endpoint for KC7 events"

    if request.method == 'POST':
        request_data = request.get_json()

    # Might need to do some scrubbing on this (the event name)
    # Or allow users to edit this after they login later
    event_name = request_data.get('event_name')
    email_address = request_data.get('email_address')

    # event_type should be one of ["middle school", "high school", "college", "industry", "CTI"]
    # need to think hard about what event type will be made available
    event_type = request_data.get('event_type')

    # this keeps us from getting spammed
    # cross check value should be stored in the config
    auth_code = request_data.get('auth_code')

    # make sure all values were supplied
    if event_name and event_type and auth_code == "THISISASECRETVALUE":
        pass
    else:
        return "Invalid request"

    ## Create the admin for the new session
    default_team = Team.query.filter_by(name='default').first()
    admin_password = generate_password(length=10)
    session_admin = Users(
        username=email_address,
        email=email_address,
        password= admin_password,
        team=default_team
    )

    db.session.add(session_admin)
    db.session.commit()

    # Now create the session
    session_password = generate_password(length=6)
    session = GameSessions(
        uses_timer=False, 
        name=event_name, 
        password=session_password
    )
    session.managers.append(session_admin)
    db.session.add(session)
    db.session.commit()


    db.session.add(
            Registrations(session.id, session_admin.id)
        )
    db.session.commit()


    #Finally return the relevant info
    return jsonify({
        "event_name": event_name,
        "admin_username": session_admin.username,
        "admin_password": admin_password,
        "session_password": session_password
    })

