
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


@main.route("/admin/manage_game")
@roles_required('Admin')
@login_required
def manage_game():
    """
    Manage the state of the game. 
    Ideally: start, stop, restart
    """
    current_session = db.session.query(GameSessions).get(1)
    game_state = current_session.state


    return render_template("admin/manage_game.html", game_state=game_state)


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

    def get_user(user_id: int):
        return Users.query.get(user_id)

    return render_template("admin/manage_sessions.html",
                           sessions=sessions,
                           get_user=get_user)


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
    # try:
    #     session_id = request.form['session_id']
    #     print(session_id)
    #     session = GameSessions.query.get(session_id)
    #     db.session.delete(session)
    #     db.session.commit()
    #     flash("Session removed!", 'success')
    # except Exception as e:
    #     print("Error: %s" % e)
    #     flash("Failed to remove session", 'error')
    return redirect(url_for('main.manage_sessions'))


@main.route("/dashboard")
@login_required
def dashboard():
    """
    Dashboard
    """
    # session_ids = Registrations.get_sessions_by_user(user_id=current_user.id)
    sessions = current_user.game_sessions
    # sessions = [
    #     db.session.query(GameSessions).get(session_id)
    #     for session_id in list(set(session_ids))
    # ]

    return render_template("main/dashboard.html", sessions=sessions)


@main.route("/mitigations")
@login_required
def mitigations():
    """
    Users can view and apply mitigations from this page
    Mitigations are submitted as a list to updateDenyList endpoint
    """
    return render_template("main/mitigations.html")


@main.route("/getDenyList", methods=['GET'])
@login_required
def get_deny_list():
    """
    Query database for team mitigations
    Return mitigations in list format
    """
    return jsonify(current_user.team._mitigations)


@main.route("/updateDenyList", methods=['POST'])
@login_required
def update_deny_list():
    """
    POST request from mitigations page on click
    Take a list of indicators from the view
    Update the user's _mitigations attribute to reflect
    Mitigations are stored as a strigified list
    Must be json loaded after being retrieved
    """
    try:
        deny_list = request.form['dlist']
        mitigations = deny_list.split("\n")
        mitigations = [x for x in mitigations if x]
        current_user.team._mitigations = json.dumps(mitigations)

        # update the teams score
        # check if any new indicators are tagged as malicious
        # # award point for malicious indicators found
        # for indicator in mitigations:
        #     current_user.team.score += 100

        print(current_user.team.score)

        db.session.commit()
        return jsonify(success=current_user.team._mitigations)
    except Exception as e:
        print(e)
        return jsonify(success=False)


@main.route("/updatePermissions", methods=['POST'])
@roles_required('Admin')
@login_required
def update_permissions():
    """
    POST request from mitigations page on click
    Take a list of indicators from the view
    Update the user's _mitigations attribute to reflect
    Mitigations are stored as a strigified list
    Must be json loaded after being retrieved
    """
    try:
        permissions_list = request.form['plist']
        log_uploader = LogUploader()
        user_strings = [x for x in permissions_list.split("\n") if x]
        for user_string in user_strings:
                log_uploader.add_user_permissions(user_string)
        return jsonify(success=True)
    except Exception as e:
        print(e)
        flash("Error updating ADX Permissions: ","error")
        return jsonify(success=False)


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
@main.route("/challenges/<int:game_session_id>")
@login_required
def challenges(game_session_id=None):
    game_session = GameSessions.query.get(game_session_id) or abort(404)
    if current_user.id not in game_session.registrants:
        abort(404)

    challenges = Challenges.query.filter_by(game_session=game_session).all()
    solves = Solves.query.all()
    users = Users.query.all()

    return render_template("main/challenges.html", 
                            challenges=challenges, 
                            solves=solves, 
                            users=users,
                            game_session = game_session)


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
@roles_required('Admin')
def create_challenge():
    name =  request.form['challenge_name']
    value = request.form['value']
    description = request.form['description']
    answer = request.form['answer']
    category = request.form['answer'] or None
    game_session_id = request.form['game_session_id'] 

    #get game session object
    game_session = db.session.query(GameSessions).get(game_session_id)

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

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/addchallengebulk', methods=['POST'])
@login_required
@roles_required('Admin')
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
                if row[0].lower() == "name":
                    # this is the header
                    continue
                name = row[0]
                print(row)
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
    else:
        flash("Not a valid file format. Only CSV files are allowed.", "error")
    db.session.commit()
    flash(f"Added new challenges from csv", "success")

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


@main.route('/editchallenge', methods=['POST', 'GET'])
@login_required
@roles_required('Admin')
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
    challenge = db.session.query(Challenges).get(challenge_id)
    
    print(challenge.solvers)
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

    return redirect(url_for('main.challenges', game_session_id=game_session_id))


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
        session = GameSessions(state=True, name=session_name, password=password)
        db.session.add(session)
        db.session.commit()
        flash("Added a new session", 'success')
    except Exception as e:
        print('Failed to create session.', e)
        flash("Could not create this Session", 'error')
    return redirect(url_for('main.manage_sessions'))

