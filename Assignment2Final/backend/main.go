package main

import (
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	appaudit "campus-trading/audit"
	appdb "campus-trading/db"
	"campus-trading/handlers"
	mw "campus-trading/middleware"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/joho/godotenv"
)

func main() {
	// Load .env if present
	_ = godotenv.Load()

	// Init DB
	appdb.Init()

	// Init audit log file
	auditPath := os.Getenv("AUDIT_LOG_PATH")
	if auditPath == "" {
		auditPath = "./logs/audit.log"
	}
	appaudit.Init(auditPath)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	frontendURL := os.Getenv("FRONTEND_URL")
	if frontendURL == "" {
		frontendURL = "http://localhost:5173"
	}

	r := chi.NewRouter()

	// Global middleware
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(corsMiddleware(frontendURL))
	r.Use(mw.AuditMiddleware)

	// Serve uploaded images (before /api to avoid conflict)
	workDir, _ := os.Getwd()
	uploadsDir := os.Getenv("UPLOADS_DIR")
	if uploadsDir == "" {
		uploadsDir = filepath.Join(workDir, "uploads")
	}
	r.Handle("/uploads/*", http.StripPrefix("/uploads", http.FileServer(http.Dir(uploadsDir))))

	// ── Public routes ──────────────────────────────────────────
	r.Route("/api/v1", func(r chi.Router) {

		r.Route("/auth", func(r chi.Router) {
			r.Post("/login", handlers.Login)
			r.Post("/register", handlers.Register)
			r.With(mw.SessionGuard).Post("/logout", handlers.Logout)
			r.With(mw.SessionGuard).Get("/me", handlers.Me)
		})

		// ── Authenticated routes ─────────────────────────────────
		r.Group(func(r chi.Router) {
			r.Use(mw.SessionGuard)

			// Members
			r.Get("/members", handlers.ListMembers)                 // admin
			r.Get("/members/{id}/portfolio", handlers.GetPortfolio) // auth — public profile (watchlist owner-only)
			r.Put("/members/{id}", handlers.UpdateMember)           // own|admin
			r.Delete("/members/{id}", handlers.DeleteMember)        // admin

			r.Get("/categories", handlers.ListCategories) // auth

			// Listings
			r.Get("/listings", handlers.ListListings)                    // auth
			r.Post("/listings", handlers.CreateListing)                  // member
			r.Get("/listings/{id}", handlers.GetListing)                 // auth
			r.Put("/listings/{id}", handlers.UpdateListing)            // own|admin
			r.Delete("/listings/{id}", handlers.DeleteListing)          // own|admin
			r.Post("/listings/{id}/images", handlers.AddListingImage)   // own|admin
			r.Delete("/listings/{id}/images/{imageId}", handlers.DeleteListingImage) // own|admin

			// Offers
			r.Get("/listings/{id}/my-offer", handlers.GetMyOffer)               // own-buyer
			r.Get("/listings/{id}/offers", handlers.ListOffersForListing)       // own-seller|admin
			r.Post("/listings/{id}/offers", handlers.CreateOffer)               // member
			r.Put("/offers/{id}/accept", handlers.AcceptOffer)                  // own-seller
			r.Put("/offers/{id}/decline", handlers.DeclineOffer)                // own-seller
			r.Put("/offers/{id}/withdraw", handlers.WithdrawOffer)              // own-buyer
			r.Put("/offers/{id}/price", handlers.UpdateOfferPrice)              // own-buyer
			r.Put("/offers/{id}/buyer-accept", handlers.BuyerAcceptOffer)       // own-buyer (syncs price to asking, does NOT finalise)
			r.Put("/offers/{id}/seller-price", handlers.UpdateSellerAskingPrice) // own-seller (per-offer counter price)

			// Threads & Messages
			r.Get("/listings/{id}/my-thread", handlers.GetMyThread)             // own-buyer
			r.Post("/listings/{id}/threads", handlers.CreateThread)             // member (chat-only)
			r.Get("/listings/{id}/interactions", handlers.ListInteractions)     // own-seller|admin
			r.Get("/threads/{id}/messages", handlers.ListMessages)              // buyer|seller
			r.Post("/threads/{id}/messages", handlers.SendMessage)              // buyer|seller

			// Transactions
			r.Get("/transactions", handlers.ListTransactions)           // auth
			r.Post("/transactions/{id}/rate", handlers.RateTransaction) // own-party (Accepted only)

			// Wish Requests
			r.Get("/wishrequests", handlers.ListWishRequests)       // auth
			r.Post("/wishrequests", handlers.CreateWishRequest)     // member
			r.Put("/wishrequests/{id}", handlers.UpdateWishRequest) // own

			// Watchlist
			r.Get("/watchlist", handlers.GetWatchlist)                                   // member
			r.Post("/watchlist", handlers.AddToWatchlist)                                // member
			r.Delete("/watchlist/listing/{listingId}", handlers.RemoveFromWatchlistByListing) // member (by listing)
			r.Delete("/watchlist/{id}", handlers.RemoveFromWatchlist)                    // own (by watchlist id)

			// Notifications
			r.Get("/notifications", handlers.ListNotifications)              // member
			r.Put("/notifications/{id}/read", handlers.MarkNotificationRead) // own

			// Reports
			r.Get("/reports", handlers.ListReports)                // admin
			r.Post("/reports", handlers.CreateReport)              // auth
			r.Put("/reports/{id}/resolve", handlers.ResolveReport) // admin

			// Admin-only routes
			r.Route("/admin", func(r chi.Router) {
				r.Use(mw.AdminOnly)
				r.Get("/audit-log", handlers.GetAuditLog)
				r.Get("/benchmark", handlers.Benchmark)
				r.Get("/stats", handlers.AdminStats)
				r.Post("/users", handlers.CreateAdminUser)
				r.Get("/members/{id}", handlers.AdminGetMember)
			})
		})
	})

	log.Printf("Campus Trading API running on :%s", port)
	if err := http.ListenAndServe(":"+port, r); err != nil {
		log.Fatalf("server error: %v", err)
	}
}

func parseAllowedOrigins(raw string) []string {
	var out []string
	for _, p := range strings.Split(raw, ",") {
		if s := strings.TrimSpace(p); s != "" {
			out = append(out, s)
		}
	}
	return out
}

func corsMiddleware(allowedOrigins string) func(http.Handler) http.Handler {
	allowed := parseAllowedOrigins(allowedOrigins)
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			for _, o := range allowed {
				if origin != "" && o == origin {
					w.Header().Set("Access-Control-Allow-Origin", origin)
					w.Header().Set("Access-Control-Allow-Credentials", "true")
					break
				}
			}
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
