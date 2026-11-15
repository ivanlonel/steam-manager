"""The base of every payload model, and the report of the fields nothing declares."""

from pydantic import BaseModel, ConfigDict


class SteamModel(BaseModel):
    """
    A part of an answer Steam sent. Fields nothing declares are kept, to be reported.

    Lists are declared as tuples defaulting to ``()``: an immutable default suits a frozen
    model, and needs no ``default_factory``.
    """

    model_config = ConfigDict(extra="allow", frozen=True)


def unknown_fields(model: BaseModel) -> list[str]:
    """
    List the fields of *model*, at any depth, that no model declares.

    An unknown field holding ``None``, ``[]`` or ``{}`` isn't listed: Steam sends such empty
    placeholders, and the notebooks' loader skipped them too.

    :param model: A validated answer.
    :return: The sorted paths of the unknown fields, such as ``purchase_options[].new``. A list
        item adds ``[]`` and a mapping value ``*``.
    """
    paths: set[str] = set()
    _collect(model, "", paths)
    return sorted(paths)


def _collect(value: object, path: str, paths: set[str]) -> None:
    """
    Add to *paths* the unknown fields within *value*, which sits at *path*.

    :param value: A model, a list or mapping that may hold models, or a plain value.
    :param path: Where *value* sits in the answer.
    :param paths: The paths found so far.
    """
    if isinstance(value, BaseModel):
        for key, extra in (value.model_extra or {}).items():
            if extra not in (None, [], {}):
                paths.add(_join(path, key))
        for name in type(value).model_fields:
            _collect(getattr(value, name), _join(path, name), paths)
    elif isinstance(value, list | tuple):
        for item in value:
            _collect(item, f"{path}[]", paths)
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, _join(path, "*"), paths)


def _join(path: str, name: str) -> str:
    """
    Append *name* to *path*.

    :param path: A path, or ``""`` at the top.
    :param name: A field name.
    :return: The longer path.
    """
    return f"{path}.{name}" if path else name
