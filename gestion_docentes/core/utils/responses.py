from django.http import JsonResponse

def success_response(data=None, message=""):
    """
    Generates a standardized successful JSON response.
    Payload will include a 'status', and optional 'data' and 'message' keys.
    """
    payload = {'status': 'success'}
    if data is not None:
        payload['data'] = data
    if message:
        payload['message'] = message
    return JsonResponse(payload, status=200)

def error_response(message, status_code=400):
    """
    Generates a standardized error JSON response.
    """
    return JsonResponse({'status': 'error', 'message': message}, status=status_code)

def not_found_response(message="El recurso solicitado no fue encontrado."):
    """
    Generates a standardized 404 Not Found error response.
    """
    return error_response(message, status_code=404)

def server_error_response(message="Ocurrió un error interno en el servidor."):
    """
    Generates a standardized 500 Internal Server Error response.
    """
    return error_response(message, status_code=500)
