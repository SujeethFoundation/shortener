"""Azure Table Storage repository. RowKey is the immutable short code."""
from __future__ import annotations

import os
from heapq import nsmallest
from itertools import islice
from typing import Iterable
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError, ResourceModifiedError
from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import DefaultAzureCredential
from azure.core import MatchConditions
import base64


PARTITION = "links"

def row_key(code):
    return 'v1_' + base64.urlsafe_b64encode(code.encode('utf-8')).decode('ascii').rstrip('=')


class LinkStore:
    def __init__(self):
        table_name = os.getenv("SHORTLINKS_TABLE_NAME", "ShortLinks")
        endpoint = os.getenv("TABLES_ACCOUNT_URL")
        if endpoint:
            service = TableServiceClient(endpoint=endpoint, credential=DefaultAzureCredential())
        else:
            service = TableServiceClient.from_connection_string(os.environ["AzureWebJobsStorage"])
        self.table = service.create_table_if_not_exists(table_name)

    def get(self, code: str):
        try:
            entity = self.table.get_entity(PARTITION, row_key(code))
            result = dict(entity)
            result['_etag'] = entity.metadata['etag']
            return result
        except ResourceNotFoundError:
            return None

    def create(self, entity: dict) -> bool:
        try:
            item = dict(entity)
            item['Code'] = item['RowKey']
            item['RowKey'] = row_key(item['Code'])
            self.table.create_entity(item)
            return True
        except ResourceExistsError:
            return False

    def update(self, entity: dict):
        item = dict(entity)
        etag = item.pop('_etag')
        self.table.update_entity(item, mode=UpdateMode.REPLACE, etag=etag, match_condition=MatchConditions.IfNotModified)

    def list(self, search: str = "", limit: int = 250, sort: str = "") -> Iterable[dict]:
        rows = self.table.query_entities("PartitionKey eq 'links'", results_per_page=min(limit, 1000))
        needle = search.lower().strip()

        def matches():
            for row in rows:
                result = dict(row)
                if not needle or any(
                    needle in result.get(field, "").lower()
                    for field in ("Code", "DestinationUrl", "Description")
                ):
                    yield result

        field, _, direction = sort.partition("-")
        click_field = {"new": "ClickCount", "historical": "HistoricalClickCount"}.get(field)
        if click_field and direction in {"asc", "desc"}:
            sign = -1 if direction == "desc" else 1
            yield from nsmallest(
                limit, matches(),
                key=lambda row: (sign * int(row.get(click_field, 0)), row.get("Code", row["RowKey"])),
            )
        else:
            yield from islice(matches(), limit)

    def increment_click(self, code: str, now: str):
        for _ in range(4):
            entity = self.get(code)
            if not entity:
                return
            entity["ClickCount"] = int(entity.get("ClickCount", 0)) + 1
            entity["LastClickedOn"] = now
            try:
                self.update(entity)
                return
            except ResourceModifiedError:
                continue
