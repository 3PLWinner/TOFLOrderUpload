import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os

# Page configuration
st.set_page_config(
    page_title="VeraCore Order Status Checker",
    page_icon="📦",
    layout="wide"
)

# Load credentials from environment variables
LOGIN_URL = os.getenv("LOGIN_URL", "https://wms.3plwinner.com/VeraCore/Public.Api")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
SYSTEM_ID = os.getenv("SYSTEM_ID")

class VeraCoreOrderClient:
    def __init__(self, base_url, system_id):
        self.base_url = base_url.rstrip('/')
        self.system_id = system_id
        self.token = None
        self.token_expiration = None
    
    def authenticate(self, username, password):
        """Authenticate with the VeraCore API and get a token"""
        login_url = f"{self.base_url}/api/login"
        
        payload = {
            "userName": username,
            "password": password,
            "systemId": self.system_id
        }
        
        try:
            response = requests.post(login_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data.get('Token'):
                self.token = data['Token']
                self.token_expiration = data.get('UtcExpirationDate')
                return True, f"Authentication successful. Token expires: {self.token_expiration}"
            else:
                error_msg = data.get('Error', 'Unknown error')
                return False, f"Authentication failed: {error_msg}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Authentication error: {str(e)}"
    
    def check_token_status(self):
        """Check if token is still valid"""
        if not self.token:
            return False, "No token available"
        
        status_url = f"{self.base_url}/api/token"
        headers = {"Authorization": f"bearer {self.token}"}
        
        try:
            response = requests.get(status_url, headers=headers, timeout=10)
            if response.status_code == 200:
                status = response.json()
                is_valid = "valid" in str(status).lower()
                return is_valid, f"Token status: {status}"
            return False, f"Token check failed: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Token check error: {str(e)}"
    
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
        if order.get('PurchaseOrder'):
            st.write(f"**PO:** {order['PurchaseOrder']}")
    
    with col2:
        ordered_by = order.get('OrderedBy', {})
        st.write("**Customer Information:**")
        st.write(f"{ordered_by.get('Name', 'N/A')}")
        st.write(f"{ordered_by.get('Address1', 'N/A')}")
        st.write(f"{ordered_by.get('City', 'N/A')}, {ordered_by.get('State', 'N/A')} {ordered_by.get('PostalCode', 'N/A')}")
        if ordered_by.get('Email'):
            st.write(f"**Email:** {ordered_by['Email']}")
        if ordered_by.get('Phone'):
            st.write(f"**Phone:** {ordered_by['Phone']}")
    
    with col3:
        shipments = order.get('Shipments', [])
        st.metric("Number of Shipments", len(shipments))
        order_class = order.get('OrderClassification', {})
        if order_class.get('OrderProcessingStream'):
            st.write(f"**Stream:** {order_class['OrderProcessingStream']}")
    
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
                st.write(f"**Carrier:** {unit.get('RequestedFreightCarrier', 'N/A')} ({unit.get('RequestedFreightCode', 'N/A')})")
                st.write(f"**Weight:** {unit.get('TotalWeight', 'N/A')} {unit.get('TotalWeightType', '')}")
                
                # Display items
                items = unit.get('Items', [])
                if items:
                    st.write("**Items:**")
                    items_data = []
                    for item in items:
                        products = item.get('Products', [])
                        for product in products:
                            pricing = item.get('Pricing', {})
                            price = pricing.get('Price', 0)
                            qty = item['QuantityOrdered']
                            
                            items_data.append({
                                'Line': item.get('LineNumber', ''),
                                'Product ID': item['ID'],
                                'Title': item['Title'],
                                'Quantity': qty,
                                'Price': f"${price:.2f}" if price else 'N/A',
                                'Total': f"${price * qty:.2f}" if price else 'N/A'
                            })
                    
                    items_df = pd.DataFrame(items_data)
                    st.dataframe(items_df, use_container_width=True, hide_index=True)
            
            # Display return address
            return_addr = shipment.get('ReturnAddress', {})
            if return_addr.get('Company') or return_addr.get('Address1'):
                st.write("**Return Address:**")
                st.write(f"{return_addr.get('Company', 'N/A')}")
                st.write(f"{return_addr.get('Address1', '')}, {return_addr.get('City', '')}, {return_addr.get('State', '')} {return_addr.get('PostalCode', '')}")

# Initialize session state
if 'client' not in st.session_state:
    st.session_state.client = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'orders_data' not in st.session_state:
    st.session_state.orders_data = None

# Main app
def main():
    st.title("📦 VeraCore Order Status Checker")
    
    # Check for required environment variables
    if not all([LOGIN_URL, USERNAME, PASSWORD, SYSTEM_ID]):
        st.error("⚠️ Missing environment variables. Please configure LOGIN_URL, USERNAME, PASSWORD, and SYSTEM_ID.")
        st.stop()
    
    # Auto-authenticate on first load
    if not st.session_state.authenticated:
        with st.spinner("Authenticating..."):
            client = VeraCoreOrderClient(LOGIN_URL, SYSTEM_ID)
            auth_success, auth_message = client.authenticate(USERNAME, PASSWORD)
        
        if auth_success:
            st.session_state.client = client
            st.session_state.authenticated = True
            st.success(f"✅ {auth_message}")
        else:
            st.error(f"❌ {auth_message}")
            st.stop()
    
    # Filters in main area
    st.subheader("🔍 Filter Orders")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status = st.selectbox(
            "Order Status",
            options=["All", "Unprocessed", "Processed", "PartiallyShipped", "Complete", "Canceled"],
            index=0
        )
    
    with col2:
        carrier_code = st.text_input(
            "Carrier Code (optional)",
            placeholder="e.g., U11, R02",
            help="Leave empty for all carriers"
        )
    
    with col3:
        use_date_filter = st.checkbox("Filter by Date Range")
    
    start_date = None
    end_date = None
    
    if use_date_filter:
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            start_date_input = st.date_input(
                "Start Date",
                value=datetime.now().date() - timedelta(days=7)
            )
        with col_date2:
            end_date_input = st.date_input(
                "End Date",
                value=datetime.now().date()
            )
        
        start_date = f"{start_date_input}T00:00:00"
        end_date = f"{end_date_input}T23:59:59"
    
    # Fetch button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
    with col_btn1:
        fetch_orders = st.button("🔄 Fetch Orders", type="primary", use_container_width=True)
    with col_btn2:
        if st.button("🔍 Check Token", use_container_width=True):
            is_valid, status_msg = st.session_state.client.check_token_status()
            if is_valid:
                st.success(f"✅ Token is valid")
            else:
                st.warning(f"⚠️ {status_msg}")
    
    st.divider()
    
    # Fetch and display orders
    if fetch_orders:
        with st.spinner("Fetching orders..."):
            orders_data, error = st.session_state.client.get_orders(
                status=status if status != "All" else None,
                carrier_code=carrier_code if carrier_code else None,
                start_date=start_date,
                end_date=end_date
            )
        
        if error:
            st.error(f"❌ {error}")
        elif orders_data:
            st.session_state.orders_data = orders_data
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
    
    elif st.session_state.orders_data:
        # Display previously fetched data
        orders = st.session_state.orders_data.get('Orders', [])
        if orders:
            st.info(f"Showing {len(orders)} previously fetched order(s). Click 'Fetch Orders' to refresh.")
            
            df = parse_orders_to_dataframe(st.session_state.orders_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
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
        st.info("👆 Select your filters and click 'Fetch Orders' to begin.")

if __name__ == "__main__":
    main()