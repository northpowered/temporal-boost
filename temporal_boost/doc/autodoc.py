import typing


if typing.TYPE_CHECKING:
    from core import BoostApp


class DocumentationManager:

    def __init__(self, app: "BoostApp") -> None:
        self.app: "BoostApp" = app
