"""Expected failures with stable exit-code mapping."""


class UpliftError(Exception):
    """Base class for errors a user can act on."""


class DataError(UpliftError):
    """Dataset is missing, malformed, or cannot be downloaded."""


class ChecksumError(DataError):
    """Downloaded or cached bytes do not match the pinned digest."""


class SchemaError(DataError):
    """Dataset columns or values do not match the declared contract."""


class ConfigError(UpliftError):
    """Configuration is missing, malformed, or out of range."""


class AnalysisError(UpliftError):
    """The requested analysis is not defined for the supplied data."""


class ReportError(UpliftError):
    """A report or result file could not be written safely."""
