from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from ..shared.http import api_login_required, error_response, parse_body
from .models import Product
from .services import purchase_product


@require_GET
def product_list(request):
    products = Product.objects.filter(active=True)
    return JsonResponse({"results": [{
        "id": item.id, "name": item.name, "kind": item.kind,
        "access_scope": item.access_scope, "gym_id": item.gym_id,
        "price": str(item.price), "currency": item.currency,
    } for item in products]})


@api_login_required
@require_POST
def buy_product(request, product_id):
    try:
        data = parse_body(request)
        purchase = purchase_product(
            request.user,
            get_object_or_404(Product, pk=product_id, active=True),
            data.get("payment_token", ""),
            data.get("promotion_code"),
        )
        return JsonResponse({
            "id": purchase.id, "status": purchase.status,
            "amount": str(purchase.amount), "currency": purchase.currency,
            "expires_at": purchase.expires_at.isoformat() if purchase.expires_at else None,
        }, status=201)
    except ValidationError as exc:
        return error_response(exc)
