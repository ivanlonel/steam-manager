"""The base every Steam table is declared on, and the types STRICT tables allow."""

from typing import TYPE_CHECKING, Any, ClassVar, Final, override

from sqlalchemy import Integer, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect
    from sqlalchemy.types import TypeEngine

STRICT: Final = {"sqlite_strict": True}
"""``__table_args__`` of a STRICT table: SQLite refuses a value of the wrong type."""

STRICT_WITHOUT_ROWID: Final = {"sqlite_strict": True, "sqlite_with_rowid": False}
"""``__table_args__`` of a STRICT table that stores its rows in its primary key."""


# SQLAlchemy's type hierarchy is deeper than pylint allows, and TypeDecorator renders literals
# through process_bind_param when process_literal_param isn't overridden.
# pylint: disable-next=too-many-ancestors,abstract-method
class Flag(TypeDecorator[bool]):
    """A yes or no, stored as 1 or 0 as the notebook stores it: STRICT tables have no BOOLEAN."""

    impl: TypeEngine[Any] | type[TypeEngine[Any]] = Integer
    """Stored as an INTEGER."""
    cache_ok: bool | None = True
    """It holds no state, so statements using it can be cached."""

    @override
    def process_bind_param(self, value: bool | None, dialect: Dialect) -> int | None:
        """
        Turn a flag into the integer stored.

        :param value: The flag, or ``None`` when unknown.
        :param dialect: The database's dialect, unused.
        :return: 1, 0 or ``None``.
        """
        return None if value is None else int(value)

    @override
    def process_result_value(self, value: Any, dialect: Dialect) -> bool | None:
        """
        Turn a stored integer back into a flag.

        :param value: 1, 0 or ``None``.
        :param dialect: The database's dialect, unused.
        :return: The flag, or ``None`` when unknown.
        """
        return None if value is None else bool(value)


class SteamBase(DeclarativeBase):
    """
    The base of every Steam table: what Steam says, rebuilt from the raw archive when it changes.

    A ``str`` column is TEXT and a ``bool`` one a :class:`Flag`, since STRICT tables refuse the
    VARCHAR and BOOLEAN that SQLAlchemy would otherwise declare.
    """

    type_annotation_map: ClassVar = {bool: Flag, str: Text}
    """The column type each Python type gets."""
