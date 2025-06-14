from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, SelectField, DateField, FloatField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, NumberRange, Optional
from app.models import User

class GradeForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired()])
    grade_type = SelectField('Grade Type', choices=[('number', 'Number'), ('letter', 'Letter')], default='number')

    grade = DecimalField('Grade (0-100)', validators=[Optional(), NumberRange(min=0, max=100)])
    letter = SelectField(
        'Letter Grade',
        choices=[('', 'Select')] + [(g, g) for g in ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F']],
        validators=[Optional()]
    )

    # ✅ Updated course_type with all possible options
    course_type = SelectField(
        'Course Type',
        choices=[
            ('Regular', 'Regular'),
            ('Honors', 'Honors'),
            ('AP', 'AP'),
            ('IB', 'IB'),
            ('DE', 'DE')
        ],
        default='Regular'
    )

    date = DateField('Date', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Add Grade')

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.grade_type.data == 'number':
            if self.grade.data is None:
                self.grade.errors.append("Numeric grade is required.")
                return False
        elif self.grade_type.data == 'letter':
            if not self.letter.data or self.letter.data not in dict(self.letter.choices):
                self.letter.errors.append("Valid letter grade is required.")
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
