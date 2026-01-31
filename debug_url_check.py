from playwright.sync_api import sync_playwright

def check_url():
    url = "https://yandex.ru/maps/org/auto_fix/203293742306"
    print(f"Checking URL: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=30000)
            print(f"Title: {page.title()}")
            print(f"URL after load: {page.url}")
            
            # Check for specific login elements
            if page.query_selector("input[name='login']") or "passport.yandex.ru" in page.url:
                print("🚨 DETECTED LOGIN PAGE")
            elif "maps/org" in page.url:
                 print("✅ Redirected to Public Map")
            else:
                 print("❓ Loaded unknown page")
                 
            # Dump minimal content
            print(f"Content snippet: {page.content()[:500]}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    check_url()
