import unittest

from server.signing import sign_result, verify_result


class SigningTests(unittest.TestCase):
    def test_round_trip(self):
        payload = {"v": 2, "score": 87, "bracha": "4"}
        token = sign_result(payload, "test-secret")
        self.assertEqual(verify_result(token, "test-secret"), payload)

    def test_tampering_fails(self):
        token = sign_result({"score": 87}, "test-secret")
        prefix, payload, signature = token.split(".")
        changed = ("A" if payload[0] != "A" else "B") + payload[1:]
        with self.assertRaises(ValueError):
            verify_result(f"{prefix}.{changed}.{signature}", "test-secret")

    def test_malformed_token_fails_cleanly(self):
        with self.assertRaises(ValueError):
            verify_result("not-a-token", "test-secret")


if __name__ == "__main__":
    unittest.main()
