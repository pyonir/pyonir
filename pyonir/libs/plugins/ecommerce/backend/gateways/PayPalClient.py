import requests
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class IAmount:
    value: int
    shipping: dict[str, object]
    handling: dict[str, object]
    discount: dict[str, object]
    currency_code: str = ''
    breakdown: str = ''

@dataclass
class Money:
    value: int
    currency_code: str = ''
    breakdown: str = ''
    shipping: dict = None
    handling: dict = None
    discount: dict = None

@dataclass
class PayPalItem:
    sku: str
    name: str
    price: int
    weight: int
    quantity: int
    category: str
    unit_amount: Money
    tax: Money

class PayPalOrder:
    items: list[PayPalItem]
    amount: IAmount
    reference_id: str

class PayPalClient:
    """
    A simple client for interacting with the PayPal Orders V2 API.
    Handles order creation, approval, and capture flows.

    Docs: https://developer.paypal.com/docs/api/orders/v2/
    """
    LIVE_IPN =  'https://ipnpb.paypal.com/cgi-bin/webscr' #(for live IPNs)
    LIVE_API_URL = 'https://api.paypal.com'
    LIVE_WEB_URL = 'https://www.paypal.com'
    SANDBOX_API_URL = 'https://api.sandbox.paypal.com'
    SANDBOX_WEB_URL = 'https://www.sandbox.paypal.com'
    SANDBOX_IPN = 'https://ipnpb.sandbox.paypal.com/cgi-bin/webscr' #(for Sandbox IPNs)

    def __init__(self, client_id: str, client_secret: str, sandbox: bool = True):
        """
        Initialize the PayPal client.

        Args:
            client_id (str): PayPal app client ID.
            client_secret (str): PayPal app secret.
            sandbox (bool): Use sandbox or live environment.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.base = "https://api-m.sandbox.paypal.com" if sandbox else "https://api-m.paypal.com"
        self._access_token: Optional[str] = None

    def _get_access_token(self) -> str:
        """
        Get a new OAuth 2.0 access token from PayPal.

        Docs: https://developer.paypal.com/api/rest/authentication/
        """
        if self._access_token:
            return self._access_token
        response = requests.post(
            f"{self.base}/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        """Prepare headers for authenticated requests to PayPal."""
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def create_checkout(
        self,
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        purchase_units: Optional[list] = None,
        intent: str = "CAPTURE",
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a new PayPal order.

        Args:
            return_url (Optional[str]): Where to send user after approval.
            cancel_url (Optional[str]): Where to send user if they cancel.
            purchase_units (Optional[list]): Full purchase_units override.
            intent (str): Either 'CAPTURE' or 'AUTHORIZE'.

        Returns:
            dict: JSON response from PayPal containing order ID and approval links.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders-create-request-body
        """
        body = {
            "intent": intent,
            "purchase_units": purchase_units
        }

        if return_url or cancel_url:
            body["application_context"] = {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "PAY_NOW"
            }

        response = requests.post(
            f"{self.base}/v2/checkout/orders",
            headers=self._headers(),
            json=body
        )
        print(response.text)
        res = response.json()
        order_status = res.get('status')
        if order_status == 'CREATED':
            order_id = res.get('id')
            checkout_url = f"{self.SANDBOX_WEB_URL}/checkoutnow?token={order_id}"
            return True, {
                "status": order_status,
                "order_id": order_id,
                "checkout_page_url": checkout_url,
                "order_items": purchase_units
            }
        self._get_access_token()
        return False, {"error": res}


    def capture_order(self, order_id: str) -> Dict[str, Any]:
        """
        Capture an approved order. Must be called after buyer approves.

        Args:
            order_id (str): The PayPal order ID returned during creation.

        Returns:
            dict: Capture result (transaction details, payer info, etc.).

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders-capture
        """
        response = requests.post(
            f"{self.base}/v2/checkout/orders/{order_id}/capture",
            headers=self._headers()
        ).json()
        print(response)
        return response

    @staticmethod
    def get_approval_link(order: Dict[str, Any]) -> Optional[str]:
        """
        Extract the buyer approval link from a create_order response.

        Args:
            order (dict): Response from create_order().

        Returns:
            str or None: Approval URL for redirecting the user to PayPal.

        Docs: https://developer.paypal.com/docs/api/orders/v2/#orders-create-response-body
        """
        for link in order.get("links", []):
            if link.get("rel") == "approve":
                return link["href"]
        return None
