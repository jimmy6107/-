from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_end_to_end_order_flow():
    buyer = client.post(
        "/auth/register",
        json={"name": "Buyer", "email": "buyer@example.com", "line_user_id": "line-b"},
    ).json()

    seller_user = client.post(
        "/auth/register",
        json={"name": "Seller", "email": "seller@example.com", "line_user_id": "line-s"},
    ).json()

    application = client.post(
        "/seller/apply",
        json={
            "user_id": seller_user["id"],
            "company_name": "Demo Shop",
            "requested_role": "seller",
        },
    )
    assert application.status_code == 200
    app_data = application.json()

    paid = client.post(
        f"/seller/{app_data['id']}/deposit",
        json={"amount": app_data["required_deposit"]},
    )
    assert paid.status_code == 200

    order = client.post(
        "/orders",
        json={
            "buyer_id": buyer["id"],
            "seller_id": seller_user["id"],
            "item_name": "Phone Case",
            "quantity": 2,
            "unit_price": 300,
        },
    )
    assert order.status_code == 200
    order_data = order.json()

    for endpoint in ["accept", "ship", "logistics-receive", "arrive", "pickup"]:
        resp = client.post(f"/orders/{order_data['id']}/{endpoint}")
        assert resp.status_code == 200

    final_order = client.get(f"/orders/{order_data['id']}").json()
    assert final_order["status"] == "COMPLETED"

    notifications = client.get("/admin/notifications")
    assert notifications.status_code == 200
    assert len(notifications.json()) > 0
