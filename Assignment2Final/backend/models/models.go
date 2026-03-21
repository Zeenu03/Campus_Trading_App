package models

import "time"

// ── Core System ──────────────────────────────────────────────

type SysUser struct {
	UserID       int       `json:"user_id"`
	Email        string    `json:"email"`
	PasswordHash string    `json:"-"`
	IsActive     bool      `json:"is_active"`
	CreatedAt    time.Time `json:"created_at"`
}

type SysSession struct {
	SessionID string    `json:"session_id"`
	UserID    int       `json:"user_id"`
	ExpiresAt time.Time `json:"expires_at"`
	IsRevoked bool      `json:"is_revoked"`
	CreatedAt time.Time `json:"created_at"`
}

type SysRole struct {
	RoleID   int    `json:"role_id"`
	RoleName string `json:"role_name"`
}

type AuditLog struct {
	LogID       int64     `json:"log_id"`
	Timestamp   time.Time `json:"timestamp"`
	SessionID   *string   `json:"session_id"`
	UserID      *int      `json:"user_id"`
	Action      string    `json:"action"`
	TargetTable string    `json:"target_table"`
	TargetID    *string   `json:"target_id"`
	IPAddress   *string   `json:"ip_address"`
	Status      string    `json:"status"`
}

// ── Project Tables ───────────────────────────────────────────

type Member struct {
	MemberID            int        `json:"member_id"`
	UserID              int        `json:"user_id"`
	Name                string     `json:"name"`
	Email               string     `json:"email,omitempty"` // joined from sys_user
	ContactNumber       string     `json:"contact_number"`
	Department          *string    `json:"department"`
	YearOfStudy         *int       `json:"year_of_study"`
	Hostel              *string    `json:"hostel"`
	RoomNumber          *string    `json:"room_number"`
	Image               *string    `json:"image"`
	Bio                 *string    `json:"bio"`
	IsVerified          bool       `json:"is_verified"`
	VerificationDate    *time.Time `json:"verification_date"`
	AccountCreationDate time.Time  `json:"account_creation_date"`
	IsActive            bool       `json:"is_active"`
}

type Administrator struct {
	AdminID      int        `json:"admin_id"`
	UserID       int        `json:"user_id"`
	Name         string     `json:"name"`
	Email        string     `json:"email,omitempty"` // joined from sys_user
	Role         string     `json:"role"`
	CreatedDate  time.Time  `json:"created_date"`
	LastLoginDate *time.Time `json:"last_login_date"`
	IsActive     bool       `json:"is_active"`
}

type Category struct {
	CategoryID   int     `json:"category_id"`
	CategoryName string  `json:"category_name"`
	Description  *string `json:"description"`
	IsActive     bool    `json:"is_active"`
}

type Listing struct {
	ListingID               int        `json:"listing_id"`
	SellerID                int        `json:"seller_id"`
	SellerName              string     `json:"seller_name,omitempty"` // joined
	CategoryID              int        `json:"category_id"`
	CategoryName            string     `json:"category_name,omitempty"` // joined
	Title                   string     `json:"title"`
	Description             *string    `json:"description"`
	AskingPrice             float64    `json:"asking_price"`
	IsNegotiable            bool       `json:"is_negotiable"`
	Condition               *string    `json:"condition"`
	Status                  string     `json:"status"`
	CreatedDate             time.Time  `json:"created_date"`
	LastModifiedDate        *time.Time `json:"last_modified_date"`
	WishRequestID           *int       `json:"wish_request_id"`
	Images                  []ListingImage `json:"images,omitempty"`
	WatcherCount            int        `json:"watcher_count"`
	MyWatchlistID           *int       `json:"my_watchlist_id"` // non-nil when the requesting member is watching
}

type ListingImage struct {
	ImageID     int       `json:"image_id"`
	ListingID   int       `json:"listing_id"`
	ImageURL    string    `json:"image_url"`
	ImageOrder  int       `json:"image_order"`
	UploadedDate time.Time `json:"uploaded_date"`
}

type Offer struct {
	OfferID           int        `json:"offer_id"`
	ListingID         int        `json:"listing_id"`
	BuyerID           int        `json:"buyer_id"`
	BuyerName         string     `json:"buyer_name,omitempty"` // joined
	OfferedPrice      float64    `json:"offered_price"`
	SellerAskingPrice *float64   `json:"seller_asking_price"` // per-offer counter price set by seller; nil = use listing AskingPrice
	AgreedPrice       *float64   `json:"agreed_price"`
	OfferStatus       string     `json:"offer_status"`
	Reason            *string    `json:"reason"`
	SubmittedDate     time.Time  `json:"submitted_date"`
	ResponseDate      *time.Time `json:"response_date"`
}

type Transaction struct {
	TransactionID int       `json:"transaction_id"`
	ListingID     int       `json:"listing_id"`
	ListingTitle  string    `json:"listing_title,omitempty"` // joined
	SellerID      int       `json:"seller_id"`
	SellerName    string    `json:"seller_name,omitempty"` // joined
	BuyerID       int       `json:"buyer_id"`
	BuyerName     string    `json:"buyer_name,omitempty"` // joined
	OfferID       int       `json:"offer_id"`
	AgreedPrice   float64   `json:"agreed_price"`
	// Status and Reason are derived at query time from Offer.OfferStatus and Offer.Reason
	// via the OfferID FK — not stored redundantly in the Transaction table.
	Status      string  `json:"status"`
	Reason      *string `json:"reason"`
	HasRated    bool    `json:"has_rated"` // true if the requesting user has already submitted a rating
	CreatedDate time.Time `json:"created_date"`
}

type Rating struct {
	RatingID     int       `json:"rating_id"`
	TransactionID int      `json:"transaction_id"`
	RaterID      int       `json:"rater_id"`
	RaterName    string    `json:"rater_name,omitempty"` // joined
	RatedID      int       `json:"rated_id"`
	Stars        int       `json:"stars"`
	ReviewText   *string   `json:"review_text"`
	RatingDate   time.Time `json:"rating_date"`
}

type WishRequest struct {
	WishRequestID     int        `json:"wish_request_id"`
	RequesterID       int        `json:"requester_id"`
	RequesterName     string     `json:"requester_name,omitempty"` // joined
	ItemDescription   string     `json:"item_description"`
	MinBudget         *float64   `json:"min_budget"`
	MaxBudget         *float64   `json:"max_budget"`
	PreferredCondition *string   `json:"preferred_condition"`
	NeededByDate      *time.Time `json:"needed_by_date"`
	AdditionalDetails *string    `json:"additional_details"`
	Status            string     `json:"status"`
	CreatedDate       time.Time  `json:"created_date"`
	FulfilledDate     *time.Time `json:"fulfilled_date"`
}

type Watchlist struct {
	WatchlistID          int       `json:"watchlist_id"`
	MemberID             int       `json:"member_id"`
	ListingID            int       `json:"listing_id"`
	ListingTitle         string    `json:"listing_title,omitempty"` // joined
	AddedDate            time.Time `json:"added_date"`
	NotifyOnPriceChange  bool      `json:"notify_on_price_change"`
	NotifyOnStatusChange bool      `json:"notify_on_status_change"`
}

type Report struct {
	ReportID          int        `json:"report_id"`
	ReporterID        int        `json:"reporter_id"`
	ReporterName      string     `json:"reporter_name,omitempty"` // joined
	ReportedMemberID  *int       `json:"reported_member_id"`
	ReportedListingID *int       `json:"reported_listing_id"`
	ReportType        string     `json:"report_type"`
	Description       string     `json:"description"`
	Status            string     `json:"status"`
	SubmittedDate     time.Time  `json:"submitted_date"`
	ResolvedDate      *time.Time `json:"resolved_date"`
	ResolvedByAdminID *int       `json:"resolved_by_admin_id"`
	Resolution        *string    `json:"resolution"`
}

type Notification struct {
	NotificationID      int        `json:"notification_id"`
	RecipientID         int        `json:"recipient_id"`
	NotificationType    string     `json:"notification_type"`
	Title               *string    `json:"title"`
	Message             string     `json:"message"`
	RelatedListingID    *int       `json:"related_listing_id"`
	RelatedOfferID      *int       `json:"related_offer_id"`
	RelatedTransactionID *int      `json:"related_transaction_id"`
	IsRead              bool       `json:"is_read"`
	CreatedDate         time.Time  `json:"created_date"`
	ReadDate            *time.Time `json:"read_date"`
}

type MessageThread struct {
	ThreadID           int        `json:"thread_id"`
	ListingID          int        `json:"listing_id"`
	BuyerID            int        `json:"buyer_id"`
	BuyerName          string     `json:"buyer_name,omitempty"` // joined
	OfferID            *int       `json:"offer_id"`
	OfferedPrice       *float64   `json:"offered_price"`        // joined from Offer
	SellerAskingPrice  *float64   `json:"seller_asking_price"`  // per-offer counter price; nil = use AskingPrice
	AgreedPrice        *float64   `json:"agreed_price"`         // joined from Offer
	OfferStatus        *string    `json:"offer_status"`         // joined from Offer
	OfferReason        *string    `json:"offer_reason"`         // joined from Offer
	AskingPrice        float64    `json:"asking_price"`         // listing global asking price
	LastMessagePreview *string    `json:"last_message_preview"` // subquery
	CreatedDate        time.Time  `json:"created_at"`
	IsActive           bool       `json:"is_active"`
}

type Message struct {
	MessageID   int       `json:"message_id"`
	ThreadID    int       `json:"thread_id"`
	SenderID    int       `json:"sender_id"`
	SenderName  string    `json:"sender_name,omitempty"` // joined
	MessageText string    `json:"message_text"`
	SentDate    time.Time `json:"sent_date"`
}

// ── Request/Response DTOs ─────────────────────────────────────

type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type RegisterRequest struct {
	Name          string  `json:"name"`
	Email         string  `json:"email"`
	Password      string  `json:"password"`
	ContactNumber string  `json:"contact_number"`
	Department    *string `json:"department"`
	YearOfStudy   *int    `json:"year_of_study"`
	Hostel        *string `json:"hostel"`
	RoomNumber    *string `json:"room_number"`
	Bio           *string `json:"bio"`
}

type AuthResponse struct {
	User  *Member   `json:"user,omitempty"`
	Admin *Administrator `json:"admin,omitempty"`
	Roles []string  `json:"roles"`
}

type PaginatedResponse struct {
	Data       interface{} `json:"data"`
	Total      int         `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int         `json:"total_pages"`
}

type ErrorResponse struct {
	Error string `json:"error"`
}

// BenchmarkResult holds EXPLAIN results for one query
type BenchmarkResult struct {
	QueryName    string  `json:"query_name"`
	Query        string  `json:"query"`
	AccessType   string  `json:"type"`
	PossibleKeys *string `json:"possible_keys"`
	KeyUsed      *string `json:"key_used"`
	KeyLen       *string `json:"key_len"`
	RowsExamined *int64  `json:"rows_examined"`
	Extra        *string `json:"extra"`
	DurationMs   float64 `json:"duration_ms"`
}
