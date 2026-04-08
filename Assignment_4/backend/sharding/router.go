package sharding

import (
	"fmt"
	"sort"
	"sync"
)

const DefaultShardCount = 3

type Placement string

const (
	PlacementPartition Placement = "partition"
	PlacementReplicate Placement = "replicate"
	PlacementCentral   Placement = "central"
)

type ShardTarget struct {
	ShardID      int    `json:"shard_id"`
	DatabaseName string `json:"database_name"`
}

type TableRoute struct {
	TableName string    `json:"table_name"`
	KeyColumn string    `json:"key_column"`
	Placement Placement `json:"placement"`
}

type Configuration struct {
	BaseDatabase      string        `json:"base_database"`
	ShardCount        int           `json:"shard_count"`
	RoutingRule       string        `json:"routing_rule"`
	Shards            []ShardTarget `json:"shards"`
	TableRoutes       []TableRoute  `json:"table_routes"`
	PartitionedTables []string      `json:"partitioned_tables"`
	ReplicatedTables  []string      `json:"replicated_tables"`
	CentralTables     []string      `json:"central_tables"`
}

type Router struct {
	baseDatabase string
	shardCount   int
}

var (
	configMu     sync.RWMutex
	baseDatabase = "CampusTradingB"
	shardCount   = DefaultShardCount
)

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

var centralTables = []string{
	"audit_log",
	"sys_role",
	"sys_session",
	"sys_user",
	"sys_user_role",
}

func Configure(baseDB string, count int) {
	configMu.Lock()
	defer configMu.Unlock()

	if baseDB != "" {
		baseDatabase = baseDB
	}
	if count > 0 {
		shardCount = count
	}
}

func CurrentConfiguration() Configuration {
	configMu.RLock()
	base := baseDatabase
	count := shardCount
	configMu.RUnlock()

	router := NewRouter(base, count)
	routeNames := make([]string, 0, len(tableRoutes))
	for tableName := range tableRoutes {
		routeNames = append(routeNames, tableName)
	}
	sort.Strings(routeNames)

	routes := make([]TableRoute, 0, len(routeNames))
	partitioned := make([]string, 0)
	replicated := make([]string, 0)
	for _, tableName := range routeNames {
		route := tableRoutes[tableName]
		routes = append(routes, route)
		switch route.Placement {
		case PlacementPartition:
			partitioned = append(partitioned, tableName)
		case PlacementReplicate:
			replicated = append(replicated, tableName)
		}
	}

	return Configuration{
		BaseDatabase:      base,
		ShardCount:        count,
		RoutingRule:       fmt.Sprintf("record_id %% %d", count),
		Shards:            router.Targets(),
		TableRoutes:       routes,
		PartitionedTables: partitioned,
		ReplicatedTables:  replicated,
		CentralTables:     append([]string(nil), centralTables...),
	}
}

func NewRouter(baseDB string, count int) *Router {
	if baseDB == "" {
		baseDB = "CampusTradingB"
	}
	if count <= 0 {
		count = DefaultShardCount
	}
	return &Router{baseDatabase: baseDB, shardCount: count}
}

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

func (r *Router) DatabaseNameFor(shardID int) string {
	if r == nil {
		return fmt.Sprintf("CampusTradingB_shard_%d", shardID)
	}
	return fmt.Sprintf("%s_shard_%d", r.baseDatabase, shardID)
}

func (r *Router) TargetFor(recordID int) ShardTarget {
	shardID := r.ShardIDFor(recordID)
	return ShardTarget{ShardID: shardID, DatabaseName: r.DatabaseNameFor(shardID)}
}

func (r *Router) Targets() []ShardTarget {
	if r == nil || r.shardCount <= 0 {
		return []ShardTarget{{ShardID: 0, DatabaseName: "CampusTradingB_shard_0"}}
	}
	targets := make([]ShardTarget, 0, r.shardCount)
	for shardID := 0; shardID < r.shardCount; shardID++ {
		targets = append(targets, ShardTarget{ShardID: shardID, DatabaseName: r.DatabaseNameFor(shardID)})
	}
	return targets
}

func RouteTableRow(tableName string, rowID int) (ShardTarget, TableRoute, error) {
	route, ok := tableRoutes[tableName]
	if !ok {
		return ShardTarget{}, TableRoute{}, fmt.Errorf("unknown table: %s", tableName)
	}

	configMu.RLock()
	base := baseDatabase
	count := shardCount
	configMu.RUnlock()
	router := NewRouter(base, count)

	if route.Placement == PlacementReplicate {
		return ShardTarget{ShardID: 0, DatabaseName: router.DatabaseNameFor(0)}, route, nil
	}
	return router.TargetFor(rowID), route, nil
}

func DescribeRoute(tableName string, rowID int) string {
	target, route, err := RouteTableRow(tableName, rowID)
	if err != nil {
		return err.Error()
	}
	if route.Placement == PlacementReplicate {
		return fmt.Sprintf("%s:%d -> all shards", tableName, rowID)
	}
	return fmt.Sprintf("%s:%d -> shard_%d (%s)", tableName, rowID, target.ShardID, target.DatabaseName)
}
