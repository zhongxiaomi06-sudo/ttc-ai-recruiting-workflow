import email
import unittest

import gmail_sync


class GmailSyncTests(unittest.TestCase):
    def test_safe_filename(self):
        result = gmail_sync.safe_filename("../../张三 简历.pdf")
        self.assertNotIn("..", result)
        self.assertNotIn("/", result)
        self.assertTrue(result.endswith(".pdf"))

    def test_decodes_filename_and_filters_extensions(self):
        raw = (
            b"Subject: Resume\r\n"
            b"MIME-Version: 1.0\r\n"
            b"Content-Type: multipart/mixed; boundary=x\r\n\r\n"
            b"--x\r\nContent-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=\"resume.pdf\"\r\n"
            b"Content-Transfer-Encoding: base64\r\n\r\nJVBERi0xLjQ=\r\n--x--\r\n"
        )
        message = email.message_from_bytes(raw)
        parts = list(gmail_sync.attachment_parts(message))
        self.assertEqual(parts[0][0], "resume.pdf")
        self.assertTrue(parts[0][1].startswith(b"%PDF"))

    def test_default_query_is_attachment_only(self):
        self.assertIn("has:attachment", gmail_sync.DEFAULT_QUERY)
        self.assertIn("filename:pdf", gmail_sync.DEFAULT_QUERY)
        self.assertIn("after:2026/07/06", gmail_sync.DEFAULT_QUERY)

    def test_target_role_filter(self):
        self.assertTrue(gmail_sync.TARGET_ROLE_TERMS.search("新消费品牌策略顾问"))
        self.assertFalse(gmail_sync.TARGET_ROLE_TERMS.search("前端技术专家"))


if __name__ == "__main__":
    unittest.main()
