# Campus Trading App - Assignment 4 Sharding Implementation Report

- GitHub repository link: [Campus Trading App](https://github.com/Zeenu03/Campus_Trading_App)
- Video link: To be added

## 1. Shard Key Chosen and Justification

I used a primary-key modulo shard key with the rule `shard_id = record_id mod 3`.

I chose this because it fits the way the app is used and it is easy to reason about:

- High cardinality: the primary keys are unique and naturally spread across a large value space.
- Query-aligned: the app often looks up listings, offers, transactions, threads, and user-owned data by ID.
- Stable: primary keys do not change after insertion, so the routing stays consistent.

Modulo routing also gives a fairly even spread, since consecutive IDs fall across all three shards. The data set we used ended up close to balanced as well; for example, listing rows were distributed as 41 / 42 / 42 and transactions as 40 / 41 / 40 across the three shards.

## 2. Partitioning Strategy Used and Why

The project uses hash-style modulo partitioning instead of range-based or directory-based partitioning.

This was the best fit for the assignment because:

- It is deterministic and easy to explain.
- It keeps shard selection O(1) for a known ID.
- It avoids the skew that can happen when all low or high ID ranges land on one shard.
- It matches the course requirement to simulate sharding using multiple databases on the same server.

The shard databases are:

- `CampusTradingB_shard_0`
- `CampusTradingB_shard_1`
- `CampusTradingB_shard_2`

The central routing logic is defined in the backend router:

```go
func (r *Router) ShardIDFor(recordID int) int {
	if r == nil || r.shardCount <= 0 {
		return 0
	}
	shardID := recordID % r.shardCount
	if shardID < 0 {
		shardID += r.shardCount
	}
	return shardID
}
```

Table placement is explicit in the routing map:

```go
var tableRoutes = map[string]TableRoute{
	"Administrator": {TableName: "Administrator", KeyColumn: "AdminID", Placement: PlacementReplicate},
	"Category":      {TableName: "Category", KeyColumn: "CategoryID", Placement: PlacementReplicate},
	"Member":        {TableName: "Member", KeyColumn: "MemberID", Placement: PlacementPartition},
	"WishRequest":   {TableName: "WishRequest", KeyColumn: "WishRequestID", Placement: PlacementPartition},
	"Listing":       {TableName: "Listing", KeyColumn: "ListingID", Placement: PlacementPartition},
	"ListingImage":  {TableName: "ListingImage", KeyColumn: "ImageID", Placement: PlacementPartition},
	"Offer":         {TableName: "Offer", KeyColumn: "OfferID", Placement: PlacementPartition},
	"Transaction":   {TableName: "Transaction", KeyColumn: "TransactionID", Placement: PlacementPartition},
	"MessageThread": {TableName: "MessageThread", KeyColumn: "ThreadID", Placement: PlacementPartition},
	"Message":       {TableName: "Message", KeyColumn: "MessageID", Placement: PlacementPartition},
	"Notification":  {TableName: "Notification", KeyColumn: "NotificationID", Placement: PlacementPartition},
	"Watchlist":     {TableName: "Watchlist", KeyColumn: "WatchlistID", Placement: PlacementPartition},
	"Report":        {TableName: "Report", KeyColumn: "ReportID", Placement: PlacementPartition},
	"Rating":        {TableName: "Rating", KeyColumn: "RatingID", Placement: PlacementPartition},
}
```

Reference tables are copied to every shard because they are small and are joined often during reads.

## 3. How Query Routing Is Implemented

The app opens one connection pool for the base database and one for each shard. The shard database names are derived from the base name, so the same DSN can be reused safely.

```go
sharding.Configure(baseDatabase, sharding.DefaultShardCount)
Shards = openShardConnections(baseDatabase, sharding.DefaultShardCount, dsn)
```

The shard connections are created by replacing only the database name in the DSN, so the rest of the connection settings stay the same.

For lookups and writes, the backend routes directly to the shard that owns the row ID. For browse-style queries, it fans out to all shards and merges the results in application code.

The listings browse path shows this clearly:

```go
func fetchListingRowsAcrossShards(ctx context.Context, baseWhere string, args []interface{}) ([]listingRow, error) {
	query := `SELECT ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable,
					 ` + "`Condition`" + `, Status, CreatedDate, LastModifiedDate, WishRequestID
				FROM Listing l` + baseWhere

	var rows []listingRow
	for _, shardDB := range appdb.AllShardConnections() {
		shardRows, err := shardDB.QueryContext(ctx, query, args...)
		...
	}
	return rows, nil
}
```

Related-record routing, especially for the offer workflow, is pinned by the listing ID. Once the listing ID is known, the backend routes listing-local reads and writes to the same shard so multi-step operations stay colocated. For inserts, the new listing ID is allocated first and then used to choose the target shard. Replicated or global tables such as Member and Category are still read from their own placements when needed.

The mapping used in the backend is:

| Query type | Routing behaviour | Example |
| --- | --- | --- |
| Single lookup | Direct to owning shard | `GET /listings/{id}` |
| Single insert | Allocate the new ListingID, then write to the owning shard | `POST /listings` |
| Related write | Route via the parent listing shard | `POST /listings/{id}/offers` |
| Browse / range | Fan-out across shards and merge results | `GET /listings` |

This matches the backend pattern of using `listingShardDB(listingID)` for listing-local operations and `fetchListingRowsAcrossShards(...)` for browse-style reads.

## 4. SQL Shard Tables Created and How Data Was Migrated

The shard DDL creates three separate databases and then builds the same table structure in each one.

```sql
CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_0;
CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_1;
CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_2;
```

The shard databases contain the following tables:

- `Member`
- `Administrator`
- `Category`
- `WishRequest`
- `Listing`
- `ListingImage`
- `Offer`
- `Transaction`
- `MessageThread`
- `Message`
- `Notification`
- `Watchlist`
- `Report`
- `Rating`

Migration is handled by [scripts/migrate_shards.py](scripts/migrate_shards.py). The flow is:

1. Create the three shard databases.
2. Read each row from the source database.
3. Route partitioned rows using the modulo rule.
4. Copy replicated rows to every shard.
5. Commit the shard writes.
6. Summarize row counts and duplicate checks.

The code makes that logic pretty clear:

```python
def copy_partitioned_table(source_cursor, shard_connections, router, base_database, table):
	columns, rows = fetch_primary_rows(source_cursor, base_database, table)
	for row in rows:
		routing_value = value_for_routing(table, row, columns)
		shard_id = router.shard_id_for(routing_value)
		...

def copy_replicated_table(source_cursor, shard_connections, base_database, table):
	columns, rows = fetch_primary_rows(source_cursor, base_database, table)
	for shard_id, shard_connection in enumerate(shard_connections):
		...
```

Verification is handled by [scripts/verify_shards.py](scripts/verify_shards.py). It checks that partitioned totals match the source and that the same primary key does not appear on more than one shard.

## 5. Sharding Approach Used and How Isolation Was Achieved

The project uses multiple databases on the same MySQL server to simulate shard isolation. That matches the assignment requirement and keeps the setup simple for a course project.

Isolation comes from two things:

- Each shard has its own database name, such as `CampusTradingB_shard_0`.
- The backend opens a separate connection pool per shard.

The connection setup in [backend/db/db.go](backend/db/db.go) makes that separation explicit:

```go
sharding.Configure(baseDatabase, sharding.DefaultShardCount)
Shards = openShardConnections(baseDatabase, sharding.DefaultShardCount, dsn)
```

This setup keeps shard-local reads and writes isolated while still allowing fan-out reads when the application needs global browse behavior.

## 6. Results of the Scalability and Trade-Offs Analysis

### Horizontal vs. Vertical Scaling

Vertical scaling means upgrading one database server with more CPU, RAM, and disk. It is simple, but it still leaves one machine as the bottleneck.

Horizontal scaling with shards spreads data and traffic across multiple databases, so the app can grow by adding capacity instead of relying on one larger server.

### Consistency

Each shard remains transactional on its own, so local reads and writes are consistent within the shard that owns the data.

The system does not provide one global transaction across all shards. That means cross-shard reads can be temporarily inconsistent if one shard changes before another, and replicated tables can briefly differ if they are updated separately.

### Availability

If one shard fails, only the data mapped to that shard becomes unavailable. The other shards can still serve their own data.

That improves partial availability, but the application still has to handle the failed shard explicitly for any request that depends on it.

### Partition Tolerance

The design tolerates simulated shard failure by keeping the shard boundaries independent and routing each request only to the owning shard.

The implementation does not try to do distributed consensus, quorum writes, or automatic rebalancing. Those would be needed for stronger production-grade partition tolerance.

## 7. Observations and Limitations

### Observations

The modulo shard key gave a balanced distribution for the current data set. The verified counts stayed close across the three shards, which shows that the routing rule worked as intended for the workload used in this assignment.

The migration process was straightforward once the shard databases were in place. Partitioned tables went to a single owning shard, replicated tables were copied to all shards, and the verification script confirmed that the final totals matched the source database.

One practical thing I noticed was that shard-aware access had to be explicit in the backend. Single-record lookups and writes could be routed directly, but browse-style queries still needed fan-out across all shards and result merging in application code.

### Limitations

Sharding does not solve cross-shard transaction management. A write that touches more than one shard cannot be treated like one atomic global transaction without extra coordination logic.

Sharding also does not remove the cost of global reads. Range queries, admin-style reports, and any query that needs data from multiple shards still require fan-out and merge steps, which are slower and more complex than a single-database query.

The design does not solve shard failure by itself. If one shard is unavailable, only the data mapped to the other shards can be accessed; the application still needs retry, failover, or recovery logic to restore full availability.

Finally, sharding is not a rebalance or scaling cure-all. The chosen modulo key works well for the current data set, but it does not support easy live reshuffling of data, automatic shard expansion, or removal of all hot-spot risk in every future workload.
