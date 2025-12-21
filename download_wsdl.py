#!/usr/bin/env python3
"""Télécharge le WSDL et tous les XSD associés."""

import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

base_url = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService"

# Télécharger le WSDL
print("Téléchargement du WSDL...")
r = requests.get(f"{base_url}?wsdl", headers=headers, timeout=30)
print(f"WSDL: {r.status_code}")
wsdl_content = r.text

# Télécharger XSD 1
print("Téléchargement de XSD 1...")
r1 = requests.get(f"{base_url}?xsd=1", headers=headers, timeout=30)
print(f"XSD 1: {r1.status_code}")

# Télécharger XSD 2
print("Téléchargement de XSD 2...")
r2 = requests.get(f"{base_url}?xsd=2", headers=headers, timeout=30)
print(f"XSD 2: {r2.status_code}")

# Modifier les références dans le WSDL pour pointer vers les fichiers locaux
wsdl_content = wsdl_content.replace(
    'schemaLocation="https://servicesenligne2.ville.montreal.qc.ca:443/api/infoneige/InfoneigeWebService?xsd=1"',
    'schemaLocation="file:///tmp/infoneige_xsd1.xsd"'
)
wsdl_content = wsdl_content.replace(
    'schemaLocation="https://servicesenligne2.ville.montreal.qc.ca:443/api/infoneige/InfoneigeWebService?xsd=2"',
    'schemaLocation="file:///tmp/infoneige_xsd2.xsd"'
)

# Modifier aussi les références dans XSD1 qui pointe vers XSD2
xsd1_content = r1.text.replace(
    'schemaLocation="https://servicesenligne2.ville.montreal.qc.ca:443/api/infoneige/InfoneigeWebService?xsd=2"',
    'schemaLocation="file:///tmp/infoneige_xsd2.xsd"'
)

# Sauvegarder tous les fichiers
with open('/tmp/infoneige.wsdl', 'w') as f:
    f.write(wsdl_content)

with open('/tmp/infoneige_xsd1.xsd', 'w') as f:
    f.write(xsd1_content)

with open('/tmp/infoneige_xsd2.xsd', 'w') as f:
    f.write(r2.text)

print("\n✅ Fichiers sauvegardés:")
print("   /tmp/infoneige.wsdl")
print("   /tmp/infoneige_xsd1.xsd")
print("   /tmp/infoneige_xsd2.xsd")
