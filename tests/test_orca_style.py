"""Orca 방식 피드백: 달라진 줄만 · 헛조작 감지 · 확인됨/확인 안 됨 · 입력 다시 읽기 · 오류 코드 · screen 좁히기 (기기 없이)"""
import os
import unittest
from unittest import mock

from helpers import load_qakit, make_workspace

q = load_qakit()


def el(type_, label="", id_="", x=0, y=0, w=10, h=10, depth=1, value=""):
    return {"type": type_, "id": id_, "labelRaw": label, "x": x, "y": y, "w": w, "h": h, "depth": depth, "value": value}


def screen(*els):
    return {"screen": {"w": 400, "h": 800}, "elements": [el("Other", "", "root", 0, 0, 400, 800, 0), *els]}


HOME = screen(el("Button", "메뉴", "menuButton", 300, 700, 48, 48),
              el("StaticText", "S -", "sog", 10, 70, 60, 20),
              el("Cell", "", "list", 0, 100, 400, 300),
              el("StaticText", "내 선박", "", 10, 110, 200, 40, 2),
              el("StaticText", "검색", "", 10, 160, 200, 40, 2))


class Diff(unittest.TestCase):
    def test_keys_ignore_position_and_value(self):
        moved = screen(el("Button", "메뉴", "menuButton", 300, 600, 48, 48), *HOME["elements"][2:])
        diff, same = q.screen_diff(q.screen_rows(HOME), q.screen_rows(moved))
        self.assertEqual(len(diff), 1)
        self.assertTrue(diff[0].startswith("~ Button #menuButton"))
        self.assertEqual(same, len(q.screen_rows(moved)) - 1)

    def test_added_and_removed(self):
        after = screen(*HOME["elements"][1:5], el("Button", "닫기", "close", 350, 110, 32, 32))
        diff, _ = q.screen_diff(q.screen_rows(HOME), q.screen_rows(after))
        self.assertIn("+ Button #close \"닫기\" @350,110 32x32", diff)
        self.assertTrue(any(d.startswith("- ") and "검색" in d for d in diff))

    def test_big_change_sends_whole_screen(self):
        other = screen(el("Button", "a", "a"), el("Button", "b", "b"), el("Button", "c", "c"), el("Button", "d", "d"))
        diff, _ = q.screen_diff(q.screen_rows(HOME), q.screen_rows(other))
        self.assertIsNone(diff)


class Session(unittest.TestCase):
    def setUp(self):
        self.tmp, root = make_workspace()
        self.s = q.McpSession(q.find_workspace(str(root)))
        self.env = mock.patch.dict(os.environ, {"QAKIT_AI_AUTOSCREEN": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def feed(self, *screens):
        it = iter(screens)
        return mock.patch.object(self.s, "read_rows", side_effect=lambda settle: (lambda p: (p, q.screen_rows(p)))(next(it)))

    def test_noop_tap_is_unverified(self):
        with self.feed(HOME, HOME), mock.patch.object(q.time, "sleep"):
            out = self.s.after_screen(pre=q.screen_rows(HOME))
        self.assertIn("확인 안 됨", out)

    def test_changed_screen_is_verified_and_diffed(self):
        self.s.seen_rows = q.screen_rows(HOME)
        sheet = screen(*HOME["elements"][1:], el("Button", "닫기", "close", 350, 110, 32, 32))
        with self.feed(sheet):
            out = self.s.after_screen(pre=q.screen_rows(HOME))
        self.assertIn("달라진 줄만", out)
        self.assertIn("+ Button #close", out)
        self.assertIn("확인됨: 화면 바뀜", out)
        self.assertNotIn("#menuButton", out)   # 그대로인 줄은 다시 보내지 않음

    def test_field_readback(self):
        typed = screen(el("TextField", "", "email", 10, 100, 300, 40, value="aa@b.coaa@b.co"))
        with self.feed(typed):
            out = self.s.after_screen(field=({"id": "email"}, "aa@b.co"))
        self.assertIn("두 번 들어감", out)
        with self.feed(typed):
            out = self.s.after_screen(field=({"id": "email"}, "{secret:EMAIL}"))
        self.assertNotIn("입력칸", out)

    def test_error_code_attached(self):
        with mock.patch.object(self.s, "do", return_value=(False, "❌ 10초 안에 나타나지 않음: { id: x }")):
            out, err = self.s.call("wait_for", {"target": "x"})
        self.assertTrue(err)
        self.assertIn("오류 코드: not_found", out[-1]["text"])

    def test_screen_query_and_under(self):
        with self.feed(HOME, HOME):
            _, found = self.s.screen(query="검색")
            _, under = self.s.screen(under="list")
        self.assertIn("검색", found)
        self.assertNotIn("menuButton", found)
        self.assertIn("내 선박", under)
        self.assertNotIn("menuButton", under)
        self.assertIsNone(self.s.seen_rows)   # 좁혀 본 것은 '본 화면'으로 치지 않음


class Codes(unittest.TestCase):
    def test_codes(self):
        self.assertIn("ambiguous_target", q.failure_code("같은 대상이 2개 — …"))
        self.assertIn("covered", q.failure_code("가운데를 Button 가 덮고 있음"))
        self.assertIn("no_effect", q.failure_code("탭 뒤 기대 효과가 나타나지 않음 (탭이 무시됐거나 …)"))
        self.assertIn("bad_step", q.failure_code("알 수 없는 단계: {…}"))
        self.assertIn("step_failed", q.failure_code("???"))


class Suggest(unittest.TestCase):
    def test_contains_condition_does_not_crash(self):
        msg = '기대 조건 실패: {"contains":{"target":{"type":"textfield"},"text":"abc"}}'
        self.assertEqual(q.suggestion_lines(msg, "Application @0,0 10x10\n  TextField #a @0,0 5x5"), [])


if __name__ == "__main__":
    unittest.main()
