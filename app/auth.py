from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Grade
from werkzeug.security import check_password_hash
from datetime import datetime

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user)

        # Migrate guest grades from session into DB
        guest_grades = session.pop('guest_grades', [])
        for g in guest_grades:
            existing = Grade.query.filter_by(user_id=user.id, subject=g['subject'], date=datetime.fromisoformat(g['date'])).first()
            if not existing:
                new_grade = Grade(
                    subject=g['subject'],
                    grade=g['grade'],
                    letter=g['letter'],
                    date=datetime.fromisoformat(g['date']),
                    user_id=user.id
                )
                db.session.add(new_grade)
        db.session.commit()

        flash('Logged in successfully!', 'success')
        return redirect(url_for('main.index'))

    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('main.index'))
