"""Add explicit internal-fixture and kickoff-confirmation flags.

Revision ID: 9c31e2a7f64b
Revises: 844685d729fb
"""
from alembic import op
import sqlalchemy as sa

revision = "9c31e2a7f64b"
down_revision = "844685d729fb"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "matches",
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "matches",
        sa.Column("kickoff_confirmed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # The current Planadeu-only fixture is a placeholder, not an official league
    # match. Identify it by season + both team names + an unplayed midnight kickoff
    # so no real result or confirmed fixture is touched.
    op.execute(
        sa.text("""
            UPDATE matches AS m
               SET is_internal = TRUE,
                   kickoff_confirmed = FALSE
              FROM seasons AS s, teams AS home, teams AS away
             WHERE m.season_id = s.id
               AND m.home_team_id = home.id
               AND m.away_team_id = away.id
               AND s.name = '2026-2027'
               AND home.name = 'UD Can Trias'
               AND away.name = 'UE Planadeu'
               AND m.is_played = FALSE
               AND m.home_goals IS NULL
               AND m.away_goals IS NULL
               AND m.kickoff::time = TIME '00:00:00'
        """)
    )


def downgrade():
    op.drop_column("matches", "kickoff_confirmed")
    op.drop_column("matches", "is_internal")
