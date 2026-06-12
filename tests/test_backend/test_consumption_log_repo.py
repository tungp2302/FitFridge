from flaskr_new import consumption_log_repo as clr


def test_consumption_log_api_exists():
    assert callable(getattr(clr, "log_consume", None))
    assert callable(getattr(clr, "log_refill", None))
