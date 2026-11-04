from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import watch as w
from source_report import compare
from audit_sources import audit
from unittest.mock import patch

RULES = w.load(w.ROOT / 'config/rules.json')
NOW = datetime(2026, 11, 4, tzinfo=w.JST)

def source(key, publisher='号外NET', **fields):
    return {'id':key, 'name':key, 'publisher':publisher, 'url':'https://example.com/feed', 'method':'feed', 'enabled':True, **fields}

def article(url, category, title='地域の記事'):
    return {'title':title, 'url':url, 'published_at':None, 'source_categories':[category]}

class Feeds:
    def __init__(self, values): self.values=values
    def feed(self, s):
        result=self.values[s['id']]
        if isinstance(result, Exception): raise result
        return result

class SourceTests(unittest.TestCase):
    def test_source_scope_and_global_exclusions_both_apply(self):
        blog=source('blog','個人ブログ',include_categories=['沖縄イベント','沖縄本島中部'],exclude_categories=['兵庫県'])
        items=[article('https://example.com/ok','沖縄本島中部'),article('https://example.com/foreign','兵庫県'),
               article('https://example.com/unknown','不明'),article('https://example.com/politics','沖縄イベント','県知事の話題')]
        data, report=w.collect([blog],RULES,{'articles':[]},NOW,Feeds({'blog':items}))
        self.assertEqual(len(data['articles']),1)
        self.assertEqual(report['sources'][0]['excluded'],{'source_category:兵庫県':1,'source_category:not_included':1,'keyword:県知事':1})
        changed={**blog,'include_categories':['新しい対象']}
        revised, report=w.collect([changed],RULES,data,NOW,Feeds({'blog':[]}))
        self.assertEqual(revised['articles'],[])
        self.assertEqual(report['exclusions'][0]['reason'],'existing:source_category:not_included')

    def test_media_grouping_preserves_unique_urls_and_failure_isolation(self):
        sources=[source('naha'),source('uruma'),source('blog','個人ブログ'),source('failed','失敗元')]
        feeds=Feeds({'naha':[article('https://example.com/a','イベント')],
                     'uruma':[article('https://example.com/b','まち')],
                     'blog':[article('https://example.com/a?utm_source=duplicate','イベント'),article('https://example.com/c','Foods')],
                     'failed':URLError('offline')})
        data, report=w.collect(sources,RULES,{'articles':[]},NOW,feeds)
        self.assertEqual(report['publishers'],{'号外NET':2,'個人ブログ':1})
        self.assertEqual(report['sources'][2]['duplicate'],1)
        self.assertEqual(report['sources'][3]['status'],'failed')
        comparison=compare(data,{'sources':sources},['号外NET'],report)
        self.assertEqual(comparison['before']['publisher_count'],1)
        self.assertEqual(comparison['after']['publisher_count'],2)
        self.assertEqual(comparison['before']['event_percent'],50.0)
        self.assertEqual(comparison['after']['event_percent'],33.3)
        self.assertEqual(comparison['after']['food_percent'],33.3)
        self.assertEqual(comparison['after']['largest_publisher_percent'],66.7)
        self.assertEqual(len(comparison['samples']),1)
        display={'evaluated_on_jst':'2026-11-04','articles':[
            {'id':a['id'],'hidden_reason':None if a['publisher']=='号外NET' else 'old_unverified'} for a in data['articles']]}
        visible=compare(data,{'sources':sources},['号外NET'],report,display)
        self.assertEqual(visible['visible_before']['total'],2)
        self.assertEqual(visible['visible_after']['total'],2)
        self.assertEqual(visible['visible_after']['publisher_count'],1)

    def test_existing_records_gain_publisher_without_refreshing_first_seen(self):
        sources=[source('naha')]
        data, _=w.collect(sources,RULES,{'articles':[]},NOW,Feeds({'naha':[article('https://example.com/a','まち')]}))
        stamp=data['articles'][0]['collected_at']
        del data['articles'][0]['publisher']
        result, report=w.collect(sources,RULES,data,NOW,Feeds({'naha':URLError('offline')}))
        self.assertEqual(result['articles'][0]['publisher'],'号外NET')
        self.assertEqual(result['articles'][0]['collected_at'],stamp)
        self.assertEqual(report['publishers'],{'号外NET':1})
        self.assertEqual(compare({'articles':[]},{'sources':sources},['号外NET'])['after']['publisher_count'],0)

    def test_audit_skip_does_not_request_declined_source(self):
        with patch('audit_sources.AuditFetcher.feed',return_value=[]) as feed:
            result=audit([{'id':'declined','url':'https://example.com/feed','skip_reason':'terms pending'}, source('allowed')])
        self.assertEqual(feed.call_count,1)
        self.assertEqual(result['candidates'][0]['status'],'skipped')
        self.assertEqual(result['candidates'][0]['requests'],[])
        self.assertEqual(result['candidates'][1]['status'],'ok')

if __name__=='__main__': unittest.main()
