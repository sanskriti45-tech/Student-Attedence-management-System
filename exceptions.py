class AttendanceSystemError(Exception):
    """Base exception for the Smart Attendance Management System."""
    pass

class InvalidStudentIDError(AttendanceSystemError):
    """Raised when a student ID is invalid or does not exist."""
    pass

class DuplicateAttendanceEntryError(AttendanceSystemError):
    """Raised when marking attendance for a user who already has attendance on that date."""
    pass

class InvalidAttendanceStatusError(AttendanceSystemError):
    """Raised when an invalid status is provided (must be Present, Absent, or Leave)."""
    pass

class LeaveRecordNotFoundError(AttendanceSystemError):
    """Raised when a requested leave record cannot be found."""
    pass

class IncorrectUserInputError(AttendanceSystemError):
    """Raised when user input fails validation check."""
    pass
