import csv
import requests
from io import StringIO
from datetime import date
import os
from urllib.parse import unquote
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

SBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=0"
LBR_CSV_URL = "https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/export?format=csv&gid=397188942"

WIKI_URL = "https://mcseedfinding.miraheze.org"
WIKI_API_URL = f"{WIKI_URL}/w/api.php"
WIKI_PAGE = "Largest Biomes Records"
BOT_USERNAME = "MCAHBiomeRecordsBot"
# Miraheze rejects the default Python requests user agent. Include a way to
# contact the bot operator, as requested by its user-agent policy.
BOT_USER_AGENT = (
    "MCAHBiomeRecordsBot/1.0 "
    "(https://github.com/picawawa4000/mcahbiomerecordsbot)"
)

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

    output = [
        f"The contents of this page were automatically generated from [https://docs.google.com/spreadsheets/d/1uiC9-eObIh16oEemAKQoRGp2elyv5nlDcnu_c5lxOtM/edit?gid=0#gid=0] on {date.today().isoformat()}.",
        "",
        "If you are reading this in dark mode and some of the biome titles are illegible due to their colours, try setting your browser to dark mode."
    ]

    for biome in sorted(biomes):
        output.append(build_biome_template(biome, biomes[biome]))

    return "\n".join(output)

def wiki_api(session, params, *, post=False):
    request = session.post if post else session.get
    response = request(
        WIKI_API_URL,
        data=params if post else None,
        params=None if post else params,
        timeout=30,
    )
    # Report edge diagnostics on read-only queries instead of an opaque 403.
    # Never print an authenticated response body in case it contains secrets.
    if response.status_code == 403 and not post and params.get("action") == "query":
        authenticated = "Authorization" in session.headers
        body = ("[suppressed for authenticated request]" if authenticated
                else " ".join(response.text.split())[:500])
        raise RuntimeError(
            "Wiki API rejected "
            f"{'authenticated' if authenticated else 'anonymous'} query: HTTP 403; "
            f"server={response.headers.get('Server', 'unknown')}; "
            f"cf-ray={response.headers.get('CF-Ray', 'none')}; "
            f"cf-mitigated={response.headers.get('CF-Mitigated', 'none')}; "
            f"content-type={response.headers.get('Content-Type', 'unknown')}; "
            f"body={body!r}"
        )
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        error = result["error"]
        raise RuntimeError(f"Wiki API error {error.get('code')}: {error.get('info')}")
    return result


def run_bot_browser(wiki_text: str, password: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.goto(
                f"{WIKI_URL}/wiki/Special:UserLogin",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # The login form may appear only after Cloudflare's JavaScript
            # check and CentralAuth's cross-domain redirects have completed.
            try:
                page.locator('input[name="wpName"]').wait_for(state="visible", timeout=90000)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "Browser never reached the wiki login form; Cloudflare may "
                    "require an interactive challenge. "
                    f"URL={page.url.partition('?')[0]!r}; title={page.title()!r}"
                ) from exc

            page.locator('input[name="wpName"]').fill(BOT_USERNAME)
            page.locator('input[name="wpPassword"]').fill(password)
            page.locator('button[name="wploginattempt"]').click(timeout=60000)
            try:
                page.wait_for_url(
                    lambda url: url.hostname == "mcseedfinding.miraheze.org",
                    timeout=60000,
                )
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "Browser login did not return to the wiki; "
                    f"URL={page.url.partition('?')[0]!r}; title={page.title()!r}"
                ) from exc

            article_url = f"{WIKI_URL}/wiki/{WIKI_PAGE.replace(' ', '_')}"
            page.goto(
                f"{article_url}?action=edit",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            textarea = page.locator("textarea#wpTextbox1")
            try:
                textarea.wait_for(state="visible", timeout=90000)
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "Browser never reached the wiki edit form; Cloudflare may "
                    "require an interactive challenge. "
                    f"URL={page.url.partition('?')[0]!r}; title={page.title()!r}"
                ) from exc

            # This page is anonymously editable, so a textarea alone does
            # not prove login. Check the account link and non-anonymous CSRF
            # token in the page HTML without touching the challenged API.
            account_link = page.locator("#pt-userpage a").first
            account_href = account_link.get_attribute("href") if account_link.count() else ""
            account_name = unquote(account_href or "").replace("_", " ")
            edit_token = page.locator('input[name="wpEditToken"]').first.input_value()
            if BOT_USERNAME not in account_name or edit_token == "+\\":
                raise RuntimeError(
                    "Browser login did not authenticate the bot account; "
                    f"URL={page.url.partition('?')[0]!r}; title={page.title()!r}"
                )

            textarea.fill(wiki_text)

            with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
                page.locator("input#wpSave").click()
            if page.url.partition("?")[0] != article_url or textarea.count():
                raise RuntimeError(
                    "Wiki did not return to the article after saving; "
                    f"URL={page.url.partition('?')[0]!r}; title={page.title()!r}"
                )
            print("Page updated successfully.")
        finally:
            browser.close()


def run_bot(wiki_text: str):
    # Prefer the browser when a password is configured: the API's anonymous
    # and OAuth requests can both be stopped by the Cloudflare edge challenge.
    password = os.environ.get("MW_PASSWORD")
    if password:
        run_bot_browser(wiki_text, password)
        return

    oauth_token = os.environ.get("MW_OAUTH_TOKEN")
    if not oauth_token:
        raise RuntimeError("Set MW_PASSWORD or MW_OAUTH_TOKEN")

    with requests.Session() as session:
        session.headers["User-Agent"] = BOT_USER_AGENT
        # An owner-only OAuth 2 token avoids storing the bot's password.
        # Keep the same session for all requests so CDN cookies persist.
        session.headers["Authorization"] = f"Bearer {oauth_token}"

        edit_info = wiki_api(session, {
            "action": "query", "meta": "tokens|userinfo", "type": "csrf",
            "prop": "revisions", "rvprop": "ids", "titles": WIKI_PAGE,
            "assert": "user", "format": "json",
        })["query"]
        if edit_info["userinfo"]["name"] != BOT_USERNAME:
            raise RuntimeError("Wiki credentials are not for the bot account")
        page = next(iter(edit_info["pages"].values()))
        if "missing" in page:
            raise RuntimeError(f"Wiki page does not exist: {WIKI_PAGE}")

        result = wiki_api(session, {
            "action": "edit",
            "title": WIKI_PAGE,
            "text": wiki_text,
            "baserevid": page["revisions"][0]["revid"],
            "token": edit_info["tokens"]["csrftoken"],
            "assert": "user",
            "format": "json",
        }, post=True)["edit"]
        if result.get("result") != "Success":
            raise RuntimeError(f"Wiki edit failed: {result.get('result', 'unknown result')}")
        print("Page updated successfully.")

if __name__ == "__main__":
    wiki_text = generate_wiki_markup()
    run_bot(wiki_text)
    print("Written records")
