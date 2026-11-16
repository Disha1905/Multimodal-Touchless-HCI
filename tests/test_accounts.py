import pytest
from security.accounts import AccountStore, AccountError


@pytest.fixture
def store(tmp_path):
    t = [1000.0]
    s = AccountStore(str(tmp_path / "access.json"), clock=lambda: t[0])
    s.t = t
    return s


def test_register_login_and_hashed_storage(store, tmp_path):
    code = store.register("Disha", "123456")
    assert store.login("disha", "123456")
    raw = (tmp_path / "access.json").read_text()
    assert "123456" not in raw and code not in raw


def test_validation(store):
    for u, p in [("ab", "123456"), ("bad name", "123456"), ("okname", "12345"), ("okname", "1234567890123"), ("okname", "12ab56")]:
        with pytest.raises(AccountError):
            store.register(u, p)


def test_lockout_after_five_failures(store):
    store.register("user1", "123456")
    for _ in range(5):
        with pytest.raises(AccountError):
            store.login("user1", "000000")
    with pytest.raises(AccountError, match="Try again"):
        store.login("user1", "123456")
    store.t[0] += 61
    assert store.login("user1", "123456")


def test_recovery_resets_pin(store):
    code = store.register("user1", "123456")
    new_code = store.recover("user1", code, "654321")
    assert store.login("user1", "654321")
    assert new_code != code
    with pytest.raises(AccountError):
        store.recover("user1", code, "111111")


def test_change_username_pin_and_recovery(store):
    store.register("Disha", "123456")
    assert store.change_username("Disha", "123456", "Disha2") == "Disha2"
    assert store.login("disha2", "123456")
    with pytest.raises(AccountError):
        store.login("disha", "123456")                   # old name gone
    store.change_pin("Disha2", "123456", "654321")
    assert store.login("Disha2", "654321")
    with pytest.raises(AccountError):
        store.change_pin("Disha2", "000000", "111111")   # wrong current PIN
    new_code = store.new_recovery_code("Disha2", "654321")
    assert store.recover("Disha2", new_code, "222222")


def test_change_username_rejects_duplicates_and_bad_names(store):
    store.register("alice1", "123456"); store.register("bob22", "123456")
    with pytest.raises(AccountError):
        store.change_username("bob22", "123456", "Alice1")
    with pytest.raises(AccountError):
        store.change_username("bob22", "123456", "x")
