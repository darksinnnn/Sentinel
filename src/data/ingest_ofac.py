import pandas as pd
import requests
import xml.etree.ElementTree as ET
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
OFAC_PATH = "data/processed/ofac_sdn.parquet"

def download_and_parse_ofac():
    logger.info(f"Downloading OFAC SDN list from {SDN_URL}...")
    try:
        response = requests.get(SDN_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to download OFAC list: {e}")
        return

    logger.info("Parsing XML...")
    root = ET.fromstring(response.content)
    
    # The XML has a default namespace we need to handle
    namespace = {'ofac': 'https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML'}
    
    entries = []
    for sdn in root.findall('ofac:sdnEntry', namespace):
        uid = sdn.findtext('ofac:uid', default='', namespaces=namespace)
        last_name = sdn.findtext('ofac:lastName', default='', namespaces=namespace)
        first_name = sdn.findtext('ofac:firstName', default='', namespaces=namespace)
        sdn_type = sdn.findtext('ofac:sdnType', default='', namespaces=namespace)
        
        full_name = f"{first_name} {last_name}".strip()
        
        aliases = []
        aka_list = sdn.find('ofac:akaList', namespace)
        if aka_list is not None:
            for aka in aka_list.findall('ofac:aka', namespace):
                a_last = aka.findtext('ofac:lastName', default='', namespaces=namespace)
                a_first = aka.findtext('ofac:firstName', default='', namespaces=namespace)
                aliases.append(f"{a_first} {a_last}".strip())
                
        entries.append({
            'uid': uid,
            'name': full_name,
            'type': sdn_type,
            'aliases': "|".join(aliases)
        })
        
    df = pd.DataFrame(entries)
    
    # Ensure processed directory exists
    os.makedirs(os.path.dirname(OFAC_PATH), exist_ok=True)
    
    df.to_parquet(OFAC_PATH)
    logger.info(f"Saved {len(df)} OFAC SDN entries to {OFAC_PATH}")

if __name__ == "__main__":
    download_and_parse_ofac()
