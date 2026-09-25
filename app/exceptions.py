class WorkspaceAccessDeniedError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class WorkspacePermissionDeniedError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class WorkspaceNotFoundError(Exception):
    pass


class DeliveryNotFoundError(Exception): ...


class DeliveryNotReplayableError(Exception): ...
