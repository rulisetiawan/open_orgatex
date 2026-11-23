package setex

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"strconv"
)

// RegisterMapping defines calibration and metadata for a single SETEX register.
type RegisterMapping struct {
	Index         int     `json:"index"`
	IWNumber      int     `json:"iw_number"`
	Name          string  `json:"name"`
	NameLocal     string  `json:"name_local"`
	Unit          string  `json:"unit"`
	DigitsBefore  int     `json:"digits_before"`
	DigitsAfter   int     `json:"digits_after"`
	X1            float64 `json:"x1"`     // Engineering min
	X2            float64 `json:"x2"`     // Engineering max
	Y1            float64 `json:"y1"`     // Raw min
	Y2            float64 `json:"y2"`     // Raw max
	Factor        float64 `json:"factor"` // Scale factor
	TagName       string  `json:"tag_name"`
	TagRole       string  `json:"tag_role"`
	FieldName     string  `json:"field_name"`
}

// Calibrate converts raw uint16 to calibrated engineering units using linear interpolation.
func (rm *RegisterMapping) Calibrate(raw uint16) float64 {
	rawF := float64(raw)
	// Linear interpolation: x = x1 + (raw - y1) * (x2 - x1) / (y2 - y1)
	deltaY := rm.Y2 - rm.Y1
	if math.Abs(deltaY) > 1e-6 {
		val := rm.X1 + (rawF-rm.Y1)*(rm.X2-rm.X1)/deltaY
		// Round to decimals if needed
		if rm.DigitsAfter >= 0 && rm.DigitsAfter <= 4 {
			pow := math.Pow(10, float64(rm.DigitsAfter))
			return math.Round(val*pow) / pow
		}
		return val
	}

	// Fallback to factor division
	if rm.Factor > 0 {
		return rawF / rm.Factor
	}
	return rawF
}

// TypeconfMap maps register index (0..239) to its calibration configuration.
type TypeconfMap map[int]*RegisterMapping

// LoadTypeconfFromFile loads a JSON map file (e.g. typeconf_iw_map.json).
func LoadTypeconfFromFile(path string) (TypeconfMap, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read typeconf json %s: %w", path, err)
	}

	var rawMap map[string]*RegisterMapping
	if err := json.Unmarshal(bytes, &rawMap); err != nil {
		return nil, fmt.Errorf("parse typeconf json: %w", err)
	}

	result := make(TypeconfMap)
	for k, v := range rawMap {
		idx, err := strconv.Atoi(k)
		if err != nil {
			continue
		}
		v.Index = idx
		v.IWNumber = idx + 1
		result[idx] = v
	}

	return result, nil
}
