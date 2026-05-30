import csv
import requests
from io import StringIO
from datetime import date
import mwclient
import os

SBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=0"
LBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=789012"

def load_csv(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return list(csv.DictReader(StringIO(response.text)))

def ingest_sheet(rows, biomes, record_type):
    for row in rows:
        biome = row.get("Biome", "").strip()

        if not biome:
            continue

        if biome not in biomes:
            biomes[biome] = {}

        entry = {
            "seed": row.get("Seed", "").strip(),
            "coords": f"{row.get('X', '').strip()}, {row.get('Z', '').strip()}",
            "size": row.get("Blocks^2", "").strip(),
            "finder": row.get("Found By", "").strip()
        }

        if record_type == "SBR":
            biomes[biome]["sbr"] = entry

        elif record_type == "LBR":
            # Skip empty LBR records
            if entry["seed"]:
                biomes[biome]["lbr"] = entry

def build_biome_template(name, data):
    lines = [
        f"== {name} ==",
        "",
        "{{Biome",
        f"|name={name}"
    ]

    today = date.today().isoformat()

    if "sbr" in data:
        sbr = data["sbr"]

        lines.extend([
            f"|sbr_seed={sbr['seed']}",
            f"|sbr_coords={sbr['coords']}",
            f"|sbr_size={sbr['size']}",
            f"|sbr_finder={sbr['finder']}",
            f"|sbr_date={today}"
        ])

    if "lbr" in data:
        lbr = data["lbr"]

        lines.extend([
            f"|lbr_seed={lbr['seed']}",
            f"|lbr_coords={lbr['coords']}",
            f"|lbr_size={lbr['size']}",
            f"|lbr_finder={lbr['finder']}",
            f"|lbr_date={today}"
        ])

    lines.append("}}")
    lines.append("")

    return "\n".join(lines)

def generate_wiki_markup():
    biomes = {}

    ingest_sheet(load_csv(SBR_CSV_URL), biomes, "SBR")
    ingest_sheet(load_csv(LBR_CSV_URL), biomes, "LBR")

    output = []

    for biome in sorted(biomes):
        output.append(build_biome_template(biome, biomes[biome]))

    return "\n".join(output)

def write_records(data):
    site = mwclient.Site("minecraftathome.miraheze.org", path="/wiki/")
    site.login("MCAHBiomeRecordsBot", os.environ["MW_PASSWORD"])

    page = site.pages["Largest Biome Records"]
    current = page.text()
    if current != data:
        page.save(data, summary="Automated Records Update")

if __name__ == "__main__":
    wiki_text = generate_wiki_markup()
    write_records(wiki_text)
    print("Written records")