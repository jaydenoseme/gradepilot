from flask_login import UserMixin
from app import db

# ----------------------------
# Custom GPA Configuration Model
# ----------------------------
class CustomGPA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # GPA values per letter grade
    a_plus = db.Column(db.Float, default=4.0)
    a = db.Column(db.Float, default=4.0)
    a_minus = db.Column(db.Float, default=3.7)
    b_plus = db.Column(db.Float, default=3.3)
    b = db.Column(db.Float, default=3.0)
    b_minus = db.Column(db.Float, default=2.7)
    c_plus = db.Column(db.Float, default=2.3)
    c = db.Column(db.Float, default=2.0)
    c_minus = db.Column(db.Float, default=1.7)
    d_plus = db.Column(db.Float, default=1.3)
    d = db.Column(db.Float, default=1.0)
    d_minus = db.Column(db.Float, default=0.7)
    f = db.Column(db.Float, default=0.0)

    # Custom course type weights
    weight_regular = db.Column(db.Float, default=0.0)
    weight_honors = db.Column(db.Float, default=0.5)
    weight_ap = db.Column(db.Float, default=1.0)
    weight_ib = db.Column(db.Float, default=1.0)
    weight_de = db.Column(db.Float, default=1.0)

    # GPA cap (optional)
    gpa_cap = db.Column(db.Float, nullable=True)


# ----------------------------
# UserSettings Model (NEW)
# ----------------------------
class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    default_course_type = db.Column(db.String(20), default='Regular')
    default_grade_type = db.Column(db.String(20), default='number')


# ----------------------------
# User Model
# ----------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # GPA format and scale settings
    gpa_scale = db.Column(db.String(20), default='standard')  # 'standard', 'weighted_5', 'weighted_6', 'percentage', 'custom'
    grade_format = db.Column(db.String(20), default='simple')  # 'plus_minus' or 'simple'

    # Custom GPA values (used if scale is set to 'custom')
    a_plus = db.Column(db.Float, default=4.0)
    a = db.Column(db.Float, default=4.0)
    a_minus = db.Column(db.Float, default=3.7)
    b_plus = db.Column(db.Float, default=3.3)
    b = db.Column(db.Float, default=3.0)
    b_minus = db.Column(db.Float, default=2.7)
    c_plus = db.Column(db.Float, default=2.3)
    c = db.Column(db.Float, default=2.0)
    c_minus = db.Column(db.Float, default=1.7)
    d_plus = db.Column(db.Float, default=1.3)
    d = db.Column(db.Float, default=1.0)
    d_minus = db.Column(db.Float, default=0.7)
    f = db.Column(db.Float, default=0.0)

    # Course weight values
    weight_regular = db.Column(db.Float, default=0.0)
    weight_honors = db.Column(db.Float, default=0.5)
    weight_ap = db.Column(db.Float, default=1.0)
    weight_ib = db.Column(db.Float, default=1.0)
    weight_de = db.Column(db.Float, default=1.0)

    # Optional GPA cap
    gpa_cap = db.Column(db.Float, nullable=True)

    # Relationships
    settings = db.relationship('UserSettings', uselist=False, backref='user', cascade="all, delete")

    # Helper methods
    def get_custom_gpa_value(self, letter):
        """Return the custom GPA value for the given letter grade."""
        mapping = {
            'A+': self.a_plus,
            'A': self.a,
            'A-': self.a_minus,
            'B+': self.b_plus,
            'B': self.b,
            'B-': self.b_minus,
            'C+': self.c_plus,
            'C': self.c,
            'C-': self.c_minus,
            'D+': self.d_plus,
            'D': self.d,
            'D-': self.d_minus,
            'F': self.f
        }

        val = mapping.get(letter.upper())
        try:
            return float(val)
        except (ValueError, TypeError):
            print(f"[DEBUG] Invalid custom GPA value for '{letter}': {val}")
            return None

    def get_course_weight(self, course_type):
        return {
            "Regular": self.weight_regular,
            "Honors": self.weight_honors,
            "AP": self.weight_ap,
            "IB": self.weight_ib,
            "DE": self.weight_de
        }.get(course_type, 0.0)

    def get_gpa_cap(self):
        return self.gpa_cap

    def get_active_gpa_scale(self):
        return self.gpa_scale or 'standard'


# ----------------------------
# Grade Model
# ----------------------------
class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    subject = db.Column(db.String(100), nullable=False)
    grade = db.Column(db.Float, nullable=False)  # Numeric grade (optional)
    letter = db.Column(db.String(2), nullable=False)  # A, B+, C-, etc.

    course_type = db.Column(db.String(20), default='Regular')  # Regular, Honors, AP

    date = db.Column(db.Date, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
