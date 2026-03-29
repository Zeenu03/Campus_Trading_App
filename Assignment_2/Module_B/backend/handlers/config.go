package handlers

import (
	"encoding/json"
	"net/http"
)

var DEPARTMENTS = []string{
	"Chemical Engineering", "Civil Engineering", "Computer Science",
	"Electrical Engineering", "Mathematics", "Mechanical Engineering", "Physics", "Other",
}

var HOSTELS = []string{
	"Aibaan", "Beaukni", "Chimair", "Duven", "Emiet", "Firpeal", "Griwiksh", "Ijokha", "Jurqia", "Kyzeel", "Lekhaag", "Hiqom",
}

func ListDepartments(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(DEPARTMENTS)
}

func ListHostels(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(HOSTELS)
}
