#!/usr/bin/env python3
"""Script to find COTE_RUE_ID using the public API geobase."""
import json
import urllib.request

PUBLIC_API_GEOBASE_URL = "https://raw.githubusercontent.com/ludodefgh/planif-neige-public-api/main/data/geobase-map.json"


def search_address(street_name: str, street_number: int = None):
    """Search for an address in the public API geobase.

    Args:
        street_name: Name of the street (e.g., "something")
        street_number: Optional street number to filter by range
    """
    print("Downloading geobase from public API...")

    try:
        with urllib.request.urlopen(PUBLIC_API_GEOBASE_URL, timeout=30) as response:
            geobase = json.loads(response.read().decode())

        print(f"Loaded {len(geobase)} street segments from geobase\n")

        # Search for matching streets
        matches = []
        for cote_rue_id, info in geobase.items():
            nom_voie = info.get("nom_voie", "").lower()

            if street_name.lower() in nom_voie:
                # Check if street number is in range
                in_range = False
                if street_number:
                    debut = info.get("debut_adresse")
                    fin = info.get("fin_adresse")
                    if debut and fin:
                        try:
                            if int(debut) <= street_number <= int(fin):
                                in_range = True
                        except:
                            pass

                matches.append({
                    "cote_rue_id": cote_rue_id,
                    "info": info,
                    "in_range": in_range
                })

        # Sort: exact matches first, then by COTE_RUE_ID
        matches.sort(key=lambda x: (not x["in_range"], int(x["cote_rue_id"])))

        # Display results
        print(f"{'='*80}")
        print(f"Found {len(matches)} results for '{street_name}':")
        print(f"{'='*80}\n")

        for match in matches:
            cote_rue_id = match["cote_rue_id"]
            info = match["info"]
            in_range = match["in_range"]

            nom_voie = info.get("nom_voie", "")
            type_voie = info.get("type_voie", "")
            debut = info.get("debut_adresse")
            fin = info.get("fin_adresse")
            cote = info.get("cote", "")
            ville = info.get("nom_ville", "")

            marker = " ✓✓✓ EXACT MATCH! ✓✓✓" if in_range else ""

            print(f"COTE_RUE_ID: {cote_rue_id}{marker}")
            print(f"  Street: {type_voie} {nom_voie}")
            print(f"  Range: {debut} - {fin}")
            print(f"  Side: {cote}")
            print(f"  City: {ville}")
            print()

        # Summary
        exact_matches = [m for m in matches if m["in_range"]]
        if exact_matches and street_number:
            print(f"\n{'='*80}")
            print(f"SUMMARY - Best matches for {street_number} {street_name}:")
            print(f"{'='*80}\n")
            for match in exact_matches:
                cote_rue_id = match["cote_rue_id"]
                info = match["info"]
                type_voie = info.get("type_voie", "")
                nom_voie = info.get("nom_voie", "")
                debut = info.get("debut_adresse")
                fin = info.get("fin_adresse")
                cote = info.get("cote", "")

                print(f"  → Use COTE_RUE_ID: {cote_rue_id}")
                print(f"    {type_voie} {nom_voie} ({debut}-{fin})")
                print(f"    Side: {cote}")
                print()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Search for 1234 Avenue Something
    search_address("something", 1234)
