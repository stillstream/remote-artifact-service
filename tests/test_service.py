from pathlib import Path
from fastapi.testclient import TestClient
from artifact_service.config import AppConfig, RootConfig
from artifact_service.main import create_app

def client_for(tmp_path):
    (tmp_path/'report.md').write_text('# Report',encoding='utf-8')
    (tmp_path/'data.bin').write_bytes(b'0123456789')
    outside=tmp_path.parent/'outside-secret.txt'; outside.write_text('secret')
    (tmp_path/'escape').symlink_to(outside)
    cfg=AppConfig('127.0.0.1',18765,(RootConfig('test','Test',tmp_path.resolve()),))
    return TestClient(create_app(cfg)),outside

def test_health_and_listing(tmp_path):
    c,_=client_for(tmp_path)
    assert c.get('/api/health').json()['ok'] is True
    names={x['name'] for x in c.get('/api/entries',params={'root_id':'test'}).json()['entries']}
    assert 'report.md' in names and 'escape' not in names

def test_path_guards(tmp_path):
    c,_=client_for(tmp_path)
    assert c.get('/api/file',params={'root_id':'test','path':'../outside-secret.txt'}).status_code==400
    assert c.get('/api/file',params={'root_id':'test','path':'escape'}).status_code==403
    assert c.get('/api/entries',params={'root_id':'test','path':'.git'}).status_code==404

def test_range(tmp_path):
    c,_=client_for(tmp_path)
    r=c.get('/api/file',params={'root_id':'test','path':'data.bin'},headers={'Range':'bytes=2-5'})
    assert r.status_code==206 and r.content==b'2345'
    assert r.headers['content-range']=='bytes 2-5/10'

def test_no_write_api(tmp_path):
    c,_=client_for(tmp_path)
    assert c.post('/api/file',json={'content':'overwrite'}).status_code in (404,405)
    assert (tmp_path/'report.md').read_text()=='# Report'
