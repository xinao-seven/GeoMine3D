from rest_framework.views import exception_handler
from .response import error


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return error(str(exc), code=response.status_code, status=response.status_code)
    return error("Internal Server Error", code=500, status=500)
