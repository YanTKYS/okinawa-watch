import json
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

policy = json.loads((Path(__file__).resolve().parents[1] / 'config/rules.json').read_text())['display']

def article(title, slug, **values):
    return {'title': title, 'url': f'https://example.com/{slug}', 'source_name': '媒体',
            'published_at': '2026-11-03', 'collected_at': '2026-11-03T10:00:00+09:00',
            'topic': '催し・体験', 'region': None, 'labels': ['発見'], 'timing': None, **values}

fixtures = {'schema_version': 1, 'updated_at': '2026-11-04T00:01:00+09:00', 'display_policy': policy, 'articles': [
    article('終了済みの催し', 'ended', labels=['今だけ'], timing={'start':'2026-11-03','end':'2026-11-03'}),
    article('2026年11月4日限定の無料体験', 'current', published_at='2026-11-02', labels=['今だけ','お得'], timing={'start':'2026-11-04','end':'2026-11-04'}),
    article('<img src=x onerror=alert(1)>街の発見', 'discover', published_at=None, topic='街・暮らし'),
    article('11/8に開催する催し', 'fresh'),
    article('10月の古い催し', 'old', published_at='2026-10-01'),
    article('本日限定クーポン', 'old-deal', topic='買い物', published_at='2026-10-01', labels=['お得']),
    article('公開日不明の催し', 'old-collected', published_at=None, collected_at='2026-10-01', last_seen_at='2026-11-04'),
    article('掲載日不明の催し', 'unknown', published_at=None, collected_at=None)
]}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width':390,'height':844})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.clock.install(time=datetime.fromisoformat('2026-11-03T15:01:00+00:00'))
    page.route('**/articles.json', lambda route: route.fulfill(json=fixtures))
    page.goto('http://127.0.0.1:8000/site/')
    page.wait_for_selector('article')
    assert page.locator('article').count() == 3
    assert '終了済み' not in page.locator('#articles').inner_text()
    assert page.locator('#articles img').count() == 0
    assert '公開日不明' in page.locator('#articles').inner_text()
    assert '初回取得 2026/11/03' in page.locator('#articles').inner_text()
    page.get_by_role('button', name='今だけ', exact=True).click()
    assert page.locator('article').count() == 1
    assert page.locator('h3 a').get_attribute('href') == 'https://example.com/current'
    page.locator('#expired').check()
    assert page.locator('article').count() == 2
    page.locator('#expired').uncheck()
    page.locator('#topic').select_option('買い物')
    assert page.locator('article').count() == 0
    page.locator('#empty-events').click()
    assert page.locator('#topic').input_value() == ''
    assert page.locator('article').count() == 1
    assert '開催日未確認' in page.locator('article').inner_text()
    assert '開催中を保証しません' in page.locator('#filter-help').inner_text()
    page.locator('#older').check()
    assert page.locator('article').count() == 4
    assert '11/8に開催する催し' in page.locator('article').first.inner_text()
    assert '掲載日不明の催し' in page.locator('article').last.inner_text()
    page.get_by_role('button', name='すべて', exact=True).click()
    assert page.locator('article').count() == 7
    page.locator('#visibility-summary').click()
    assert page.locator('#visibility-log li').count() == 5
    assert '終了日を経過' in page.locator('#visibility-log').inner_text()
    assert '公開日・初回取得日が不明' in page.locator('#visibility-log').inner_text()
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
    assert not errors, errors
    print('PASS: unverified-event entry, empty-state shortcut, separate date labels, old/ended toggles, reason log, mobile width, safe titles')
    page.unroute('**/articles.json')
    page.goto('http://127.0.0.1:8000/site/')
    page.wait_for_selector('article')
    assert page.locator('article').count() == 17
    page.screenshot(path='work/issue-3-mobile.png', full_page=True)
    page.get_by_role('button', name='催し（日付未確認）', exact=True).click()
    assert page.locator('article').count() == 15
    assert '11/28・29' in page.locator('#articles').inner_text()
    page.set_viewport_size({'width':1280,'height':900})
    page.screenshot(path='work/issue-3-desktop.png', full_page=True)
    print('PASS: initial 20 articles, default 17, unverified-event entry 15')
    browser.close()
