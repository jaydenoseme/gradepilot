"""
Add Semester model and semester_id foreign key to Grade
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250614_01'
down_revision = '42ba7e6641db'  # Set this to the latest previous migration's revision id
branch_labels = None
depends_on = None

def upgrade():
    # Add semester_id column and foreign key using batch mode for SQLite compatibility
    with op.batch_alter_table('grade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('semester_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_grade_semester', 'semester', ['semester_id'], ['id']
        )

def downgrade():
    with op.batch_alter_table('grade', schema=None) as batch_op:
        batch_op.drop_constraint('fk_grade_semester', type_='foreignkey')
        batch_op.drop_column('semester_id')
    # op.drop_table('semester')
