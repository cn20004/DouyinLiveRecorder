import tempfile
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest
from src.douyin_live_monitor import DouyinEventStore, extract_douyin_web_rid
from src.utils import atomic_write_text

class ModTests(unittest.TestCase):
    def test_duplicate_room_event_is_stored_once(self):
        with tempfile.TemporaryDirectory() as d:
            store = DouyinEventStore(str(Path(d)/'test.db'))
            ev = {'roomId':'123','type':'room','ts':1000,'data':{'total':25,'totalUser':100}}
            store.save_event(ev); store.save_event(ev)
            with closing(sqlite3.connect(store.db_path)) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM douyin_events').fetchone()[0],1)
                self.assertEqual(conn.execute('SELECT online_total,total_user FROM douyin_room_stats').fetchall(),[(25,100)])
    def test_comment_and_control_messages(self):
        with tempfile.TemporaryDirectory() as d:
            store = DouyinEventStore(str(Path(d)/'test.db'))
            store.save_event({'id':'c1','roomId':'123','type':'chat','ts':1000,'user':{'nickname':'张三'},'data':{'content':'你好'}})
            store.save_event({'roomId':'123','type':'__connected'})
            with closing(sqlite3.connect(store.db_path)) as conn:
                self.assertEqual(conn.execute('SELECT nickname,content FROM douyin_events').fetchall(),[('张三','你好')])
    def test_atomic_write_preserves_previous_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'URL_config.ini'
            atomic_write_text(p,'live.douyin.com/123\n')
            atomic_write_text(p,'live.douyin.com/456\n')
            self.assertEqual(p.read_text(encoding='utf-8-sig'),'live.douyin.com/456\n')
            self.assertEqual(Path(str(p)+'.last_good').read_text(encoding='utf-8-sig'),'live.douyin.com/123\n')
            self.assertFalse(list(Path(d).glob('*.tmp')))
    def test_room_id(self):
        self.assertEqual(extract_douyin_web_rid('https://live.douyin.com/123456'), '123456')
        self.assertEqual(extract_douyin_web_rid('short',{'owner':{'web_rid':'789'}}),'789')
        self.assertIsNone(extract_douyin_web_rid('https://example.com'))

if __name__ == '__main__': unittest.main()
