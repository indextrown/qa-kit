"""안드로이드 라이브 화면 H.264: Annex-B를 NAL로 나누기 · 닫힌 연결 알아채기 (기기 없이)"""
import socket
import unittest

from helpers import load_qakit

q = load_qakit()


class Nals(unittest.TestCase):
    def test_split_keeps_unfinished_tail(self):
        sps, pps, idr = b"\x67\x42\x00\x1f", b"\x68\xce", b"\x65\x88\x84"
        buf = b"\x00\x00\x00\x01" + sps + b"\x00\x00\x00\x01" + pps + b"\x00\x00\x01" + idr + b"\x00\x00\x00\x01\x41\x9a"
        nals, rest = q.h264_nals(buf)
        self.assertEqual(nals, [sps, pps, idr])
        self.assertEqual(rest, b"\x00\x00\x00\x01\x41\x9a")   # 끝나지 않은 NAL은 다음 조각과 이어 붙인다
        more, _ = q.h264_nals(rest + b"\x00\x00\x01\x41")
        self.assertEqual(more, [b"\x41\x9a"])


class PeerGone(unittest.TestCase):
    def test_closed_peer(self):
        a, b = socket.socketpair()
        with a, b:
            self.assertFalse(q.peer_gone(a))
            b.close()
            self.assertTrue(q.peer_gone(a))


if __name__ == "__main__":
    unittest.main()
