from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="Ecommerce MVP API", version="0.1.0")


class UserRole(str, Enum):
    buyer = "buyer"
    seller = "seller"
    official_merchant = "official_merchant"


class OrderStatus(str, Enum):
    created = "CREATED"
    pending_payment = "PENDING_PAYMENT"
    paid = "PAID"
    accepted = "ACCEPTED"
    ready_to_ship = "READY_TO_SHIP"
    shipped = "SHIPPED"
    in_transit = "IN_TRANSIT"
    arrived_pickup_point = "ARRIVED_PICKUP_POINT"
    picked_up = "PICKED_UP"
    completed = "COMPLETED"


class MembershipLevel(str, Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    line_user_id: str = Field(..., description="LINE 綁定 ID")


class User(BaseModel):
    id: str
    name: str
    email: EmailStr
    line_user_id: str
    role: UserRole = UserRole.buyer
    points: int = 0
    membership_level: MembershipLevel = MembershipLevel.bronze


class SellerApplicationCreate(BaseModel):
    user_id: str
    company_name: str
    requested_role: Literal["seller", "official_merchant"] = "seller"


class SellerApplication(BaseModel):
    id: str
    user_id: str
    company_name: str
    requested_role: Literal["seller", "official_merchant"]
    approved: bool = False
    deposit_paid: bool = False
    required_deposit: int


class DepositPayRequest(BaseModel):
    amount: int


class OrderCreate(BaseModel):
    buyer_id: str
    seller_id: str
    item_name: str
    quantity: int = Field(gt=0)
    unit_price: int = Field(gt=0)


class Order(BaseModel):
    id: str
    order_no: str
    buyer_id: str
    seller_id: str
    item_name: str
    quantity: int
    unit_price: int
    total_amount: int
    status: OrderStatus
    status_log: List[str] = Field(default_factory=list)
    shipping_no: Optional[str] = None


class Notification(BaseModel):
    id: str
    user_id: str
    channel: Literal["line", "email", "in_app"]
    title: str
    content: str
    created_at: datetime


users: Dict[str, User] = {}
applications: Dict[str, SellerApplication] = {}
orders: Dict[str, Order] = {}
notifications: List[Notification] = []


def _update_membership(points: int) -> MembershipLevel:
    if points >= 5000:
        return MembershipLevel.gold
    if points >= 1000:
        return MembershipLevel.silver
    return MembershipLevel.bronze


def _notify(user_id: str, title: str, content: str) -> None:
    for channel in ["line", "email", "in_app"]:
        notifications.append(
            Notification(
                id=str(uuid4()),
                user_id=user_id,
                channel=channel,
                title=title,
                content=content,
                created_at=datetime.utcnow(),
            )
        )


def _must_user(user_id: str) -> User:
    user = users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _transition(order: Order, expected: OrderStatus, nxt: OrderStatus, message: str):
    if order.status != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {order.status} -> {nxt}, expected {expected}",
        )
    order.status = nxt
    order.status_log.append(f"{datetime.utcnow().isoformat()} {message}")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/register", response_model=User)
def register(payload: UserCreate):
    user = User(id=str(uuid4()), **payload.model_dump())
    users[user.id] = user
    return user


@app.post("/seller/apply", response_model=SellerApplication)
def apply_seller(payload: SellerApplicationCreate):
    _must_user(payload.user_id)
    required_deposit = 10000 if payload.requested_role == "seller" else 30000
    app_form = SellerApplication(
        id=str(uuid4()), required_deposit=required_deposit, **payload.model_dump()
    )
    app_form.approved = True
    applications[app_form.id] = app_form
    return app_form


@app.post("/seller/{application_id}/deposit", response_model=SellerApplication)
def pay_deposit(application_id: str, payload: DepositPayRequest):
    app_form = applications.get(application_id)
    if not app_form:
        raise HTTPException(status_code=404, detail="Application not found")
    if payload.amount < app_form.required_deposit:
        raise HTTPException(status_code=400, detail="Deposit amount insufficient")

    app_form.deposit_paid = True
    user = _must_user(app_form.user_id)
    user.role = (
        UserRole.seller
        if app_form.requested_role == "seller"
        else UserRole.official_merchant
    )
    _notify(user.id, "保證金繳納成功", "您已開通賣家權限")
    return app_form


@app.post("/orders", response_model=Order)
def create_order(payload: OrderCreate):
    buyer = _must_user(payload.buyer_id)
    seller = _must_user(payload.seller_id)
    if seller.role not in [UserRole.seller, UserRole.official_merchant]:
        raise HTTPException(status_code=400, detail="Target user is not an active seller")

    order_id = str(uuid4())
    order = Order(
        id=order_id,
        order_no=f"OD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        total_amount=payload.quantity * payload.unit_price,
        status=OrderStatus.paid,
        status_log=[f"{datetime.utcnow().isoformat()} 買家下單並完成付款"],
        **payload.model_dump(),
    )
    orders[order.id] = order
    _notify(buyer.id, "下單成功", f"訂單 {order.order_no} 已建立")
    _notify(seller.id, "您有新訂單", f"請處理訂單 {order.order_no}")
    return order


@app.post("/orders/{order_id}/accept", response_model=Order)
def accept_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _transition(order, OrderStatus.paid, OrderStatus.accepted, "賣家已接單")
    _transition(order, OrderStatus.accepted, OrderStatus.ready_to_ship, "建立物流單號")
    order.shipping_no = f"SH{datetime.utcnow().strftime('%H%M%S')}{order.id[:4]}"
    _notify(order.buyer_id, "訂單已接單", f"物流單號 {order.shipping_no}")
    return order


@app.post("/orders/{order_id}/ship", response_model=Order)
def ship_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _transition(order, OrderStatus.ready_to_ship, OrderStatus.shipped, "賣家已出貨")
    _notify(order.buyer_id, "賣家已出貨", f"訂單 {order.order_no} 已出貨")
    return order


@app.post("/orders/{order_id}/logistics-receive", response_model=Order)
def logistics_receive(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _transition(order, OrderStatus.shipped, OrderStatus.in_transit, "物流已收件")
    return order


@app.post("/orders/{order_id}/arrive", response_model=Order)
def arrive_pickup(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _transition(order, OrderStatus.in_transit, OrderStatus.arrived_pickup_point, "已到指定地點")
    _notify(order.buyer_id, "貨件已到店", f"訂單 {order.order_no} 可取貨")
    return order


@app.post("/orders/{order_id}/pickup", response_model=Order)
def pickup(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    _transition(order, OrderStatus.arrived_pickup_point, OrderStatus.picked_up, "買家已取貨")
    _transition(order, OrderStatus.picked_up, OrderStatus.completed, "訂單完成")

    buyer = _must_user(order.buyer_id)
    buyer.points += max(order.total_amount // 10, 1)
    buyer.membership_level = _update_membership(buyer.points)

    _notify(order.buyer_id, "訂單已完成", f"您已獲得積分 {max(order.total_amount // 10, 1)}")
    return order


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.get("/admin/orders", response_model=List[Order])
def admin_orders():
    return list(orders.values())


@app.get("/admin/seller-applications", response_model=List[SellerApplication])
def admin_seller_apps():
    return list(applications.values())


@app.get("/admin/notifications", response_model=List[Notification])
def admin_notifications():
    return notifications
