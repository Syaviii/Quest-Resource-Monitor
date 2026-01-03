"""
VR System Monitor - API Error Handling
Custom exceptions and error response handlers.
"""
from flask import jsonify
import logging

logger = logging.getLogger(__name__)


# ========== Custom Exceptions ==========

class APIError(Exception):
    """Base API error class."""
    status_code = 500
    error_code = "INTERNAL_ERROR"
    
    def __init__(self, message: str = None, status_code: int = None):
        super().__init__(message)
        self.message = message or "An internal error occurred"
        if status_code:
            self.status_code = status_code
    
    def to_dict(self):
        return {
            "success": False,
            "error": {
                "code": self.error_code,
                "message": self.message
            },
            "data": None
        }


class DeviceNotFoundError(APIError):
    """Device not found or not connected."""
    status_code = 404
    error_code = "DEVICE_NOT_FOUND"
    
    def __init__(self, device_id: str = None):
        message = f"Device '{device_id}' not found" if device_id else "Device not found"
        super().__init__(message)


class DeviceDisconnectedError(APIError):
    """Device is disconnected."""
    status_code = 503
    error_code = "DEVICE_DISCONNECTED"
    
    def __init__(self, device_id: str = None):
        message = f"Device '{device_id}' is disconnected" if device_id else "Device disconnected"
        super().__init__(message)


class ADBError(APIError):
    """ADB communication error."""
    status_code = 503
    error_code = "ADB_ERROR"
    
    def __init__(self, message: str = "ADB communication failed"):
        super().__init__(message)


class MetricCollectionError(APIError):
    """Failed to collect metrics."""
    status_code = 500
    error_code = "METRIC_COLLECTION_ERROR"
    
    def __init__(self, message: str = "Failed to collect metrics"):
        super().__init__(message)


class DatabaseError(APIError):
    """Database operation error."""
    status_code = 500
    error_code = "DATABASE_ERROR"
    
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message)


class RecordingError(APIError):
    """Recording session error."""
    status_code = 400
    error_code = "RECORDING_ERROR"
    
    def __init__(self, message: str = "Recording operation failed"):
        super().__init__(message)


class ValidationError(APIError):
    """Request validation error."""
    status_code = 400
    error_code = "VALIDATION_ERROR"
    
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message)


# ========== Error Handlers ==========

def register_error_handlers(app):
    """Register error handlers with Flask app."""
    
    @app.errorhandler(APIError)
    def handle_api_error(error):
        logger.error(f"API Error: {error.error_code} - {error.message}")
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "Resource not found"
            },
            "data": None
        }), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        logger.error(f"Internal Server Error: {error}")
        return jsonify({
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred"
            },
            "data": None
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        logger.exception(f"Unexpected error: {error}")
        return jsonify({
            "success": False,
            "error": {
                "code": "UNEXPECTED_ERROR",
                "message": str(error)
            },
            "data": None
        }), 500


# ========== Response Helpers ==========

def success_response(data=None, message: str = None):
    """Create a success response."""
    response = {
        "success": True,
        "data": data,
        "error": None
    }
    if message:
        response["message"] = message
    return jsonify(response)


def error_response(code: str, message: str, status_code: int = 400):
    """Create an error response."""
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message
        },
        "data": None
    }), status_code
