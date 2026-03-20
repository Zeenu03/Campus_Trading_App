package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
)

func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, map[string]string{"error": message})
}

func urlParamInt(r *http.Request, key string) (int, error) {
	return strconv.Atoi(chi.URLParam(r, key))
}

func queryInt(r *http.Request, key string, def int) int {
	v := r.URL.Query().Get(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	return n
}

func paginate(page, pageSize, total int) (offset int, totalPages int) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 20
	}
	offset = (page - 1) * pageSize
	totalPages = (total + pageSize - 1) / pageSize
	return
}

func jsonNumToFloat(v interface{}) (float64, error) {
	switch x := v.(type) {
	case float64:
		return x, nil
	case int:
		return float64(x), nil
	case int64:
		return float64(x), nil
	case json.Number:
		return x.Float64()
	default:
		return 0, errors.New("expected number")
	}
}

func jsonNumToInt(v interface{}) (int, error) {
	switch x := v.(type) {
	case float64:
		return int(x), nil
	case int:
		return x, nil
	case int64:
		return int(x), nil
	case json.Number:
		i64, err := x.Int64()
		if err != nil {
			return 0, err
		}
		return int(i64), nil
	default:
		return 0, errors.New("expected integer")
	}
}

func jsonToBool(v interface{}) (bool, error) {
	switch x := v.(type) {
	case bool:
		return x, nil
	case float64:
		return x != 0, nil
	default:
		return false, errors.New("expected boolean")
	}
}
