from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app import db, csrf
from app.models import User, Grade, CustomGPA, UserSettings
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from app.forms import GradeForm, DeleteForm, LoginForm, SignupForm, GpaScaleForm, SettingsForm
from flask_wtf.csrf import CSRFProtect

main = Blueprint('main', __name__)

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
    count = 0
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

        print(f"[DEBUG] Grade: {g_letter}, Base Points: {points}, Type: {ctype}, Weight: {weight}, Weighted: {weighted_points}")

        total_points += weighted_points
        count += 1

    if count == 0:
        print(f"[DEBUG] All grades skipped. Total skipped: {skipped}")
        return 0.0

    gpa = round(total_points / count, 2)
    print(f"[DEBUG] Final GPA: {gpa} from {count} grades (Skipped: {skipped})")
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

@main.route('/')
def index():
    if current_user.is_authenticated:
        grades = Grade.query.filter_by(user_id=current_user.id).all()

        for grade in grades:
            if isinstance(grade.date, str):
                try:
                    grade.date = datetime.strptime(grade.date, "%Y-%m-%d").date()
                except ValueError:
                    grade.date = date.today()

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

        grades = [
            GuestGrade(g['subject'], g['grade'], g['letter'], g.get('course_type', 'Regular'), g['date'])
            for g in guest_grades
        ]

        gpa_scale = session.get('gpa_scale', 'standard')
        grade_format = session.get('grade_format', 'plus_minus')

    # Update letter grades from numeric grades BEFORE calculating GPA
    for g in grades:
        g.letter = get_letter_grade(g.grade, grade_format)

    # Calculate average numeric grade
    average = round(sum(g.grade for g in grades) / len(grades), 2) if grades else None

    # Calculate current GPA (uses updated letter grades)
    gpa = calculate_gpa(grades) if grades else None

    # Prepare GPA trend data (running GPA over time)
    sorted_grades = sorted(grades, key=lambda g: g.date)
    labels = []
    running_totals = []

    partial_grades = []
    for g in sorted_grades:
        partial_grades.append(g)
        partial_gpa = calculate_gpa(partial_grades)
        running_totals.append(partial_gpa)
        try:
            labels.append(g.date.strftime('%b %-d %Y'))
        except Exception:
            labels.append(str(g.date))

    delete_form = DeleteForm()

    return render_template(
        'index.html',
        grades=grades,
        average=average,
        gpa=gpa,
        delete_form=delete_form,
        labels=labels,
        values=running_totals,
        gpa_scale=gpa_scale,
        grade_format=grade_format
    )


@main.route('/add', methods=['GET', 'POST'])
def add_grade():
    form = GradeForm()

    if request.method == "POST":
        print("[DEBUG] POST request received")

    if form.validate_on_submit():
        print("[DEBUG] Form validated successfully")
        subject = form.subject.data
        grade_type = form.grade_type.data
        course_type = form.course_type.data or 'Regular'
        date_obj = form.date.data or date.today()

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

        if current_user.is_authenticated:
            new_grade = Grade(
                subject=subject,
                grade=grade,
                letter=letter,
                course_type=course_type,
                date=date_obj,
                user_id=current_user.id
            )
            db.session.add(new_grade)
            db.session.commit()
            flash('Grade added successfully!', 'success')
            print(f"[DEBUG] Added grade to DB for user {current_user.username}")
        else:
            guest_grades = session.get('guest_grades', [])
            guest_grades.append({
                'subject': subject,
                'grade': grade,
                'letter': letter,
                'course_type': course_type,
                'date': date_obj.strftime('%Y-%m-%d')
            })
            session['guest_grades'] = guest_grades
            session.modified = True
            flash('Grade added temporarily for this session (log in to save).', 'info')
            print(f"[DEBUG] Added grade to session: {session['guest_grades']}")

        return redirect(url_for('main.index'))
    else:
        print("[DEBUG] Form failed validation:", form.errors)

    if not form.date.data:
        form.date.data = date.today()

    return render_template('add_grade.html', form=form)

@main.route('/edit/<int:grade_id>', methods=['GET', 'POST'])
@login_required
def edit_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    if grade.user_id != current_user.id:
        flash("You don't have permission to edit this grade.", "danger")
        return redirect(url_for('main.index'))

    if isinstance(grade.date, str):
        try:
            grade.date = datetime.strptime(grade.date, '%Y-%m-%d').date()
        except ValueError:
            grade.date = date.today()

    form = GradeForm(obj=grade)

    if form.validate_on_submit():
        subject = form.subject.data
        grade_type = form.grade_type.data
        course_type = form.course_type.data or 'Regular'
        date_obj = form.date.data or date.today()

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
        grade.date = date_obj

        db.session.commit()
        flash('Grade updated successfully.', 'success')
        return redirect(url_for('main.index'))

    return render_template('edit_grade.html', form=form, grade=grade)

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
    grades = Grade.query.filter_by(user_id=current_user.id).order_by(Grade.date).all()

    if not grades:
        return render_template('trends.html', labels=[], values=[])

    labels = []
    values = []
    total_points = 0

    for i, grade in enumerate(grades, start=1):
        partial_gpa = calculate_gpa(grades[:i])
        values.append(partial_gpa)

        if isinstance(grade.date, (datetime, date)):
            labels.append(grade.date.strftime('%b %-d %Y'))
        else:
            labels.append(datetime.strptime(str(grade.date), '%Y-%m-%d').strftime('%b %-d %Y'))

    return render_template('trends.html', labels=labels, values=values)

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
        flash('Settings saved successfully. GPA calculations now reflect your chosen scale.', 'success')
        return redirect(url_for('main.settings'))

    elif request.method == 'GET':
        # Populate form fields with current user settings
        form.gpa_scale.data = current_user.gpa_scale or 'standard'
        form.grade_format.data = current_user.grade_format or 'plus_minus'

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
