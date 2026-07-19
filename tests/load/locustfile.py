from locust import HttpUser, between, task


class RedirectUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def redirect(self):
        self.client.get("/demo0001", name="redirect", allow_redirects=False)

    @task(1)
    def guest_rate_limit(self):
        self.client.post(
            "/api/v1/links", json={"url": "https://example.com/load-test"}, name="guest-create"
        )
