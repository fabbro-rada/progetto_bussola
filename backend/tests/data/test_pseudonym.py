from bussola.data.pseudonym import generate_pseudonym


def test_has_prefix_and_hex_body():
    pid = generate_pseudonym()
    assert pid.startswith("P-")
    body = pid[2:]
    assert body and all(c in "0123456789abcdef" for c in body)


def test_within_profile_length_bounds():
    pid = generate_pseudonym()
    assert 1 <= len(pid) <= 64


def test_values_are_unique():
    values = {generate_pseudonym() for _ in range(1000)}
    assert len(values) == 1000
