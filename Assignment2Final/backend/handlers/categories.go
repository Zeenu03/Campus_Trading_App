package handlers

import (
	"net/http"

	appdb "campus-trading/db"
	"campus-trading/models"
)

// GET /api/v1/categories — active categories for filters / forms
func ListCategories(w http.ResponseWriter, r *http.Request) {
	rows, err := appdb.DB.QueryContext(r.Context(),
		`SELECT CategoryID, CategoryName FROM Category WHERE IsActive = 1 ORDER BY CategoryName`)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var out []models.Category
	for rows.Next() {
		var c models.Category
		if err := rows.Scan(&c.CategoryID, &c.CategoryName); err != nil {
			continue
		}
		out = append(out, c)
	}
	if out == nil {
		out = []models.Category{}
	}
	respondJSON(w, http.StatusOK, out)
}
