"""add audit_template_id to audits

Revision ID: c2f4b8d6e3a1
Revises: 609bec748f2a
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2f4b8d6e3a1'
down_revision = '609bec748f2a'


def upgrade():
    with op.batch_alter_table('audits') as batch_op:
        batch_op.add_column(
            sa.Column('audit_template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_audits_audit_template_id',
            'audit_templates',
            ['audit_template_id'],
            ['id'])


def downgrade():
    with op.batch_alter_table('audits') as batch_op:
        batch_op.drop_constraint(
            'fk_audits_audit_template_id',
            type_='foreignkey')
        batch_op.drop_column('audit_template_id')
