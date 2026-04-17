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
	Host         string `json:"host,omitempty"`
	Port         int    `json:"port,omitempty"`
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
	shardTargets []ShardTarget
)

var tableRoutes = map[string]TableRoute{
	"Administrator": {TableName: "Administrator", KeyColumn: "AdminID", Placement: PlacementCentral},
	"Category":      {TableName: "Category", KeyColumn: "CategoryID", Placement: PlacementReplicate},
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

var centralTables = []string{
	"audit_log",
	"Administrator",
	"Member",
	"sys_role",
	"sys_session",
	"sys_user",
	"sys_user_role",
}

func Configure(baseDB string, count int, targets []ShardTarget) {
	configMu.Lock()
	defer configMu.Unlock()

	if baseDB != "" {
		baseDatabase = baseDB
	}
	if count > 0 {
		shardCount = count
	}
	if len(targets) > 0 {
		shardTargets = normalizeTargets(baseDatabase, shardCount, targets)
	} else {
		shardTargets = nil
	}
}

func CurrentConfiguration() Configuration {
	configMu.RLock()
	base := baseDatabase
	count := shardCount
	targets := append([]ShardTarget(nil), shardTargets...)
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
		Shards:            targetsForRouter(router, targets),
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
	target := defaultTargetForShard(r, shardID)
	if configured, ok := configuredTargetForShard(r, shardID); ok && configured.DatabaseName != "" {
		return configured.DatabaseName
	}
	return target.DatabaseName
}

func (r *Router) TargetFor(recordID int) ShardTarget {
	shardID := r.ShardIDFor(recordID)
	if target, ok := configuredTargetForShard(r, shardID); ok {
		return target
	}
	return defaultTargetForShard(r, shardID)
}

func (r *Router) Targets() []ShardTarget {
	return shardTargetsForRouter(r)
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
		return router.Targets()[0], route, nil
	}
	if route.Placement == PlacementCentral {
		targets := router.Targets()
		if len(targets) > 0 {
			return targets[0], route, nil
		}
		return ShardTarget{ShardID: 0, DatabaseName: router.baseDatabase}, route, nil
	}
	return router.TargetFor(rowID), route, nil
}

func DescribeRoute(tableName string, rowID int) string {
	target, route, err := RouteTableRow(tableName, rowID)
	if err != nil {
		return err.Error()
	}
	shardLabel := target.ShardID + 1
	if route.Placement == PlacementReplicate {
		return fmt.Sprintf("%s:%d -> all shards", tableName, rowID)
	}
	if route.Placement == PlacementCentral {
		if target.Host != "" && target.Port > 0 {
			return fmt.Sprintf("%s:%d -> central shard_%d (%s:%d/%s)", tableName, rowID, shardLabel, target.Host, target.Port, target.DatabaseName)
		}
		return fmt.Sprintf("%s:%d -> central shard_%d (%s)", tableName, rowID, shardLabel, target.DatabaseName)
	}
	if target.Host != "" && target.Port > 0 {
		return fmt.Sprintf("%s:%d -> shard_%d (%s:%d/%s)", tableName, rowID, shardLabel, target.Host, target.Port, target.DatabaseName)
	}
	return fmt.Sprintf("%s:%d -> shard_%d (%s)", tableName, rowID, shardLabel, target.DatabaseName)
}

func normalizeTargets(base string, count int, targets []ShardTarget) []ShardTarget {
	normalized := make([]ShardTarget, 0, len(targets))
	for idx, target := range targets {
		if target.ShardID != idx {
			target.ShardID = idx
		}
		if target.DatabaseName == "" {
			target.DatabaseName = base
		}
		normalized = append(normalized, target)
	}
	if count > 0 && len(normalized) > count {
		normalized = normalized[:count]
	}
	return normalized
}

func shardTargetsForRouter(r *Router) []ShardTarget {
	configMu.RLock()
	targets := append([]ShardTarget(nil), shardTargets...)
	configMu.RUnlock()
	if r == nil {
		return targets
	}
	if len(targets) == r.shardCount && len(targets) > 0 {
		return targets
	}
	if r.shardCount <= 0 {
		return []ShardTarget{defaultTargetForShard(r, 0)}
	}
	fallback := make([]ShardTarget, 0, r.shardCount)
	for shardID := 0; shardID < r.shardCount; shardID++ {
		fallback = append(fallback, defaultTargetForShard(r, shardID))
	}
	return fallback
}

func targetsForRouter(r *Router, targets []ShardTarget) []ShardTarget {
	if len(targets) > 0 {
		return targets
	}
	return shardTargetsForRouter(r)
}

func configuredTargetForShard(r *Router, shardID int) (ShardTarget, bool) {
	if r == nil || shardID < 0 {
		return ShardTarget{}, false
	}
	configMu.RLock()
	targets := append([]ShardTarget(nil), shardTargets...)
	configMu.RUnlock()
	if len(targets) != r.shardCount || shardID >= len(targets) {
		return ShardTarget{}, false
	}
	target := targets[shardID]
	if target.ShardID != shardID {
		target.ShardID = shardID
	}
	if target.DatabaseName == "" {
		target.DatabaseName = r.baseDatabase
	}
	return target, true
}

func defaultTargetForShard(r *Router, shardID int) ShardTarget {
	base := "CampusTradingB"
	if r != nil && r.baseDatabase != "" {
		base = r.baseDatabase
	}
	return ShardTarget{ShardID: shardID, DatabaseName: base}
}
