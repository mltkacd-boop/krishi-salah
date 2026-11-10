import json
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:5173"
bodies=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel="msedge",headless=True)
    pg=b.new_context(viewport={"width":1440,"height":960}).new_page()
    def on_req(r):
        if "/rag/answer" in r.url:
            bodies.append((r.method, r.url, r.post_data))
    pg.on("request", on_req)
    pg.goto(BASE+"/advisory",wait_until="networkidle")
    pg.click("button:has-text('हिं')")
    pg.fill("#advisory-query","धान का तना छेदक")
    pg.click("button[type=submit]")
    pg.wait_for_selector("[data-decision]",timeout=30000)
    pg.wait_for_timeout(800)
    print("request bodies sent by the UI:")
    for m,u,d in bodies:
        print(" ",m,u)
        print("  ",d)
    print("decision:",pg.get_attribute("[data-decision]","data-decision"))
    b.close()
