from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_SHARD_COUNT = 3


@dataclass(frozen=True)
class ShardTarget:
    shard_id: int
    database_name: str


class ShardRouter:
    def __init__(self, shard_count: int = DEFAULT_SHARD_COUNT, base_database: str = "CampusTradingB") -> None:
        if shard_count <= 0:
            raise ValueError("shard_count must be positive")
        self.shard_count = shard_count
        self.base_database = base_database

    def shard_id_for(self, record_id: int) -> int:
        return record_id % self.shard_count

    def database_name_for(self, shard_id: int) -> str:
        return f"{self.base_database}_shard_{shard_id}"

    def target_for(self, record_id: int) -> ShardTarget:
        shard_id = self.shard_id_for(record_id)
        return ShardTarget(shard_id=shard_id, database_name=self.database_name_for(shard_id))

    def targets(self) -> Iterable[ShardTarget]:
        for shard_id in range(self.shard_count):
            yield ShardTarget(shard_id=shard_id, database_name=self.database_name_for(shard_id))


TABLE_ROUTING = {
    "Administrator": ("AdminID", "replicate"),
    "Member": ("MemberID", "partition"),
    "WishRequest": ("WishRequestID", "partition"),
    "Listing": ("ListingID", "partition"),
    "ListingImage": ("ImageID", "partition"),
    "Offer": ("OfferID", "partition"),
    "Transaction": ("TransactionID", "partition"),
    "MessageThread": ("ThreadID", "partition"),
    "Message": ("MessageID", "partition"),
    "Notification": ("NotificationID", "partition"),
    "Watchlist": ("WatchlistID", "partition"),
    "Report": ("ReportID", "partition"),
    "Rating": ("RatingID", "partition"),
    "Category": ("CategoryID", "replicate"),
}


def route_table_row(table_name: str, row_id: int, shard_count: int = DEFAULT_SHARD_COUNT) -> int:
    if table_name not in TABLE_ROUTING:
        raise KeyError(f"Unknown table: {table_name}")
    router = ShardRouter(shard_count=shard_count)
    _, strategy = TABLE_ROUTING[table_name]
    if strategy == "replicate":
        return 0
    return router.shard_id_for(row_id)


def describe_route(table_name: str, row_id: int, shard_count: int = DEFAULT_SHARD_COUNT) -> str:
    shard_id = route_table_row(table_name, row_id, shard_count=shard_count)
    if TABLE_ROUTING.get(table_name, (None, "partition"))[1] == "replicate":
        return f"{table_name}:{row_id} -> all shards"
    return f"{table_name}:{row_id} -> shard_{shard_id}"
