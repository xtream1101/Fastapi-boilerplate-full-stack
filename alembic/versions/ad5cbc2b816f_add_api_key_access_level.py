"""add_api_key_access_level

Revision ID: ad5cbc2b816f
Revises: e4f84e126dd0
Create Date: 2025-02-09 12:00:25.496061

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import Enum

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ad5cbc2b816f"
down_revision: Union[str, None] = "e4f84e126dd0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type first
    access_level_enum = Enum("READ", "READ_WRITE", name="apikeyaccesslevel")
    access_level_enum.create(op.get_bind())

    # Add column using the enum
    op.add_column(
        "api_keys",
        sa.Column(
            "access_level", access_level_enum, nullable=False, server_default="READ"
        ),
    )


def downgrade() -> None:
    # Drop the column first
    op.drop_column("api_keys", "access_level")

    # Then drop the enum type
    access_level_enum = Enum("READ", "READ_WRITE", name="apikeyaccesslevel")
    access_level_enum.drop(op.get_bind())
