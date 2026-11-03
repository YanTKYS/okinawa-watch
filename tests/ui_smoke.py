import json
from playwright.sync_api import sync_playwright

fixtures = {'schema_version':1, 'updated_at':'2026-11-04T00:01:00+09:00', 'articles':[
 {'title':'終了済みの催し','url':'https://example.com/expired','source_name':'媒体A','published_at':'2026-11-03','collected_at':'2026-11-03T10:00:00+09:00','topic':'催し・体験','region':'那覇市','labels':['今だけ'],'timing':{'start':'2026-11-03','end':'2026-11-03'}},
 {'title':'2026年11月4日限定の無料体験','url':'https://example.com/current','source_name':'媒体B','published_at':'2026-11-02','collected_at':'2026-11-03T10:00:00+09:00','topic':'催し・体験','region':None,'labels':['今だけ','お得'],'timing':{'start':'2026-11-04','end':'2026-11-04'}},
 {'title':'<img src=x onerror=alert(1)>街の発見','url':'https://example.com/discover','source_name':'媒体C','published_at':None,'collected_at':'2026-11-03T10:00:00+09:00','topic':'街・暮らし','region':None,'labels':['発見'],'timing':None}
]}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':844})
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.clock.install(time=__import__('datetime').datetime.fromisoformat('2026-11-03T15:01:00+00:00'))
    page.route('**/articles.json', lambda route:route.fulfill(json=fixtures))
    page.goto('http://127.0.0.1:8000/site/')
    page.wait_for_selector('article')
    assert page.locator('article').count()==2
    assert '終了済み' not in page.locator('#articles').inner_text()
    assert page.locator('#articles img').count()==0
    page.get_by_role('button',name='今だけ',exact=True).click()
    assert page.locator('article').count()==1
    assert page.locator('h3 a').get_attribute('href')=='https://example.com/current'
    page.locator('#expired').check()
    assert page.locator('article').count()==2
    page.get_by_role('button',name='発見',exact=True).click()
    assert page.locator('article').count()==1
    assert '取得 2026/11/03' in page.locator('article').inner_text()
    page.locator('#topic').select_option('催し・体験')
    assert page.locator('article').count()==0
    assert page.locator('#empty').is_visible()
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not errors,errors
    print('PASS: JST date boundary, expired toggle, category/topic filters, safe title rendering, original link, acquired date fallback, empty state, mobile width')
    page.unroute('**/articles.json')
    page.goto('http://127.0.0.1:8000/sample-site/')
    page.wait_for_selector('article')
    page.screenshot(path='work/mobile-preview.png',full_page=True)
    page.set_viewport_size({'width':1280,'height':900})
    page.screenshot(path='work/desktop-preview.png',full_page=True)
    browser.close()
