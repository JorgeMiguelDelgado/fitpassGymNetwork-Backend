from django.http import HttpResponse


class DevelopmentCorsMiddleware:
    """Allow the separately hosted Flutter client during local development."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS" and request.path.startswith("/api/"):
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response
