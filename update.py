import csv
import requests
from io import StringIO
from datetime import date
#import mwclient
import os
import time
from playwright.sync_api import sync_playwright

SBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=0"
LBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=397188942"

WIKI_URL = "https://mcseedfinding.miraheze.org"

def load_csv(url):
    response = requests.get(url, timeout=30, allow_redirects=True)
    print(response.status_code)
    print(response.url)
    #print(response.text[:2000])
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
            "finder": row.get("Found By", "").strip(),
            "date": row.get("Date last broken", "").strip()
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
        "{{Biome Size Record",
        f"|name={name}"
    ]

    today = date.today().isoformat()

    if "sbr" in data:
        sbr = data["sbr"]

        lines.extend([
            f"|sbr_seed={sbr['seed']}",
            f"|sbr_coords={sbr['coords']}",
            f"|sbr_size={sbr['size']}",
            f"|sbr_finder={sbr['finder']}"
        ])
        if sbr['date']:
            lines.append(f"|sbr_date={sbr['date']}")

    if "lbr" in data:
        lbr = data["lbr"]

        lines.extend([
            f"|lbr_seed={lbr['seed']}",
            f"|lbr_coords={lbr['coords']}",
            f"|lbr_size={lbr['size']}",
            f"|lbr_finder={lbr['finder']}"
        ])
        if lbr['date']:
            lines.append(f"|lbr_date={lbr['date']}")

    lines.append("}}")
    lines.append("")

    return "\n".join(lines)

def generate_wiki_markup():
    biomes = {}

    ingest_sheet(load_csv(SBR_CSV_URL), biomes, "SBR")
    ingest_sheet(load_csv(LBR_CSV_URL), biomes, "LBR")

    output = [f"The contents of this page were automatically generated from [https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/edit?gid=0#gid=0] on {date.today().isoformat()}."]

    for biome in sorted(biomes):
        output.append(build_biome_template(biome, biomes[biome]))

    return "\n".join(output)

#import os
#import time
#from playwright.sync_api import sync_playwright

PASSWORD = os.environ["MW_PASSWORD"]

def run_bot(wiki_text: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{WIKI_URL}/wiki/Special:UserLogin")

        # Wait for page + any JS challenge
        page.wait_for_load_state("networkidle")

        # Fill login form
        page.fill('input[name="wpName"]', "MCAHBiomeRecordsBot")
        page.fill('input[name="wpPassword"]', PASSWORD)

        page.click('button[name="wploginattempt"]')

        # Wait for login to complete
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        page.goto(f"{WIKI_URL}/wiki/Largest_Biomes_Records?action=edit")
        page.wait_for_load_state("networkidle")

        textarea = page.locator("textarea#wpTextbox1")
        textarea.wait_for()

        textarea.fill(wiki_text)

        page.click("input#wpSave")

        # Wait for save completion
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print("Page updated successfully.")

        browser.close()

if __name__ == "__main__":
    wiki_text = generate_wiki_markup()
    run_bot(wiki_text)
    print("Written records")