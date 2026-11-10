from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:5173"
paths=["/","/advisory","/knowledge-base","/safety-guidelines","/project-info"]
with sync_playwright() as p:
    b=p.chromium.launch(channel="msedge",headless=True)
    for w,h in ((390,844),(1440,960)):
        ctx=b.new_context(viewport={"width":w,"height":h},is_mobile=w<500,has_touch=w<500)
        pg=ctx.new_page()
        for path in paths:
            pg.goto(BASE+path,wait_until="networkidle")
            pg.wait_for_timeout(900)
            sw=pg.evaluate("document.documentElement.scrollWidth")
            cw=pg.evaluate("document.documentElement.clientWidth")
            print(f"{w}px {path:18} scrollWidth={sw} clientWidth={cw} overflow={'YES' if sw>cw+1 else 'no'}")
        ctx.close()
    b.close()
