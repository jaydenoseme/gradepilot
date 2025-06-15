from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, SelectField, DateField, FloatField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, NumberRange, Optional
from app.models import User

class GradeForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired()])
    grade_type = SelectField('Grade Type', choices=[('number', 'Numeric'), ('letter', 'Letter')], validators=[DataRequired()])
    grade = FloatField('Grade', validators=[Optional()])
    letter = SelectField('Letter Grade', choices=[
        ('A+', 'A+'), ('A', 'A'), ('A-', 'A-'),
        ('B+', 'B+'), ('B', 'B'), ('B-', 'B-'),
        ('C+', 'C+'), ('C', 'C'), ('C-', 'C-'),
        ('D+', 'D+'), ('D', 'D'), ('D-', 'D-'),
        ('F', 'F')
    ], validators=[Optional()])
    course_type = SelectField('Course Type', choices=[
        ('Regular', 'Regular'),
        ('Honors', 'Honors'),
        ('AP', 'AP'),
        ('IB', 'IB'),
        ('DE', 'Dual Enrollment')
    ], validators=[Optional()])
    semester_id = SelectField('Semester', coerce=int, validators=[Optional()], choices=[('', 'No Semester')])
    date = DateField('Date', format='%Y-%m-%d', validators=[Optional()])
    credit_hours = FloatField('Credit Hours', default=1.0)
    submit = SubmitField('Submit')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False
        
        if self.grade_type.data == 'number':
            if not self.grade.data:
                self.grade.errors.append('Numeric grade is required')
                return False
        else:
            if not self.letter.data:
                self.letter.errors.append('Letter grade is required')
                return False
        
        return True

class DeleteForm(FlaskForm):
    submit = SubmitField('Delete')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Log In')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')

class GpaScaleForm(FlaskForm):
    gpa_scale = SelectField(
        'Select GPA Scale',
        choices=[
            ('standard', 'Standard U.S. 4.0 Unweighted'),
            ('weighted_5', '5.0 Weighted Scale'),
            ('weighted_4.5', '4.5 Weighted Scale'),
            ('college_plus_minus', 'College 4.0 with +/-'),
            ('custom', 'Custom (Coming Soon)'),
        ],
        default='standard'
    )
    submit = SubmitField('Save')


class SettingsForm(FlaskForm):
    gpa_scale = SelectField(
    'GPA Scale',
    choices=[  # add a default empty choice
        ('', 'Select a scale'),
        ('standard', 'Unweighted 4.0'),
        ('weighted_5', 'Weighted 5.0'),
        ('weighted_6', 'Weighted 6.0'),
        ('college_plus_minus', 'College +/- (4.0 with Variants)'),
        ('percentage', 'Percentage-based'),
        ('custom', 'Custom GPA Scale')
    ],
    validators=[DataRequired(message="Please select a GPA scale.")]
    )

    grade_format = SelectField(
        'Grade Format',
        choices=[
            ('', 'Select a format'),
            ('plus_minus', 'Letter Grades with +/-'),
            ('simple', 'Simple Letter Grades (A, B, C...)')
        ],
        validators=[DataRequired(message="Please select a grade format.")]
    )

    # Optional GPA cap
    gpa_cap = FloatField('GPA Cap (Optional)', default=None, validators=[Optional()])

    use_credit_hours = BooleanField('Use Credit Hours for GPA Calculation')

    # Custom GPA values
    a_plus = FloatField('A+ GPA', default=4.0)
    a = FloatField('A GPA', default=4.0)
    a_minus = FloatField('A- GPA', default=3.7)
    b_plus = FloatField('B+ GPA', default=3.3)
    b = FloatField('B GPA', default=3.0)
    b_minus = FloatField('B- GPA', default=2.7)
    c_plus = FloatField('C+ GPA', default=2.3)
    c = FloatField('C GPA', default=2.0)
    c_minus = FloatField('C- GPA', default=1.7)
    d_plus = FloatField('D+ GPA', default=1.3)
    d = FloatField('D GPA', default=1.0)
    d_minus = FloatField('D- GPA', default=0.7)
    f = FloatField('F GPA', default=0.0)

    # Course weights
    weight_regular = FloatField('Regular Weight', default=0.0)
    weight_honors = FloatField('Honors Weight', default=0.5)
    weight_ap = FloatField('AP Weight', default=1.0)
    weight_ib = FloatField('IB Weight', default=1.0)
    weight_de = FloatField('DE Weight', default=1.0)

    # Optional GPA cap


    submit = SubmitField('Save Settings')

class SemesterForm(FlaskForm):
    name = StringField('Semester Name (e.g., Fall 2024)', validators=[DataRequired()])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Save Semester')
