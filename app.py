import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="VeraCore Order Status Checker",
    page_icon="📦",
    layout="wide"
)

class VeraCoreOrderClient:
    def __init__(self, base_url, system_id):
        self.base_url = base_url.rstrip('/')
        self.system_id = system_id
        self.token = None
    
    def authenticate(self, username, password):
        """Authenticate with the VeraCore API and get a token"""
        auth_url = f"{self.base_url}/api/Authentication"
        
        payload = {
            "userName": username,
            "password": password,
            "systemId": self.system_id
        }
        
        try:
            response = requests.post(auth_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('Token'):
                self.token = data['Token']
                return True, "Authentication successful"
            else:
                return False, f"Authentication failed: {data.get('Error', 'Unknown error')}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Authentication error: {str(e)}"
    
    def get_orders(self, status=None, carrier_code=None, start_date=None, end_date=None):
        """Get orders from the VeraCore API"""
        if not self.token:
            return None, "Not authenticated"
        
        orders_url = f"{self.base_url}/api/Orders"
        
        params = {}
        if status:
            params['request.status'] = status
        if carrier_code:
            params['request.carrierCode'] = carrier_code
        if start_date:
            params['request.streamAssignedUTCStartDate'] = start_date
        if end_date:
            params['request.streamAssignedUTCEndDate'] = end_date
        
        headers = {
            'Authorization': f'bearer {self.token}'
        }
        
        try:
            response = requests.get(orders_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json(), None
            
        except requests.exceptions.RequestException as e:
            return None, f"Error fetching orders: {str(e)}"

def parse_orders_to_dataframe(orders_data):
    """Convert orders data to a pandas DataFrame for display"""
    if not orders_data or 'Orders' not in orders_data:
        return pd.DataFrame()
    
    orders = orders_data['Orders']
    if not orders:
        return pd.DataFrame()
    
    rows = []
    for order in orders:
        ordered_by = order.get('OrderedBy', {})
        order_dates = order.get('OrderDates', {})
        shipments = order.get('Shipments', [])
        
        # Count total items
        total_items = 0
        carriers = set()
        for shipment in shipments:
            for unit in shipment.get('ShippingUnits', []):
                total_items += len(unit.get('Items', []))
                carrier = unit.get('RequestedFreightCarrier', 'N/A')
                if carrier:
                    carriers.add(carrier)
        
        row = {
            'Order ID': order['ID'],
            'Status': order['CurrentOrderStatus'],
            'Customer': ordered_by.get('Name', 'N/A'),
            'City': ordered_by.get('City', 'N/A'),
            'State': ordered_by.get('State', 'N/A'),
            'Order Date': order_dates.get('UTCOrderDate', 'N/A'),
            'Shipments': len(shipments),
            'Total Items': total_items,
            'Carriers': ', '.join(carriers) if carriers else 'N/A'
        }
        rows.append(row)
    
    return pd.DataFrame(rows)

def display_order_details(order):
    """Display detailed information about a single order"""
    st.subheader(f"Order #{order['ID']}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Status", order['CurrentOrderStatus'])
        order_dates = order.get('OrderDates', {})
        st.write(f"**Order Date:** {order_dates.get('UTCOrderDate', 'N/A')}")
    
    with col2:
        ordered_by = order.get('OrderedBy', {})
        st.write("**Customer Information:**")
        st.write(f"{ordered_by.get('Name', 'N/A')}")
        st.write(f"{ordered_by.get('Address1', 'N/A')}")
        st.write(f"{ordered_by.get('City', 'N/A')}, {ordered_by.get('State', 'N/A')} {ordered_by.get('PostalCode', 'N/A')}")
    
    with col3:
        shipments = order.get('Shipments', [])
        st.metric("Number of Shipments", len(shipments))
    
    # Display shipments
    st.write("---")
    st.write("**Shipment Details:**")
    
    for idx, shipment in enumerate(shipments, 1):
        with st.expander(f"Shipment {idx}", expanded=(len(shipments) == 1)):
            ship_to = shipment.get('ShipTo', {})
            st.write(f"**Ship To:** {ship_to.get('Name', 'N/A')}")
            st.write(f"{ship_to.get('Address1', 'N/A')}, {ship_to.get('City', 'N/A')}, {ship_to.get('State', 'N/A')} {ship_to.get('PostalCode', 'N/A')}")
            
            shipping_units = shipment.get('ShippingUnits', [])
            for unit_idx, unit in enumerate(shipping_units, 1):
                st.write(f"**Shipping Method:** {unit.get('RequestedShippingOption', 'N/A')}")
                st.write(f"**Carrier:** {unit.get('RequestedFreightCarrier', 'N/A')}")
                st.write(f"**Weight:** {unit.get('TotalWeight', 'N/A')} {unit.get('TotalWeightType', '')}")
                
                # Display items
                items = unit.get('Items', [])
                if items:
                    st.write("**Items:**")
                    for item in items:
                        products = item.get('Products', [])
                        for product in products:
                            col_a, col_b, col_c = st.columns([3, 1, 1])
                            with col_a:
                                st.write(f"• {item['Title']}")
                            with col_b:
                                st.write(f"Qty: {item['QuantityOrdered']}")
                            with col_c:
                                pricing = item.get('Pricing', {})
                                price = pricing.get('Price')
                                if price:
                                    st.write(f"${price}")

# Main app
def main():
    st.title("📦 VeraCore Order Status Checker")
    st.write("Check the status of orders from your VeraCore system")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        base_url = st.text_input(
            "Base URL",
            value="https://yourdomain.com/veracore/Public.api",
            help="Your VeraCore domain or RHU"
        )
        
        system_id = st.text_input(
            "System ID",
            value="abcoms",
            help="Your system ID for authentication"
        )
        
        username = st.text_input("Username", value="webuser")
        password = st.text_input("Password", value="webpass", type="password")
        
        st.divider()
        
        st.header("🔍 Filter Options")
        
        status = st.selectbox(
            "Order Status",
            options=["All", "Unprocessed", "Processed", "PartiallyShipped", "Complete", "Canceled"],
            index=0
        )
        
        carrier_code = st.text_input(
            "Carrier Code (optional)",
            placeholder="e.g., U11, R02",
            help="Leave empty for all carriers"
        )
        
        use_date_filter = st.checkbox("Filter by Date Range")
        
        start_date = None
        end_date = None
        
        if use_date_filter:
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                start_date_input = st.date_input(
                    "Start Date",
                    value=datetime.now().date() - timedelta(days=7)
                )
            with date_col2:
                end_date_input = st.date_input(
                    "End Date",
                    value=datetime.now().date()
                )
            
            start_date = f"{start_date_input}T00:00:00"
            end_date = f"{end_date_input}T23:59:59"
        
        st.divider()
        
        fetch_orders = st.button("🔄 Fetch Orders", type="primary", use_container_width=True)
    
    # Main content area
    if fetch_orders:
        with st.spinner("Authenticating..."):
            client = VeraCoreOrderClient(base_url, system_id)
            auth_success, auth_message = client.authenticate(username, password)
        
        if auth_success:
            st.success("✅ " + auth_message)
            
            with st.spinner("Fetching orders..."):
                orders_data, error = client.get_orders(
                    status=status if status != "All" else None,
                    carrier_code=carrier_code if carrier_code else None,
                    start_date=start_date,
                    end_date=end_date
                )
            
            if error:
                st.error(f"❌ {error}")
            elif orders_data:
                orders = orders_data.get('Orders', [])
                
                if orders:
                    st.success(f"✅ Found {len(orders)} order(s)")
                    
                    # Display summary table
                    st.subheader("Orders Summary")
                    df = parse_orders_to_dataframe(orders_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Download button for CSV
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download as CSV",
                        data=csv,
                        file_name=f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    # Detailed view
                    st.divider()
                    st.subheader("Order Details")
                    
                    selected_order = st.selectbox(
                        "Select an order to view details",
                        options=range(len(orders)),
                        format_func=lambda i: f"Order #{orders[i]['ID']} - {orders[i]['CurrentOrderStatus']}"
                    )
                    
                    if selected_order is not None:
                        display_order_details(orders[selected_order])
                else:
                    st.info("ℹ️ No orders found matching the criteria.")
            else:
                st.error("❌ No data received from API")
        else:
            st.error(f"❌ {auth_message}")
    else:
        st.info("👈 Configure your settings in the sidebar and click 'Fetch Orders' to begin.")
        
        # Display example/help information
        with st.expander("ℹ️ How to use this app"):
            st.write("""
            **Step 1:** Enter your VeraCore API credentials in the sidebar
            - Base URL: Your VeraCore domain
            - System ID: Your system identifier
            - Username and Password: Your API credentials
            
            **Step 2:** Configure your filters (optional)
            - Select order status
            - Enter carrier code if needed
            - Set date range if desired
            
            **Step 3:** Click 'Fetch Orders' to retrieve order information
            
            **Step 4:** View the summary table and download as CSV if needed
            
            **Step 5:** Select individual orders to see detailed information
            """)

if __name__ == "__main__":
    main()