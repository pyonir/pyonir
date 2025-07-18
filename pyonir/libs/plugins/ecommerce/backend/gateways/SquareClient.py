from typing import List, Dict, Optional, Tuple
import uuid

from square.requests.checkout_options import CheckoutOptionsParams
from square.requests.order import OrderParams
from square.types.create_payment_link_response import CreatePaymentLinkResponse


class SquareClient:
    """
    Wraps Square's Checkout API to generate a hosted checkout link.

    Docs:
      - Create Payment Link: POST /v2/online-checkout/payment-links
        https://developer.squareup.com/reference/square/checkout-api/create-payment-link
    """

    def __init__(self, env_configs: dict, sandbox: bool = True):
        """
        Args:
            env_configs: Square configurations with access token (sandbox or production).
            sandbox: Whether to use sandbox or production environment.
        """
        from square import Square
        from square.environment import SquareEnvironment

        env = env_configs.get('sandbox' if sandbox else 'prod')
        self.client = Square(
            environment=SquareEnvironment.SANDBOX if sandbox else SquareEnvironment.PRODUCTION,
            token=env.get('access_token')
        )
        self.location_id = env.get('location_id')

    def create_checkout_order(
        self,
        line_items: List[Dict[str, any]],
        idempotency_key: Optional[str] = None,
        redirect_url: Optional[str] = None
    ) -> any:
        """checkout order"""

        res = self.client.orders.create(
            idempotency_key=idempotency_key,
            order={
                "location_id": self.location_id,
                "line_items": [
                    {
                        "quantity": "1",
                        "base_price_money": {
                            "amount": 1200,
                            "currency": "USD"
                        },
                        "name": "Hamburger",
                        "modifiers": [
                            {
                                "base_price_money": {
                                    "amount": 50,
                                    "currency": "USD"
                                },
                                "quantity": "2",
                                "name": "cheese"
                            }
                        ]
                    }
                ],
                # https://developer.squareup.com/docs/orders-api/apply-taxes-and-discounts
                "discounts": [
                    {
                        "uid": "EXPLICIT_DISCOUNT_UID",
                        "name": "Sale - $1.00 off",
                        "amount_money": {
                            "amount": 100,
                            "currency": "USD"
                        },
                        "scope": "ORDER"
                    }
                ],
                "taxes": [
                    {
                        "uid": "STATE_SALES_TAX_UID",
                        "scope": "ORDER",
                        "name": "State Sales Tax",
                        "percentage": "7.0"
                    }
                ],
                # "fulfillments": [
                #     {
                #         "type": "PICKUP",
                #         "state": "PROPOSED",
                #         "pickup_details": {
                #             "recipient": {
                #                 "display_name": "Jaiden Urie"
                #             },
                #             "expires_at": "2019-02-14T20:21:54.859Z",
                #             "auto_complete_duration": "P0DT1H0S",
                #             "schedule_type": "SCHEDULED",
                #             "pickup_at": "2019-02-14T19:21:54.859Z",
                #             "note": "Pour over coffee"
                #         }
                #     }
                # ]
            }
        )
        return res

    def create_checkout_link(
        self,
        line_items: List[Dict[str, any]],
        idempotency_key: Optional[str] = None,
        redirect_url: Optional[str] = None
    ) -> Tuple[bool, dict]:
        """
        Create a Square-hosted checkout URL.

        Args:
            line_items: List of line item dicts:
                {
                  "name": "T-shirt",
                  "quantity": "2",
                  "base_price_money": {"amount": 1500, "currency": "USD"}
                }
            idempotency_key: Unique key for creating the Order.
            redirect_url: Where Square redirects after payment.

        Returns:
            str: The 'url' field from the created PaymentLink response.
        """
        idempotency_key = idempotency_key or str(uuid.uuid4())
        # order_idempotency_key = order_idempotency_key or str(uuid.uuid4())
        # checkout_idempotency_key = checkout_idempotency_key or str(uuid.uuid4())
        order: OrderParams = {
                    "location_id": self.location_id,
                    "line_items": line_items,
                }
        checkout_options: CheckoutOptionsParams = {
            "ask_for_shipping_address": True
        }
        if redirect_url:
            checkout_options["redirect_url"] = redirect_url
        order["checkout_options"] = checkout_options
        response = self.client.checkout.payment_links.create(
                idempotency_key=str(uuid.uuid4()),
                order={
                    "location_id": self.location_id,
                    "line_items": [
                        {
                            "name": "60,000 mile maintenance",
                            "quantity": "1",
                            "base_price_money": {
                                "amount": 30000,
                                "currency": "USD"
                            },
                            "note": "1st line item note"
                        },
                        {
                            "name": "Tire rotation and balancing",
                            "quantity": "1",
                            "base_price_money": {
                                "amount": 15000,
                                "currency": "USD"
                            }
                        },
                        {
                            "name": "Wiper fluid replacement",
                            "quantity": "1",
                            "base_price_money": {
                                "amount": 1900,
                                "currency": "USD"
                            }
                        },
                        {
                            "name": "Oil change",
                            "quantity": "1",
                            "base_price_money": {
                                "amount": 2000,
                                "currency": "USD"
                            }
                        }
                    ]
                }
            )

        response = self.client.checkout.payment_links.create(
                idempotency_key=str(uuid.uuid4()),
                quick_pay={
                    "name": "Auto Detailing",
                    "price_money": {
                        "amount": 12500,
                        "currency": "USD"
                    },
                    "location_id": self.location_id
                },
                pre_populated_data={
                    "buyer_email": "buyer@email.com",
                    "buyer_phone_number": "1-415-555-1212",
                    "buyer_address": {
                        "address_line1": "1455 MARKET ST #600",
                        "country": "US",
                        "administrative_district_level1": "CA",
                        "locality": "San Jose",
                        "postal_code": "94103"
                    }
                },
                checkout_options={
                    "allow_tipping": True,
                    "ask_for_shipping_address": True,
                    "custom_fields": [
                        {
                            "title": "Special Instructions"
                        },
                        {
                            "title": "Would you like to be on mailing list"
                        }
                    ]
                }
            )

        response: CreatePaymentLinkResponse = self.client.checkout.payment_links.create(idempotency_key=idempotency_key, order=order)
        if response.errors:
            errors = response.errors
            print(f"Square API Error: {errors}")
            return False, {"errors": errors}

        return True, {"checkout_page_url": response.payment_link.url, "order_items": line_items, "order_id": response.payment_link.id}
