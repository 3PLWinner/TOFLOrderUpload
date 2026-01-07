import streamlit as st
import requests
import pandas as pd
import datetime
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(dotenv_path=Path('.env'), override=True)

st.logo("3plwinner-logo.png", size="large", link="https://3plwinner.com")

st.set_page_config(page_title="Order Upload")

st.title("Order Upload System")

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

def escape_xml(text):
    """Escape special characters for XML"""
    if not text or pd.isna(text):
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text

def generate_order_xml(username, password, order_id, offers):
    """Generate XML for order submission"""
    
    offers_xml = ""
    for offer in offers:
        offers_xml += f"""
                    <OfferOrdered>
                        <Offer>
                            <Header>
                                <ID>{escape_xml(offer['Offer ID'])}</ID>
                            </Header>
                        </Offer>
                        <Quantity>{int(offer['Quantity'])}</Quantity>
                        <OrderShipTo>
                            <Key>1</Key>
                        </OrderShipTo>
                    </OfferOrdered>"""
    
    first = offers[0]
    
    ref_nums = [str(o['Reference #']) for o in offers if o['Reference #']]
    ref_string = ",".join(ref_nums)[:50] if ref_nums else ""
    
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
    xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <soap:Header>
        <AuthenticationHeader xmlns="http://omscom/">
            <Username>{USERNAME}</Username>
            <Password>{PASSWORD}</Password>
        </AuthenticationHeader>
    </soap:Header>
    <soap:Body>
        <AddOrder xmlns="http://omscom/">
            <order>
                <Header>
                    <ID>{escape_xml(str(order_id))}</ID>
                    <EntryDate>{datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}</EntryDate>
                    <Comments>{escape_xml(first.get('Order Comments', ''))}</Comments>
                    <ReferenceNumber>{escape_xml(ref_string)}</ReferenceNumber>
                </Header>
                <Money></Money>
                <Payment></Payment>
                <OrderVariables>
                    <OrderVariable>
                        <VariableField>
                            <FieldName>Order Type</FieldName>
                        </VariableField>
                        <Value>True</Value>
                        <ValueDescription>SFDWInc</ValueDescription>
                    </OrderVariable>
                </OrderVariables>
                <Shipping>
                    <FreightCarrier>
                        <Name>{escape_xml(first.get('Freight Carrier', ''))}</Name>
                    </FreightCarrier>
                </Shipping>
                <OrderedBy>
                    <FirstName>{escape_xml(first.get('First Name', ''))}</FirstName>
                    <LastName>{escape_xml(first.get('Last Name', ''))}</LastName>
                    <Address1>{escape_xml(first.get('Address 1', ''))}</Address1>
                    <Address2>{escape_xml(first.get('Address 2', ''))}</Address2>
                    <Address3>{escape_xml(first.get('Address 3', ''))}</Address3>
                    <City>{escape_xml(first.get('City', ''))}</City>
                    <State>{escape_xml(first.get('State', ''))}</State>
                    <PostalCode>{escape_xml(str(first.get('Postal Code', '')))}</PostalCode>
                    <Country>{escape_xml(first.get('Country', ''))}</Country>
                </OrderedBy>
                <ShipTo>
                    <OrderShipTo>
                        <Flag>OrderedBy</Flag>
                        <Key>1</Key>
                    </OrderShipTo>
                </ShipTo>
                <BillTo>
                    <Flag>OrderedBy</Flag>
                </BillTo>
                <Offers>
                    {offers_xml}
                </Offers>
            </order>
        </AddOrder>
    </soap:Body>
</soap:Envelope>"""

uploaded_file = st.file_uploader("Upload Order CSV File", type=['csv'])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()
        df = df.fillna("")
        
        st.success(f"✅ File uploaded successfully: {uploaded_file.name}")
        
        with st.expander("📋 View Uploaded Data", expanded=True):
            st.dataframe(df, use_container_width=True)
        
        required_cols = ['Order ID', 'Offer ID', 'First Name', 'Last Name', 'Address 1', 
                         'City', 'State', 'Postal Code', 'Country', 'Quantity', 'Freight Carrier']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"Missing Required Columns: {', '.join(missing_cols)}")
            st.info(f"**Available columns in your file:** {', '.join(df.columns)}")
            st.stop()
        
        grouped = df.groupby(['Order ID', 'Offer ID'], as_index=False).agg({
            'First Name': 'first',
            'Last Name': 'first',
            'Address 1': 'first',
            'Address 2': 'first',
            'Address 3': 'first',
            'City': 'first',
            'State': 'first',
            'Postal Code': 'first',
            'Country': 'first',
            'Quantity': 'sum',
            'Freight Carrier': 'first',
            'Reference #': 'first',
            'Order Comments': 'first'
        })
        
        #with st.expander("View Grouped Orders (Combined Line Items)"):
            #st.dataframe(grouped, use_container_width=True)
        
        unique_orders = grouped['Order ID'].unique()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Orders", len(unique_orders))
        col2.metric("Total Line Items", len(grouped))
        col3.metric("Total Quantity", int(grouped['Quantity'].sum()))
        
        st.markdown("---")
        
        if st.button("Submit All Orders", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = {
                'success': [],
                'failed': [],
                'error_details': []
            }
            
            for idx, order_id in enumerate(unique_orders):
                status_text.text(f"Processing order {idx + 1} of {len(unique_orders)}: {order_id}")
                
                order_offers = grouped[grouped['Order ID'] == order_id].to_dict('records')
                xml = generate_order_xml(USERNAME, PASSWORD, str(order_id), order_offers)
                
                try:
                    response = requests.post(
                        "https://rhu335.veracore.com/pmomsws/OMS.asmx",
                        data=xml.encode('utf-8'),
                        headers={
                            'Content-Type': 'text/xml; charset=utf-8',
                            'SOAPAction': 'http://omscom/AddOrder'
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        if 'soap:Fault' not in response.text:
                            results['success'].append(str(order_id))
                        else:
                            results['failed'].append(str(order_id))
                            
                            fault_string = ""
                            if '<faultstring>' in response.text:
                                start = response.text.find('<faultstring>') + 13
                                end = response.text.find('</faultstring>')
                                fault_string = response.text[start:end]
                            
                            results['error_details'].append({
                                'order_id': str(order_id),
                                'status': response.status_code,
                                'error': fault_string if fault_string else 'SOAP Fault (see details)',
                                'full_response': response.text,
                                'offers': order_offers
                            })
                    else:
                        results['failed'].append(str(order_id))
                        results['error_details'].append({
                            'order_id': str(order_id),
                            'status': response.status_code,
                            'error': f'HTTP Error {response.status_code}',
                            'full_response': response.text,
                            'offers': order_offers
                        })
                        
                except Exception as e:
                    results['failed'].append(str(order_id))
                    results['error_details'].append({
                        'order_id': str(order_id),
                        'status': 'Exception',
                        'error': str(e),
                        'full_response': '',
                        'offers': order_offers
                    })
                
                progress_bar.progress((idx + 1) / len(unique_orders))
            
            status_text.empty()
            progress_bar.empty()
            
            st.markdown("---")
            st.subheader("📊 Submission Results")
            
            col1, col2 = st.columns(2)
            col1.metric("✅ Successfully Submitted", len(results['success']), delta=None, delta_color="normal")
            col2.metric("❌ Failed", len(results['failed']), delta=None, delta_color="inverse")
            
            if len(results['failed']) == 0:
                st.success("🎉 All orders submitted successfully!")
                with st.expander("✅ View Successful Orders"):
                    for order_id in results['success']:
                        st.text(f"• Order ID: {order_id}")
            else:
                st.error(f"⚠️ {len(results['failed'])} order(s) failed to submit. Please review the errors below.")
                
                if results['success']:
                    with st.expander("✅ View Successful Orders"):
                        for order_id in results['success']:
                            st.text(f"• Order ID: {order_id}")
                
                st.markdown("### ❌ Failed Orders - Detailed Error Report")
                
                for error_detail in results['error_details']:
                    with st.expander(f"🔴 Order ID: {error_detail['order_id']} - Status: {error_detail['status']}", expanded=True):
                        st.error(f"**Error:** {error_detail['error']}")
                        
                        st.markdown("**Order Details:**")
                        error_df = pd.DataFrame(error_detail['offers'])
                        st.dataframe(error_df, use_container_width=True)
                        
                        st.markdown("**Full Server Response:**")
                        st.code(error_detail['full_response'], language='xml')
                        
                        st.markdown("**Troubleshooting Tips:**")
                        if 'InvalidLogin' in error_detail['error']:
                            st.warning("• Check that your API credentials are correct")
                        elif 'Offer' in error_detail['error'] or 'Product' in error_detail['error']:
                            st.warning("• Verify that all Product/Offer IDs exist in the system")
                        elif 'Address' in error_detail['error']:
                            st.warning("• Check that all address fields are properly filled")
                        else:
                            st.warning("• Contact support with this error message")
                
                failed_df = pd.DataFrame([{
                    'Order ID': e['order_id'],
                    'Status': e['status'],
                    'Error Summary': e['error'][:100] + '...' if len(e['error']) > 100 else e['error']
                } for e in results['error_details']])
                
                st.markdown("### 📥 Download Failed Orders Report")
                csv = failed_df.to_csv(index=False)
                st.download_button(
                    label="Download Error Report (CSV)",
                    data=csv,
                    file_name=f"failed_orders_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
    
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.info("Please ensure your CSV file is properly formatted and try again.")

else:
    st.info("👆 Please upload a CSV file to begin")
    
    st.markdown("---")
    st.subheader("📝 CSV File Requirements")
    
    st.markdown("""
    Your CSV file must include the following columns:
    
    **Required Columns:**
    - Order ID
    - First Name
    - Last Name
    - Address 1
    - City
    - State
    - Postal Code
    - Country
    - Offer ID (Product ID)
    - Quantity
    - Freight Carrier

    **Optional Columns:**
    - Address 2
    - Address 3
    - Reference #
    - Order Comments
    """)