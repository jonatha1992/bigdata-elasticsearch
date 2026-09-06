"""Integration checks for the local Docker lab; requires the running stack."""

import base64
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


class LocalStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        settings = dict(
            line.split("=", 1)
            for line in (root / ".env").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        )
        token = base64.b64encode(
            ("elastic:" + settings["ELASTIC_PASSWORD"]).encode()
        ).decode()
        cls.authorization = "Basic " + token

    def request(self, path, *, port=9200, method="GET", body=None, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = self.authorization
        data = None if body is None else json.dumps(body).encode()
        request = Request(
            f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method
        )
        with urlopen(request, timeout=30) as response:
            return response.status, response.read()

    def test_elasticsearch_requires_authentication(self):
        with self.assertRaises(HTTPError) as caught:
            self.request("/", auth=False)
        self.assertEqual(caught.exception.code, 401)

    def test_elasticsearch_version_and_health(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["version"]["number"], "9.5.3")
        _, body = self.request("/_cluster/health")
        health = json.loads(body)
        self.assertIn(health["status"], ("green", "yellow"))
        self.assertEqual(health["number_of_nodes"], 1)

    def test_kibana_is_available_and_serves_login(self):
        status, body = self.request("/api/status", port=5601)
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertEqual(state["version"]["number"], "9.5.3")
        self.assertEqual(state["status"]["overall"]["level"], "available")
        status, body = self.request("/login", port=5601, auth=False)
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body.lower())

    def test_index_search_and_aggregation(self):
        index = "lab-smoke-" + uuid4().hex
        self.request(
            "/" + index,
            method="PUT",
            body={
                "settings": {"number_of_shards": 1, "number_of_replicas": 0},
                "mappings": {
                    "properties": {
                        "product": {"type": "text"},
                        "amount": {"type": "integer"},
                    }
                },
            },
        )
        try:
            for identifier, product, amount in (
                ("1", "red shoes", 120),
                ("2", "blue shoes", 80),
            ):
                self.request(
                    f"/{index}/_doc/{identifier}?refresh=wait_for",
                    method="PUT",
                    body={"product": product, "amount": amount},
                )
            _, body = self.request(
                f"/{index}/_search",
                method="POST",
                body={
                    "query": {"match": {"product": "shoes"}},
                    "aggs": {"total": {"sum": {"field": "amount"}}},
                },
            )
            result = json.loads(body)
            self.assertEqual(result["hits"]["total"]["value"], 2)
            self.assertEqual(result["aggregations"]["total"]["value"], 200)
        finally:
            self.request("/" + index, method="DELETE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
