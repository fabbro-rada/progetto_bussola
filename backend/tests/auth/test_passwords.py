from bussola.auth import passwords


def test_hash_is_not_plaintext_and_verifies():
    h = passwords.hash_password("s3cret-pw")
    assert h != "s3cret-pw"
    assert passwords.verify_password(h, "s3cret-pw") is True


def test_wrong_password_does_not_verify():
    h = passwords.hash_password("s3cret-pw")
    assert passwords.verify_password(h, "wrong") is False


def test_same_password_hashes_differ_by_salt():
    assert passwords.hash_password("x") != passwords.hash_password("x")


def test_verify_on_garbage_hash_is_false_not_raises():
    assert passwords.verify_password("not-a-hash", "x") is False


def test_dummy_verify_does_not_raise():
    passwords.dummy_verify()
