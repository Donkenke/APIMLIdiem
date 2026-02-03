"""
Utilities for fetching and processing tender data from Mercado Público APIs
"""
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

def fetch_ocds_tender_detail(code: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed tender information from OCDS API (no ticket required)
    
    Args:
        code: Tender code (e.g., "1506-85-O125")
        
    Returns:
        Dictionary with tender details or None if failed
    """
    try:
        url = f"https://api.mercadopublico.cl/APISOCDS/OCDS/tender/{code}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching OCDS details for {code}: {e}")
    
    return None

def fetch_category_details(category_code: str) -> Optional[Dict[str, Any]]:
    """
    Fetch category details from OCDS API
    
    Args:
        category_code: UNSPSC category code (e.g., "102104083")
        
    Returns:
        Dictionary with category details or None if failed
    """
    try:
        url = f"http://api.mercadopublico.cl/APISOCDS/Productos/Categoria/{category_code}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching category {category_code}: {e}")
    
    return None

def extract_items_from_ocds(ocds_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract and enrich items from OCDS tender data
    
    Args:
        ocds_data: OCDS tender data dictionary
        
    Returns:
        List of enriched item dictionaries
    """
    items = []
    
    try:
        releases = ocds_data.get('releases', [])
        if not releases:
            return items
        
        tender = releases[0].get('tender', {})
        tender_items = tender.get('items', [])
        
        for item in tender_items:
            classification = item.get('classification', {})
            category_id = classification.get('id', '')
            
            enriched_item = {
                'id': item.get('id'),
                'description': item.get('description'),
                'quantity': item.get('quantity'),
                'unit': item.get('unit', {}).get('name', 'N/A'),
                'classification_id': category_id,
                'classification_scheme': classification.get('scheme', ''),
                'classification_uri': classification.get('uri', '')
            }
            
            # Fetch category details if available
            if category_id:
                category_details = fetch_category_details(category_id)
                if category_details:
                    enriched_item['category_name'] = category_details.get('NombreCategoria', 'N/A')
                    enriched_item['category_products'] = category_details.get('Productos', [])
            
            items.append(enriched_item)
    
    except Exception as e:
        print(f"Error extracting items from OCDS: {e}")
    
    return items

def extract_buyer_info(ocds_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract buyer information from OCDS data
    
    Args:
        ocds_data: OCDS tender data dictionary
        
    Returns:
        Dictionary with buyer information
    """
    buyer_info = {}
    
    try:
        releases = ocds_data.get('releases', [])
        if releases:
            buyer = releases[0].get('buyer', {})
            buyer_info = {
                'name': buyer.get('name', 'N/A'),
                'id': buyer.get('id', 'N/A')
            }
            
            # Get address if available
            address = buyer.get('address', {})
            if address:
                buyer_info['region'] = address.get('region', 'N/A')
                buyer_info['locality'] = address.get('locality', 'N/A')
                buyer_info['street'] = address.get('streetAddress', 'N/A')
    
    except Exception as e:
        print(f"Error extracting buyer info: {e}")
    
    return buyer_info

def extract_tender_value(ocds_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract tender value information from OCDS data
    
    Args:
        ocds_data: OCDS tender data dictionary
        
    Returns:
        Dictionary with value information or None
    """
    try:
        releases = ocds_data.get('releases', [])
        if releases:
            tender = releases[0].get('tender', {})
            value = tender.get('value', {})
            
            if value:
                return {
                    'amount': value.get('amount'),
                    'currency': value.get('currency', 'CLP')
                }
    
    except Exception as e:
        print(f"Error extracting tender value: {e}")
    
    return None

def extract_tender_period(ocds_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract tender period information from OCDS data
    
    Args:
        ocds_data: OCDS tender data dictionary
        
    Returns:
        Dictionary with period information
    """
    period_info = {}
    
    try:
        releases = ocds_data.get('releases', [])
        if releases:
            tender = releases[0].get('tender', {})
            tender_period = tender.get('tenderPeriod', {})
            
            period_info = {
                'start_date': tender_period.get('startDate'),
                'end_date': tender_period.get('endDate'),
                'duration_days': tender_period.get('durationInDays')
            }
    
    except Exception as e:
        print(f"Error extracting tender period: {e}")
    
    return period_info

def extract_documents(ocds_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract document information from OCDS data
    
    Args:
        ocds_data: OCDS tender data dictionary
        
    Returns:
        List of document dictionaries
    """
    documents = []
    
    try:
        releases = ocds_data.get('releases', [])
        if releases:
            tender = releases[0].get('tender', {})
            tender_docs = tender.get('documents', [])
            
            for doc in tender_docs:
                documents.append({
                    'id': doc.get('id'),
                    'title': doc.get('title', 'Sin título'),
                    'description': doc.get('description', 'Sin descripción'),
                    'format': doc.get('format', 'N/A'),
                    'date_published': doc.get('datePublished'),
                    'url': doc.get('url')
                })
    
    except Exception as e:
        print(f"Error extracting documents: {e}")
    
    return documents

def get_enriched_tender_data(code: str) -> Dict[str, Any]:
    """
    Get fully enriched tender data combining OCDS API information
    
    Args:
        code: Tender code
        
    Returns:
        Dictionary with enriched tender data
    """
    ocds_data = fetch_ocds_tender_detail(code)
    
    if not ocds_data:
        return {}
    
    enriched_data = {
        'code': code,
        'items': extract_items_from_ocds(ocds_data),
        'buyer': extract_buyer_info(ocds_data),
        'value': extract_tender_value(ocds_data),
        'period': extract_tender_period(ocds_data),
        'documents': extract_documents(ocds_data),
        'raw_ocds': ocds_data
    }
    
    return enriched_data

def format_classification_info(item: Dict[str, Any]) -> str:
    """
    Format classification information for display
    
    Args:
        item: Item dictionary with classification info
        
    Returns:
        Formatted string
    """
    parts = []
    
    if 'category_name' in item:
        parts.append(f"📂 {item['category_name']}")
    
    if 'classification_id' in item:
        parts.append(f"🔢 Código: {item['classification_id']}")
    
    if 'description' in item:
        parts.append(f"📝 {item['description']}")
    
    return " | ".join(parts) if parts else "Sin información de clasificación"
