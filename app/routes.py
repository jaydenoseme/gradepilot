from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db, csrf, is_admin
from app.models import User, Grade, CustomGPA, UserSettings, Semester, UserActivity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from app.forms import GradeForm, DeleteForm, LoginForm, SignupForm, GpaScaleForm, SettingsForm, SemesterForm
from flask_wtf.csrf import CSRFProtect

main = Blueprint('main', __name__)
"""
def log_event(action):
    event = Event(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action
    )
    db.session.add(event)
    db.session.commit()
"""

LETTER_TO_NUM = {
    'A+': 98, 'A': 95, 'A-': 91,
    'B+': 88, 'B': 85, 'B-': 81,
    'C+': 78, 'C': 75, 'C-': 71,
    'D': 65, 'F': 50
}

# GPA scales mapping with numeric cutoff and GPA points for unweighted and weighted (Honors/AP)
GPA_SCALES = {
    'standard': {  # 4.0 unweighted, no weighting here (weighting is done separately)
        'cutoffs': [(90, 4.0), (80, 3.0), (70, 2.0), (60, 1.0)],
        'weight': {'Regular': 0.0, 'Honors': 0.5, 'AP': 1.0},
        'max': 5.0
    },
    'weighted_5': {
        'cutoffs': [(90, 5.0), (80, 4.0), (70, 3.0), (60, 2.0)],
        'weight': {'Regular': 0.0, 'Honors': 0.0, 'AP': 0.0},  # weights incorporated in scale directly
        'max': 5.0
    },
    'weighted_4.5': {
        'cutoffs': [(90, 4.5), (80, 3.5), (70, 2.5), (60, 1.5)],
        'weight': {'Regular': 0.0, 'Honors': 0.25, 'AP': 0.5},
        'max': 5.0
    },
    'college_plus_minus': {  # Similar to precise 4.33 scale with +/- plus no weighting
        'cutoffs': [
            (93, 4.0), (90, 3.7), (87, 3.3), (83, 3.0),
            (80, 2.7), (77, 2.3), (73, 2.0), (70, 1.7),
            (67, 1.3), (65, 1.0)
        ],
        'weight': {'Regular': 0.0, 'Honors': 0.0, 'AP': 0.0},
        'max': 4.0
    }
}

def grade_to_gpa_points(grade_numeric, course_type, scale_key):
    # Ensure grade_numeric is a float
    try:
        grade_numeric = float(grade_numeric)
    except (ValueError, TypeError):
        # Could not convert; return None or 0 GPA points
        return 0.0

    scale = GPA_SCALES.get(scale_key, GPA_SCALES['standard'])
    cutoffs = scale['cutoffs']
    weight_map = scale['weight']
    max_gpa = scale['max']

    # Find base GPA points based on cutoffs
    points = 0.0
    for cutoff, gpa_value in cutoffs:
        if grade_numeric >= cutoff:
            points = gpa_value
            break

    # Add weighting if scale supports it
    weight = weight_map.get(course_type, 0.0)
    weighted_points = points + weight

    # Cap GPA at max scale value
    return min(weighted_points, max_gpa)

def calculate_gpa(grades):
    if current_user.is_authenticated:
        scale_key = current_user.gpa_scale or 'standard'
        grade_format = current_user.grade_format or 'plus_minus'
        gpa_cap = current_user.get_gpa_cap()
        get_weight = current_user.get_course_weight
        use_credit_hours = current_user.use_credit_hours

        def get_custom_value(letter):
            val = current_user.get_custom_gpa_value(letter)
            try:
                return float(val)
            except (ValueError, TypeError):
                print(f"[DEBUG] Invalid custom GPA value for '{letter}': {val}")
                return None
    else:
        scale_key = session.get('gpa_scale', 'standard')
        grade_format = session.get('grade_format', 'plus_minus')
        gpa_cap = session.get('gpa_cap', None)
        use_credit_hours = False

        def get_weight(course_type):
            weights = session.get('weights', {
                'Regular': 0.0, 'Honors': 0.5, 'AP': 1.0, 'IB': 1.0, 'DE': 1.0
            })
            return weights.get(course_type, 0.0)

        def get_custom_value(letter):
            custom = session.get('custom_gpa_values', {})
            val = custom.get(letter.upper())
            try:
                return float(val)
            except (ValueError, TypeError):
                print(f"[DEBUG] Invalid or missing custom GPA value for '{letter}': {val}")
                return None

    total_points = 0
    total_credits = 0
    skipped = 0

    for grade in grades:
        if not grade.letter:
            print(f"[DEBUG] Skipped grade with missing letter: {grade}")
            skipped += 1
            continue

        g_letter = grade.letter.strip().upper()
        ctype = getattr(grade, 'course_type', 'Regular') or 'Regular'
        points = None

        if scale_key == 'custom':
            points = get_custom_value(g_letter)
        elif grade_format == 'plus_minus':
            points = {
                'A+': 4.0, 'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D+': 1.3, 'D': 1.0, 'D-': 0.7,
                'F': 0.0
            }.get(g_letter)
        elif grade_format == 'simple':
            points = {
                'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0
            }.get(g_letter[0], 0.0)
        else:
            # fallback to numeric
            grade_numeric = LETTER_TO_NUM.get(g_letter)
            if grade_numeric is not None:
                points = grade_to_gpa_points(grade_numeric, ctype, scale_key)
            else:
                print(f"[DEBUG] LETTER_TO_NUM missing for '{g_letter}'")
                skipped += 1
                continue

        if points is None:
            print(f"[DEBUG] Skipped grade '{g_letter}' — points is None")
            skipped += 1
            continue

        if not isinstance(points, (int, float)):
            print(f"[DEBUG] Skipped grade '{g_letter}' — points is not a number: {points}")
            skipped += 1
            continue

        weight = get_weight(ctype)
        weighted_points = points + weight
        if gpa_cap is not None:
            weighted_points = min(weighted_points, gpa_cap)

        # Get credit hours for the grade
        credit_hours = getattr(grade, 'credit_hours', 1.0)
        try:
            credit_hours = float(credit_hours)
            if not credit_hours:
                credit_hours = 1.0
        except (TypeError, ValueError):
            credit_hours = 1.0
        if not use_credit_hours:
            credit_hours = 1.0

        print(f"[DEBUG] Grade: {g_letter}, Base Points: {points}, Type: {ctype}, Weight: {weight}, Weighted: {weighted_points}, Credits: {credit_hours}")

        total_points += weighted_points * credit_hours
        total_credits += credit_hours

    if total_credits == 0:
        print(f"[DEBUG] All grades skipped. Total skipped: {skipped}")
        return 0.0

    gpa = round(total_points / total_credits, 2)
    print(f"[DEBUG] Final GPA: {gpa} from {total_credits} credits (Skipped: {skipped})")
    return gpa

def get_letter_grade(grade_numeric, grade_format='plus_minus'):
    if grade_numeric is None:
        return ''

    try:
        grade_numeric = float(grade_numeric)
    except (ValueError, TypeError):
        return ''

    if grade_format == 'simple':
        # Simple letter grades (no plus/minus)
        if grade_numeric >= 90:
            return 'A'
        elif grade_numeric >= 80:
            return 'B'
        elif grade_numeric >= 70:
            return 'C'
        elif grade_numeric >= 60:
            return 'D'
        else:
            return 'F'
    else:
        # Plus/Minus letter grades
        if grade_numeric >= 97:
            return 'A+'
        elif grade_numeric >= 93:
            return 'A'
        elif grade_numeric >= 90:
            return 'A-'
        elif grade_numeric >= 87:
            return 'B+'
        elif grade_numeric >= 83:
            return 'B'
        elif grade_numeric >= 80:
            return 'B-'
        elif grade_numeric >= 77:
            return 'C+'
        elif grade_numeric >= 73:
            return 'C'
        elif grade_numeric >= 70:
            return 'C-'
        elif grade_numeric >= 67:
            return 'D+'
        elif grade_numeric >= 63:
            return 'D'
        elif grade_numeric >= 60:
            return 'D-'
        else:
            return 'F'

def calculate_cumulative_gpa(semesters, grades):
    """Calculate cumulative GPA for each semester."""
    cumulative_points = 0
    cumulative_count = 0
    semester_gpas = []
    
    # Sort semesters by start date
    sorted_semesters = sorted(semesters, key=lambda x: x.start_date)
    
    for semester in sorted_semesters:
        # Get grades for this semester
        semester_grades = [g for g in grades if g.semester_id == semester.id]
        
        # Calculate points for this semester's grades
        for grade in semester_grades:
            if not grade.letter:
                continue
                
            g_letter = grade.letter.strip().upper()
            ctype = getattr(grade, 'course_type', 'Regular') or 'Regular'
            
            # Get points based on letter grade
            if current_user.gpa_scale == 'custom':
                points = current_user.get_custom_gpa_value(g_letter)
            elif current_user.grade_format == 'plus_minus':
                points = {
                    'A+': 4.0, 'A': 4.0, 'A-': 3.7,
                    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                    'D+': 1.3, 'D': 1.0, 'D-': 0.7,
                    'F': 0.0
                }.get(g_letter)
            elif current_user.grade_format == 'simple':
                points = {
                    'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0
                }.get(g_letter[0], 0.0)
            else:
                grade_numeric = LETTER_TO_NUM.get(g_letter)
                if grade_numeric is not None:
                    points = grade_to_gpa_points(grade_numeric, ctype, current_user.gpa_scale or 'standard')
                else:
                    continue
            
            if points is None or not isinstance(points, (int, float)):
                continue
                
            # Add course weight
            weight = current_user.get_course_weight(ctype)
            weighted_points = points + weight
            
            # Apply GPA cap if set
            gpa_cap = current_user.get_gpa_cap()
            if gpa_cap is not None:
                weighted_points = min(weighted_points, gpa_cap)
            
            cumulative_points += weighted_points
            cumulative_count += 1
        
        # Calculate cumulative GPA for this point
        if cumulative_count > 0:
            semester_gpas.append(round(cumulative_points / cumulative_count, 2))
        else:
            semester_gpas.append(0.0)
    
    return semester_gpas

@main.route('/', methods=['GET', 'POST'])
def index():
    from app.forms import SettingsForm
    settings_form = SettingsForm()
    # Handle dismiss from modal close button
    if request.method == 'POST' and request.form.get('dismiss_settings_popup'):
        session.pop('show_settings_popup', None)
        return ('', 204)

    if current_user.is_authenticated:
        # Eager load the semester relationship and order by date
        grades = Grade.query.options(
            db.joinedload(Grade.semester)
        ).filter_by(
            user_id=current_user.id
        ).order_by(
            Grade.date.desc()
        ).all()

        # Ensure dates are properly formatted
        for grade in grades:
            if isinstance(grade.date, str):
                try:
                    grade.date = datetime.strptime(grade.date, "%Y-%m-%d").date()
                except ValueError:
                    grade.date = date.today()
            elif grade.date is None:
                grade.date = date.today()

        # Get all semesters for the user
        semesters = Semester.query.filter_by(user_id=current_user.id).all()
        
        # Calculate cumulative GPA for each semester
        semester_labels = [s.name for s in sorted(semesters, key=lambda x: x.start_date)]
        semester_gpa_values = calculate_cumulative_gpa(semesters, grades)

        gpa_scale = current_user.gpa_scale or 'standard'
        grade_format = current_user.grade_format or 'plus_minus'
    else:
        guest_grades = session.get('guest_grades', [])

        class GuestGrade:
            def __init__(self, subject, grade, letter, course_type, date_str):
                self.subject = subject
                self.grade = grade
                self.letter = letter
                self.course_type = course_type or 'Regular'
                if isinstance(date_str, str):
                    try:
                        self.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        self.date = date.today()
                else:
                    self.date = date_str
                self.semester = None  # Guest grades don't have semesters

        grades = [
            GuestGrade(g['subject'], g['grade'], g['letter'], g.get('course_type', 'Regular'), g['date'])
            for g in guest_grades
        ]

        gpa_scale = session.get('gpa_scale', 'standard')
        grade_format = session.get('grade_format', 'plus_minus')
        semester_labels = []
        semester_gpa_values = []

    # Update letter grades from numeric grades BEFORE calculating GPA
    for g in grades:
        g.letter = get_letter_grade(g.grade, grade_format)

    # Calculate average numeric grade
    average = round(sum(g.grade for g in grades) / len(grades), 2) if grades else None

    # Calculate current GPA (uses updated letter grades)
    gpa = calculate_gpa(grades) if grades else None

    delete_form = DeleteForm()

    return render_template(
        'index.html',
        grades=grades,
        average=average,
        gpa=gpa,
        delete_form=delete_form,
        labels=semester_labels,
        values=semester_gpa_values,
        gpa_scale=gpa_scale,
        grade_format=grade_format,
        settings_form=settings_form,
        request=request
    )


@main.route('/add', methods=['GET', 'POST'])
def add_grade():
    form = GradeForm()
    # Populate semester choices
    if current_user.is_authenticated:
        semesters = Semester.query.filter_by(user_id=current_user.id).order_by(Semester.start_date.desc()).all()
        form.semester_id.choices = [(0, 'No Semester')] + [
            (s.id, f"{s.name} ({s.start_date.strftime('%Y-%m-%d') if s.start_date else 'No date'})") 
            for s in semesters
        ]
    else:
        form.semester_id.choices = [(0, 'No Semester')]

    if form.validate_on_submit():
        print("[DEBUG] Add Grade Form Data:", form.data)
        print("[DEBUG] Selected Semester ID:", form.semester_id.data)
        
        subject = form.subject.data
        grade_type = form.grade_type.data
        course_type = form.course_type.data or 'Regular'
        semester_id = form.semester_id.data if form.semester_id.data else None

        if grade_type == 'letter':
            letter = form.letter.data
            grade = LETTER_TO_NUM.get(letter, 0)
        else:
            grade = float(form.grade.data)
            if grade >= 90:
                letter = 'A'
            elif grade >= 80:
                letter = 'B'
            elif grade >= 70:
                letter = 'C'
            elif grade >= 60:
                letter = 'D'
            else:
                letter = 'F'

        # Handle date and semester assignment
        date_obj = None
        if semester_id and semester_id != 0:
            print(f"[DEBUG] Adding grade to semester {semester_id}")
            semester = Semester.query.get(semester_id)
            if semester and semester.start_date:
                date_obj = semester.start_date
                print(f"[DEBUG] Using semester start date: {date_obj}")
        else:
            print("[DEBUG] No semester selected, using form date")
            date_obj = form.date.data

        if current_user.is_authenticated:
            if current_user.use_credit_hours and (form.credit_hours.data is None or form.credit_hours.data == ''):
                flash('Credit hours are required when credit hours are enabled.', 'danger')
                return render_template('add_grade.html', form=form)
            credit_hours = form.credit_hours.data
            if current_user.use_credit_hours:
                try:
                    credit_hours = float(credit_hours)
                    if not credit_hours:
                        credit_hours = 1.0
                except (TypeError, ValueError):
                    credit_hours = 1.0
            else:
                credit_hours = 1.0
            new_grade = Grade(
                subject=subject,
                grade=grade,
                letter=letter,
                course_type=course_type,
                date=date_obj,
                semester_id=semester_id if semester_id != 0 else None,
                credit_hours=credit_hours,
                user_id=current_user.id
            )
            try:
                db.session.add(new_grade)
                db.session.commit()
                print("[DEBUG] Successfully added grade to database")
                flash('Grade added successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                print(f"[DEBUG] Error adding grade: {str(e)}")
                flash(f'Error adding grade: {str(e)}', 'danger')
                return render_template('add_grade.html', form=form, request=request)
        else:
            flash('You must be logged in to add grades with semesters.', 'danger')
            return redirect(url_for('main.login'))

        return redirect(url_for('main.index'))
    else:
        print("[DEBUG] Form validation failed:", form.errors)

    return render_template('add_grade.html', form=form, request=request)

@main.route('/edit/<int:grade_id>', methods=['GET', 'POST'])
@login_required
def edit_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if grade.user_id != current_user.id:
        flash("You don't have permission to edit this grade.", "danger")
        return redirect(url_for('main.index'))

    form = GradeForm(obj=grade)
    semesters = Semester.query.filter_by(user_id=current_user.id).order_by(Semester.start_date.desc()).all()
    # Add a blank choice for 'No Semester'
    form.semester_id.choices = [(0, 'No Semester')] + [
        (s.id, f"{s.name} ({s.start_date.strftime('%Y-%m-%d')})") 
        for s in semesters
    ]
    # Set initial value to 0 if no semester, otherwise use the actual semester_id
    form.semester_id.data = 0 if grade.semester_id is None else grade.semester_id
    
    # Set initial date
    form.date.data = grade.date or date.today()

    if request.method == 'GET':
        form.subject.data = grade.subject
        form.grade.data = grade.grade
        form.letter.data = grade.letter
        form.date.data = grade.date
        form.semester_id.data = grade.semester_id
        form.course_type.data = grade.course_type
        form.credit_hours.data = grade.credit_hours

    print("[DEBUG] Initial form data:", form.data)
    print("[DEBUG] Current grade semester_id:", grade.semester_id)
    print("[DEBUG] Current grade date:", grade.date)

    if form.validate_on_submit():
        print("[DEBUG] Form submitted data:", form.data)
        print("[DEBUG] Selected semester_id:", form.semester_id.data)
        print("[DEBUG] Form date data:", form.date.data)
        
        subject = form.subject.data
        grade_type = form.grade_type.data
        course_type = form.course_type.data or 'Regular'
        semester_id = form.semester_id.data if form.semester_id.data else None
        date_str = request.form.get('date')

        if grade_type == 'letter':
            letter = form.letter.data
            numeric = LETTER_TO_NUM.get(letter, 0)
        else:
            numeric = float(form.grade.data)
            if numeric >= 90:
                letter = 'A'
            elif numeric >= 80:
                letter = 'B'
            elif numeric >= 70:
                letter = 'C'
            elif numeric >= 60:
                letter = 'D'
            else:
                letter = 'F'

        grade.subject = subject
        grade.grade = numeric
        grade.letter = letter
        grade.course_type = course_type
        grade.date = form.date.data
        grade.semester_id = semester_id
        grade.credit_hours = form.credit_hours.data
        
        # Handle date and semester assignment
        if semester_id and semester_id != 0:
            print(f"[DEBUG] Setting semester_id to: {semester_id}")
            # Get the semester directly from the database
            semester = Semester.query.filter_by(id=semester_id, user_id=current_user.id).first()
            print(f"[DEBUG] Found semester: {semester}")
            if semester:
                grade.date = semester.start_date
                grade.semester_id = semester.id
                print(f"[DEBUG] Using semester start date: {grade.date}")
            else:
                print("[DEBUG] Semester not found, using form date")
                if date_str:
                    try:
                        grade.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        grade.date = date.today()
                else:
                    grade.date = date.today()
                grade.semester_id = None
        else:
            print("[DEBUG] No semester selected, using form date:", date_str)
            if date_str:
                try:
                    grade.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    grade.date = date.today()
            else:
                grade.date = date.today()
            grade.semester_id = None

        print(f"[DEBUG] Final grade state - semester_id:", grade.semester_id)
        print(f"[DEBUG] Final grade state - date:", grade.date)

        try:
            db.session.commit()
            print("[DEBUG] Successfully committed changes to database")
            flash('Grade updated successfully.', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            print(f"[DEBUG] Error updating grade: {str(e)}")
            flash(f'Error updating grade: {str(e)}', 'danger')
            return render_template('edit_grade.html', form=form, grade=grade, request=request)

    return render_template('edit_grade.html', form=form, grade=grade, request=request)

@main.route('/delete/<int:grade_id>', methods=['POST'])
@login_required
def delete_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)

    if grade.user_id != current_user.id:
        flash("Unauthorized access.")
        return redirect(url_for('main.index'))

    db.session.delete(grade)
    db.session.commit()
    flash("Grade deleted.")
    return redirect(url_for('main.index'))

@csrf.exempt
@main.route('/delete-guest/<int:index>', methods=['POST'])
def delete_guest_grade(index):
    guest_grades = session.get('guest_grades', [])
    if 0 <= index < len(guest_grades):
        guest_grades.pop(index)
        session['guest_grades'] = guest_grades
        flash("Guest grade deleted.")
    else:
        flash("Invalid grade index.")
    return redirect(url_for('main.index'))

@main.route('/trends')
@login_required
def trends():
    # Query grades with semester information, properly joined
    grades = Grade.query.join(Semester).filter_by(user_id=current_user.id).order_by(Semester.start_date).all()

    if not grades:
        return render_template('trends.html', labels=[], values=[])

    # Get all semesters for the user
    semesters = Semester.query.filter_by(user_id=current_user.id).all()
    
    # Calculate cumulative GPA for each semester
    semester_labels = [s.name for s in sorted(semesters, key=lambda x: x.start_date)]
    semester_gpa_values = calculate_cumulative_gpa(semesters, grades)

    return render_template('trends.html', labels=semester_labels, values=semester_gpa_values)

@main.route('/simulate')
@login_required
def simulate():
    return render_template('simulate.html')

@main.route('/export')
@login_required
def export():
    return render_template('export.html')

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            # Check if first login
            if user.first_login:
                user.first_login = False
                db.session.commit()
                session['show_settings_popup'] = True
            else:
                session.pop('show_settings_popup', None)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html', form=form)


@main.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, password_hash=hashed_password)
        db.session.add(user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {e}", "danger")
            return render_template('signup.html', form=form)
        flash("Account created!", "success")
        return redirect(url_for('main.login'))
    return render_template('signup.html', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('main.login'))


@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = SettingsForm()

    # Create settings record if missing
    if not current_user.settings:
        settings = UserSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()

    if form.validate_on_submit():
        print("✅ Form validated successfully")
        # GPA scale & grade format
        current_user.gpa_scale = form.gpa_scale.data or 'standard'
        current_user.grade_format = form.grade_format.data or 'plus_minus'

        # Save use_credit_hours setting
        current_user.use_credit_hours = form.use_credit_hours.data

        # Grade values
        current_user.a_plus  = form.a_plus.data  if form.a_plus.data  is not None else 4.0
        current_user.a       = form.a.data       if form.a.data       is not None else 4.0
        current_user.a_minus = form.a_minus.data if form.a_minus.data is not None else 3.7
        current_user.b_plus  = form.b_plus.data  if form.b_plus.data  is not None else 3.3
        current_user.b       = form.b.data       if form.b.data       is not None else 3.0
        current_user.b_minus = form.b_minus.data if form.b_minus.data is not None else 2.7
        current_user.c_plus  = form.c_plus.data  if form.c_plus.data  is not None else 2.3
        current_user.c       = form.c.data       if form.c.data       is not None else 2.0
        current_user.c_minus = form.c_minus.data if form.c_minus.data is not None else 1.7
        current_user.d_plus  = form.d_plus.data  if form.d_plus.data  is not None else 1.3
        current_user.d       = form.d.data       if form.d.data       is not None else 1.0
        current_user.d_minus = form.d_minus.data if form.d_minus.data is not None else 0.7
        current_user.f       = form.f.data       if form.f.data       is not None else 0.0

        # Weight system logic
        scale = current_user.gpa_scale
        if scale == 'standard':
            current_user.weight_regular = 0.0
            current_user.weight_honors = 0.0
            current_user.weight_ap = 0.0
            current_user.weight_ib = 0.0
            current_user.weight_de = 0.0
            current_user.gpa_cap = 4.0
        elif scale == 'weighted_5':
            current_user.weight_regular = 0.0
            current_user.weight_honors = 0.5
            current_user.weight_ap = 1.0
            current_user.weight_ib = 1.0
            current_user.weight_de = 1.0
            current_user.gpa_cap = 5.0
        elif scale == 'weighted_6':
            current_user.weight_regular = 0.0
            current_user.weight_honors = 1.0
            current_user.weight_ap = 2.0
            current_user.weight_ib = 2.0
            current_user.weight_de = 2.0
            current_user.gpa_cap = 6.0
        elif scale == 'custom':
            current_user.weight_regular = form.weight_regular.data or 0.0
            current_user.weight_honors = form.weight_honors.data or 0.0
            current_user.weight_ap = form.weight_ap.data or 0.0
            current_user.weight_ib = form.weight_ib.data or 0.0
            current_user.weight_de = form.weight_de.data or 0.0
            current_user.gpa_cap = form.gpa_cap.data or 4.0

        # Commit changes
        db.session.commit()
        session.pop('show_settings_popup', None)
        flash('Settings saved successfully. GPA calculations now reflect your chosen scale.', 'success')
        return redirect(url_for('main.index'))

    elif request.method == 'GET':
        # Populate form fields with current user settings
        form.gpa_scale.data = current_user.gpa_scale or 'standard'
        form.grade_format.data = current_user.grade_format or 'plus_minus'
        form.use_credit_hours.data = current_user.use_credit_hours

        form.a_plus.data = current_user.a_plus
        form.a.data = current_user.a
        form.a_minus.data = current_user.a_minus
        form.b_plus.data = current_user.b_plus
        form.b.data = current_user.b
        form.b_minus.data = current_user.b_minus
        form.c_plus.data = current_user.c_plus
        form.c.data = current_user.c
        form.c_minus.data = current_user.c_minus
        form.d_plus.data = current_user.d_plus
        form.d.data = current_user.d
        form.d_minus.data = current_user.d_minus
        form.f.data = current_user.f

        form.weight_regular.data = current_user.weight_regular
        form.weight_honors.data = current_user.weight_honors
        form.weight_ap.data = current_user.weight_ap
        form.weight_ib.data = current_user.weight_ib
        form.weight_de.data = current_user.weight_de

        form.gpa_cap.data = current_user.gpa_cap

    else:
        print("❌ Form did not validate:")
        for field_name, error_messages in form.errors.items():
            print(f"{field_name}: {error_messages}")

    return render_template('settings.html', form=form)

@main.route('/fix_gpa')
def fix_gpa():
    from app.models import User  # if needed
    users = User.query.all()
    for u in users:
        if isinstance(u.gpa_scale, float):
            u.gpa_scale = 'standard'
        if isinstance(u.grade_format, float):
            u.grade_format = 'plus_minus'
    db.session.commit()
    return "Fixed GPA scale and grade format for any users with invalid float values."


@main.route('/admin')
@login_required
def admin_dashboard():
    if current_user.username != "jaydenokoeguale":
        flash('You do not have permission to access the admin dashboard.', 'danger')
        return redirect(url_for('main.index'))
    
    # Get basic statistics
    user_count = User.query.count()
    total_grades = Grade.query.count()
    total_semesters = Semester.query.count()
    online_users = User.query.filter_by(is_online=True).count()
    
    # Get recent activities
    recent_activities = UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(50).all()
    
    # Get all users with their activity stats
    users = User.query.all()
    
    return render_template('admin.html',
        user_count=user_count,
        total_grades=total_grades,
        total_semesters=total_semesters,
        online_users=online_users,
        recent_activities=recent_activities,
        users=users
    )

@main.route('/admin/user/<int:user_id>')
@login_required
def admin_user_details(user_id):
    if current_user.username != "jaydenokoeguale":
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    recent_activities = UserActivity.query.filter_by(user_id=user_id)\
        .order_by(UserActivity.timestamp.desc()).limit(10).all()
    
    return jsonify({
        'username': user.username,
        'is_online': user.is_online,
        'last_seen': user.last_seen.strftime('%Y-%m-%d %H:%M:%S') if user.last_seen else None,
        'total_grades': len(user.grades),
        'total_semesters': len(user.semesters),
        'recent_activities': [activity.to_dict() for activity in recent_activities]
    })

@main.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_admin(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    
    return jsonify({'success': True})

@main.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True})

@main.route('/semesters')
@login_required
def semesters():
    # Query all semesters for the current user, eager load grades
    semesters = Semester.query.filter_by(user_id=current_user.id).order_by(Semester.start_date.desc()).all()
    form = DeleteForm()
    return render_template(
        'semester.html',
        semesters=semesters,
        request=request,
        calculate_gpa=calculate_gpa,  # Pass the calculate_gpa function to the template
        form=form  # Pass the form to the template
    )

@main.route('/add_semester', methods=['GET', 'POST'])
@login_required
def add_semester():
    form = SemesterForm()
    if form.validate_on_submit():
        new_semester = Semester(
            name=form.name.data,
            start_date=form.start_date.data,
            user_id=current_user.id
        )
        db.session.add(new_semester)
        db.session.commit()
        flash('Semester added successfully!', 'success')
        return redirect(url_for('main.semesters'))
    return render_template('add_semester.html', form=form)

@main.route('/edit_semester/<int:semester_id>', methods=['GET', 'POST'])
@login_required
def edit_semester(semester_id):
    semester = Semester.query.get_or_404(semester_id)
    if semester.user_id != current_user.id:
        flash("You don't have permission to edit this semester.", "danger")
        return redirect(url_for('main.semesters'))

    form = SemesterForm(obj=semester)
    if form.validate_on_submit():
        # Store the old date for comparison
        old_date = semester.start_date
        new_date = form.start_date.data
        
        # Update semester
        semester.name = form.name.data
        semester.start_date = new_date
        
        # If the date has changed, update all associated grades
        if old_date != new_date:
            for grade in semester.grades:
                grade.date = new_date
        
        db.session.commit()
        flash('Semester and associated grades updated successfully!', 'success')
        return redirect(url_for('main.semesters'))
    return render_template('edit_semester.html', form=form, semester=semester)

@main.route('/delete_semester/<int:semester_id>', methods=['POST'])
@login_required
def delete_semester(semester_id):
    semester = Semester.query.get_or_404(semester_id)
    if semester.user_id != current_user.id:
        flash("You don't have permission to delete this semester.", "danger")
        return redirect(url_for('main.semesters'))
    
    # Check if semester has grades
    if semester.grades:
        flash("Cannot delete semester that contains grades. Please delete the grades first.", "danger")
        return redirect(url_for('main.semesters'))
    
    db.session.delete(semester)
    db.session.commit()
    flash('Semester deleted successfully!', 'success')
    return redirect(url_for('main.semesters'))

# Add activity tracking to existing routes
@main.before_request
def track_activity():
    if current_user.is_authenticated:
        current_user.update_activity(
            action=request.endpoint,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            details={'path': request.path}
        )