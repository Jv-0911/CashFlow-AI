"""Register our optional marker without changing the shared pytest root."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "sandbox: explicit credentialed PayPal Sandbox integration tests "
        "(also requires RUN_PAYPAL_SANDBOX_TESTS=1)",
    )
