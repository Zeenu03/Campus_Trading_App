# Campus Trading App - Assignment 4 Sharding Report

- GitHub repository link: [Campus Trading App](https://github.com/Zeenu03/Campus_Trading_App/tree/a4t1)
- Video link: [Video Demonstration](https://drive.google.com/drive/folders/1l-RayTmUGG57QMmtfaCMXEwNpb5eaTEG?usp=sharing)

## 1. Shard Key Chosen and Justification

I used a simple primary-key modulo rule: `shard_id = record_id mod 3`.

It fit the app pretty well and was easy to explain:

- High cardinality: the primary keys are unique and naturally spread across a large value space.
- Query-aligned: the app often looks up listings, offers, transactions, threads, and user-owned data by ID.
- Stable: primary keys do not change after insertion, so the routing stays consistent.

Modulo routing also spreads consecutive IDs across the three shards, so the partitioned tables ended up fairly balanced. The low-usage control tables were kept on Shard 1 only.

## 2. Partitioning Strategy Used and Why

The project uses hash-style modulo partitioning instead of range-based or directory-based partitioning.

That made sense for this assignment because:

- It is deterministic and easy to explain.
- It keeps shard selection O(1) for a known ID.
- It avoids the skew that can happen when all low or high ID ranges land on one shard.
- It matches the course requirement to simulate sharding using multiple databases on the same server.

The Task 1 shard endpoints are:

- Shard 1: `10.0.116.184:3307`
- Shard 2: `10.0.116.184:3308`
- Shard 3: `10.0.116.184:3309`

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
	"Administrator": {TableName: "Administrator", KeyColumn: "AdminID", Placement: PlacementCentral},
	"Category":      {TableName: "Category", KeyColumn: "CategoryID", Placement: PlacementReplicate},
	"audit_log":     {TableName: "audit_log", KeyColumn: "log_id", Placement: PlacementCentral},
	"sys_role":      {TableName: "sys_role", KeyColumn: "role_id", Placement: PlacementCentral},
	"sys_session":   {TableName: "sys_session", KeyColumn: "session_id", Placement: PlacementCentral},
	"sys_user":      {TableName: "sys_user", KeyColumn: "user_id", Placement: PlacementCentral},
	"sys_user_role": {TableName: "sys_user_role", KeyColumn: "user_id", Placement: PlacementCentral},
	"Member":        {TableName: "Member", KeyColumn: "MemberID", Placement: PlacementCentral},
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

Category is copied to every shard because it is small and gets joined a lot during reads. Member and the low-usage control tables stay on Shard 1 so authentication, session, and audit traffic does not get duplicated everywhere.

In the final layout, Shard 1 holds the central tables, including Member, while Shard 2 and Shard 3 only hold the replicated and partitioned tables.

## 3. How Query Routing Is Implemented

The app opens one connection pool for the source database and one for each shard. Each shard connection points to the host, port, and database from Task 1, so the backend can talk to the right shard directly.

```go
sharding.Configure(baseDatabase, sharding.DefaultShardCount, shardTargets)
Shards = openShardConnections(dsn, baseDatabase, shardTargets, shardUser, shardPassword)
```

That keeps the routing simple and avoids hardcoding any special-case logic in the query code.

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

Related-record routing, especially for the offer workflow, follows the listing ID. Once the listing ID is known, the backend keeps the related reads and writes on the same shard so multi-step operations stay together. For inserts, the new listing ID is assigned first and then used to pick the target shard. Replicated or global tables such as Member and Category are still read from their own placements when needed.

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
CREATE DATABASE IF NOT EXISTS Optimiser;
```

That database name is used on each assigned shard host.

The shard databases contain the following tables. Member and the control tables are centralized on Shard 1 and Category is replicated:

- `sys_user`
- `sys_role`
- `sys_user_role`
- `sys_session`
- `audit_log`
- `Administrator`
- `Category`
- `Member`
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

1. Create the shard schema on each target shard.
2. Read each row from the source database.
3. Route partitioned rows using the modulo rule.
4. Copy control-plane tables and Member to Shard 1 only.
5. Copy Category to every shard.
6. Commit the shard writes.
7. Summarize row counts and duplicate checks.

The schema initialization step is handled by [scripts/init_shards.py](scripts/init_shards.py). It builds the shard tables from the source database DDL before the migration starts, with Member created only on Shard 1.

The code makes that logic pretty clear:

```python
def copy_partitioned_table(source_cursor, shard_connections, shard_configs, router, base_database, table):
	columns, rows = fetch_primary_rows(source_cursor, base_database, table)
	for row in rows:
		routing_value = route_value_for_table(table, row, columns)
		shard_id = router.shard_id_for(routing_value)
		...

def copy_central_table(source_cursor, shard_connections, shard_configs, base_database, table):
	columns, rows = fetch_primary_rows(source_cursor, base_database, table)
	shard_connection = shard_connections[0]
	...

def copy_replicated_table(source_cursor, shard_connections, shard_configs, base_database, table):
	columns, rows = fetch_primary_rows(source_cursor, base_database, table)
	for shard_id, shard_connection in enumerate(shard_connections):
		...
```

Verification is handled by [scripts/verify_shards.py](scripts/verify_shards.py). It checks that partitioned totals match the source and that the same primary key does not appear on more than one shard.

## 5. Sharding Approach Used and How Isolation Was Achieved

The project uses multiple databases on the same MySQL server to simulate shard isolation. That matched the assignment requirement and kept the setup manageable for a course project.

Isolation comes from two things:

- Each shard has its own explicit host, port, and database configuration.
- The backend opens a separate connection pool per shard.

The connection setup in [backend/db/db.go](backend/db/db.go) makes that separation explicit:

```go
sharding.Configure(baseDatabase, sharding.DefaultShardCount, shardTargets)
Shards = openShardConnections(dsn, baseDatabase, shardTargets, shardUser, shardPassword)
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

The modulo shard key gave a pretty even spread for the partitioned data set. The verified counts stayed close across the three shards, and Member plus the control-plane tables remained on Shard 1 as intended.

Once the shard endpoints were in place, the migration was straightforward. Partitioned tables went to one owning shard, Member and the control-plane tables were copied to Shard 1 only, Category was copied to all shards, and the verification script confirmed that the totals matched the source database.

That verification also confirmed that Shard 2 and Shard 3 do not contain Member or the central tables, which is the final server state I wanted.

One thing I noticed is that shard-aware access has to be explicit in the backend. Single-record lookups and writes can be routed directly, but browse-style queries still need fan-out across all shards and result merging in application code.

### Limitations

Sharding does not solve cross-shard transaction management. A write that touches more than one shard cannot be treated like one atomic global transaction without extra coordination logic.

Sharding also does not remove the cost of global reads. Range queries, admin-style reports, and any query that needs data from multiple shards still require fan-out and merge steps, which are slower and more complex than a single-database query.

The design does not solve shard failure by itself. If one shard is unavailable, only the data on the other shards can be accessed; the application still needs retry, failover, or recovery logic to restore full availability.

Finally, sharding is not a cure-all for scaling. The modulo key worked well for the current data set, but it does not make live reshuffling or automatic shard expansion easy.
