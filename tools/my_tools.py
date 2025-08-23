from agents import function_tool

# Fake order database
ORDERS_DB = {
    "ORD123": "Shipped - Expected delivery in 3 days",
    "ORD456": "Processing - Will ship soon",
    "ORD789": "Delivered - Thank you for shopping!"
}

@function_tool(
    is_enabled=lambda query, **kwargs: "order" in query.lower(),
    error_function=lambda **kwargs: "Sorry, I couldn’t find that order. Please check your order ID."
)
async def get_order_status(order_id: str) -> str:
    """
    Fetch order status by order_id from a fake database.
    """
    status = ORDERS_DB.get(order_id)
    if status:
        return f"Order {order_id} status: {status}"
    else:
        # Trigger error_function
        return None
