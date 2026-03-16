from django.http import JsonResponse


def success(data=None, message="success"):
    return JsonResponse({"code": 0, "message": message, "data": data})


def error(message="error", code=1, status=200):
    return JsonResponse({"code": code, "message": message, "data": None}, status=status)
