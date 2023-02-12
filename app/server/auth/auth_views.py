
import io
import csv

# Import flask dependencies
from flask import Blueprint, request, render_template, \
                  flash, g, session, redirect, url_for
from flask_login import login_user, logout_user , current_user , \
     login_required
from werkzeug.utils import secure_filename



from app.server.models import *
from app.server.auth.forms import EmailForm, PasswordForm
from app.server.utils import *
from flask import current_app
from app.server.security import ts
from flask_mail import Message
from app import mail


# Define the blueprint: 'auth', set its url prefix: app.url/auth
auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('auth/login.html')

    username = request.form['username']
    password = request.form['password']
    remember_me = False
    if 'remember_me' in request.form:
        remember_me = True
    registered_user = Users.query.filter_by(username=username).first()
    # if the username or password is invalid
    if (registered_user is not None) and (registered_user.check_password(password)):
        login_user(registered_user, remember=remember_me)
        flash('Logged in successfully', 'success')
        return redirect(request.args.get('next') or url_for('main.home'))
    else:
        flash('Username or Password is invalid', 'error')
    return redirect(url_for('auth.login'))



@auth.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.home'))

@auth.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if request.method == 'GET':
        return render_template('auth/edit_user.html' )

    #else method is POST, so handle the form
    username =  request.form['username']
    email =  request.form['email']
    current_user.username = username
    current_user.email = email

    try:
        db.session.add(current_user)
        db.session.commit()
        flash("User details were updated", "success")
    except:
        flash("Hmm we can't seem to update your user details. Try again", "error")

    return redirect(url_for('auth.edit_profile'))


@auth.route('/register', methods=['GET', 'POST'])
def register(username:str=None, password:str=None, email:str=None, team_id:int=None, via_gui=True):
    if request.method == 'GET':
        teams = Team.query.filter(Team.name!="admins").all()
        return render_template('auth/register.html', teams=teams)

    username = username or request.form['username']
    password = password or request.form['password']
    email = email or request.form['email']
    team_id = team_id or request.form['team_id']

    username_exists, email_exists = False, False
    try:
        username_exists = Users.query.filter_by(username=username).first()
        email_exists = Users.query.filter_by(email=email).first()
    except:
        pass

    if username_exists or email_exists:
        flash("Sorry, an account with this username or email already exists", "error")
        print(username, email)
    else:
        try:
            print("team id is %s" % team_id)
            team = Team.query.get(team_id)
            user = Users(username,
                        password,
                        email,
                        team=team)
            db.session.add(user)
            db.session.commit()
            flash('User successfully registered', "success")
            #html = render_template('email/basic.html',
            #                       username=username)
            #send_email("Welcome to the attendance app!", email, html)
        except Exception as e:
            print(f"failed to create user {username}: {e}")
            flash("Oops, something went wrong in creating your account" , "error")

    if via_gui:
        return redirect(url_for('auth.login'))

@auth.route('/bulkuserregistration', methods=['GET', 'POST'])
def create_users_from_file():
    """take values from csv and call register function to register them"""
    pass
    file = request.files['file']
    team_id = request.form['team_id']

    # Check if the file is one of the allowed types/extensions
    if file and ".csv" in file.filename:   ### make this better
        # Make the filename safe, remove unsupported chars
        filename = secure_filename(file.filename)
        with io.TextIOWrapper(request.files["file"], encoding="utf-8", newline='\n') as text_file:
            reader = csv.reader(text_file, delimiter=';')                
            for row in reader:
                if isinstance(row, list):
                    row = row[0].split(",")
                if row[0].lower() == "username".lower():
                    # this is the header
                    continue

                username = row[0]
                password = row[1]
                email = row[2] or f"{username}@email.com" #hack so we don't always have to provide an email addr
                register(username=username, password=password, email=email, team_id=team_id, via_gui=False)
                flash('Users successfully registered', "success")
    else:
        print("this ain't no csv")

    return redirect(url_for('main.manage_users'))



@auth.route('/reset', methods=["GET", "POST"])
def reset():
    if request.method == 'GET':
        return render_template("auth/reset.html")

    form = EmailForm()
    try:
        user = Users.query.filter_by(email=form.email.data).first_or_404()
    except Exception as e:
        print(e)
        flash('No such user', "error")
        return redirect(url_for('auth.reset'))

    subject = "Password reset requested"
    print(subject)

    # Here we use the URLSafeTimedSerializer we created in `util` at the
    # beginning of the chapter
    token = ts.dumps(user.email, salt='recover-key')

    recover_url = url_for(
        'auth.reset_with_token',
        token=token,
        _external=True)

    html = render_template(
        'auth/recover.html',
        recover_url=recover_url)

    # send_email is defined in myapp/util.py
    send_email(subject=subject, recipient=user.email, template=html)
    flash('Check your email for a password reset link. Email might be in your SPAM folder.', "success")

    return redirect(url_for('auth.login'))

    # return render_template('auth/reset.html', form=form)


@auth.route('/reset/<token>', methods=["GET", "POST"])
def reset_with_token(token):
    try:
        email = ts.loads(token, salt="recover-key", max_age=86400)
    except:
        abort(404)

    form = PasswordForm()

    if form.validate_on_submit():
        user = Users.query.filter_by(email=email).first_or_404()

        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()
        flash("Password reset successfully", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_with_token.html', form=form, token=token)


@auth.route('/reset_password', methods=["POST"])
def reset_password():
    current_password = request.form["current_password"]
    new_password = request.form["new_password"]

    if current_user.check_password(current_password):
        current_user.set_password(new_password)
        db.session.add(current_user)
        db.session.commit()
        flash("You password has been updated", "success")
    else:
        flash("You did not provide the correct password, try again.", "error")

    return redirect(url_for('auth.edit_profile'))



# project/email.py  
def send_email(subject, recipient, template): 
    print("sending mail...")
    msg = Message( 
            subject, 
            recipients=[recipient], 
            html=template, 
            sender='kc7cyber@gmail.com'
        ) 

    mail.send(msg)
    print("mail sent... theoretically...")
    # print(help(mail))

    
