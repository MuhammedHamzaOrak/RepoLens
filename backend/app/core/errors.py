class RepoLensError(Exception):
    """Base application error."""


class ValidationError(RepoLensError):
    """Raised when incoming payload is invalid."""


class ProjectNotFoundError(RepoLensError):
    """Raised when a project cannot be found."""
