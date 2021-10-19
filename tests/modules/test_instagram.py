import unittest

from src.modules.instagram import parse_instagram_post_id


class ParseInstagramPostId(unittest.TestCase):
    def test_parsing(self):
        cases = [
            ['', None],
            ['hello', None],
            ['http://www.instagram.com/p/CH6lZbgFWhK', 'CH6lZbgFWhK'],
            ['https://www.instagram.com/p/CH6lZbgFWhK/', 'CH6lZbgFWhK'],
            ['https://www.instagram.com/p/CH6lZbgFWhK/?utm_source=ig_web_copy_link', 'CH6lZbgFWhK'],
            ['https://www.instagram.com/p/CH6lZbgFWhK/media/?size=l', 'CH6lZbgFWhK'],
            ['instagram.com/p/CH6lZbgFWhK/media/?size=l', 'CH6lZbgFWhK'],
            ['pretext http://www.instagram.com/p/CH6lZbgFWhK post text', 'CH6lZbgFWhK'],
            ['http://www.instagram.com/p/CH6lZbgFWhK https://www.instagram.com/p/CH6lZbgFWh2', 'CH6lZbgFWhK'],
            ['http://www.instagram.com/p/CH6lZbgFWhK, https://www.instagram.com/p/CH6lZbgFWh2', 'CH6lZbgFWhK'],
            ['http://www.instagram.com/p/CH6lZbgFWhK.https://www.instagram.com/p/CH6lZbgFWh2', 'CH6lZbgFWhK'],
            ['https://www.instagram.com/angelinajolie_offiicial/p/CBnwdW5n2VA/', 'CBnwdW5n2VA'],
            ['https://www.instagram.com/p/CKegLpJF_1-/', 'CKegLpJF_1-'],
            ['https://www.instagram.com/tv/CB2-q8knR-7/?igshid=bswpfh0cglb', 'CB2-q8knR-7'],
            ['https://www.instagram.com/reel/CKVMQ9dg-hJ/?igshid=1tuvggc2qv85b', 'CKVMQ9dg-hJ'],
        ]
        for value, expected in cases:
            self.assertEqual(parse_instagram_post_id(value), expected)


if __name__ == '__main__':
    unittest.main()
