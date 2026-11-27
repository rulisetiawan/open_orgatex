package setex

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strconv"
)

// RegisterMapping defines calibration and metadata for a single SETEX register (Object 1025 / IW).
type RegisterMapping struct {
	Index        int     `json:"index"`
	IWNumber     int     `json:"iw_number"`
	Name         string  `json:"name"`
	NameLocal    string  `json:"name_local"`
	Unit         string  `json:"unit"`
	DigitsBefore int     `json:"digits_before"`
	DigitsAfter  int     `json:"digits_after"`
	X1           float64 `json:"x1"`     // Engineering min
	X2           float64 `json:"x2"`     // Engineering max
	Y1           float64 `json:"y1"`     // Raw min
	Y2           float64 `json:"y2"`     // Raw max
	Factor       float64 `json:"factor"` // Scale factor
	TagName      string  `json:"tag_name"`
	TagRole      string  `json:"tag_role"`
	FieldName    string  `json:"field_name"`
}

// Calibrate converts raw register word to calibrated engineering units using linear interpolation.
// Analog SETEX IW registers (Y2 <= 32767) are signed int16; e.g. 65535 (0xFFFF) is -1 (zero-drift), not 65535.
func (rm *RegisterMapping) Calibrate(raw uint16) float64 {
	var rawF float64
	if rm.Y2 > 0 && rm.Y2 <= 32767 {
		rawF = float64(int16(raw))
	} else {
		rawF = float64(raw)
	}
	deltaY := rm.Y2 - rm.Y1
	if math.Abs(deltaY) > 1e-6 {
		val := rm.X1 + (rawF-rm.Y1)*(rm.X2-rm.X1)/deltaY
		// Clamp small negative sensor zero-drift to engineering min (e.g. -0.001 bar -> 0 bar)
		if rm.X1 >= 0 && val < rm.X1 {
			val = rm.X1
		}
		if rm.DigitsAfter >= 0 && rm.DigitsAfter <= 4 {
			pow := math.Pow(10, float64(rm.DigitsAfter))
			return math.Round(val*pow) / pow
		}
		return val
	}

	if rm.Factor > 0 {
		return rawF / rm.Factor
	}
	return rawF
}

// ParameterScale defines calibration scaling for Object 1009 SET parameters.
type ParameterScale struct {
	DigitsBefore int     `json:"digits_before"`
	DigitsAfter  int     `json:"digits_after"`
	Factor       float64 `json:"factor"`
	Offset       float64 `json:"offset"`
	X1           float64 `json:"x1"`
	X2           float64 `json:"x2"`
	Y1           float64 `json:"y1"`
	Y2           float64 `json:"y2"`
	Mode         int     `json:"mode"`
}

// ParameterConfig defines a recipe setpoint parameter from typeconf_functions.json (Object 1009).
type ParameterConfig struct {
	ID        int            `json:"id"`
	Name      string         `json:"name"`
	NameLocal string         `json:"name_local"`
	Unit      string         `json:"unit"`
	UnitLocal string         `json:"unit_local"`
	Scale     ParameterScale `json:"scale"`
	TagName   string         `json:"tag_name,omitempty"`
	TagRole   string         `json:"tag_role,omitempty"`
}

// Calibrate converts raw uint16 parameter value to calibrated engineering unit.
func (pc *ParameterConfig) Calibrate(raw uint16) float64 {
	rawF := float64(raw)
	deltaY := pc.Scale.Y2 - pc.Scale.Y1
	if math.Abs(deltaY) > 1e-6 {
		val := pc.Scale.X1 + (rawF-pc.Scale.Y1)*(pc.Scale.X2-pc.Scale.X1)/deltaY
		if pc.Scale.DigitsAfter >= 0 && pc.Scale.DigitsAfter <= 4 {
			pow := math.Pow(10, float64(pc.Scale.DigitsAfter))
			return math.Round(val*pow) / pow
		}
		return val
	}

	if pc.Scale.Factor > 0 {
		val := rawF / pc.Scale.Factor
		if pc.Scale.DigitsAfter >= 0 && pc.Scale.DigitsAfter <= 4 {
			pow := math.Pow(10, float64(pc.Scale.DigitsAfter))
			return math.Round(val*pow) / pow
		}
		return val
	}
	return rawF
}

// FunctionParamRef defines parameter reference inside a recipe function.
type FunctionParamRef struct {
	DefinitionID    int     `json:"definition_id"`
	DisplayPosition int     `json:"display_position"`
	Minimum         float64 `json:"minimum"`
	Maximum         float64 `json:"maximum"`
	Default         float64 `json:"default"`
}

// FunctionConfig defines an active recipe function from Object 6.
type FunctionConfig struct {
	ID             int                `json:"id"`
	Name           string             `json:"name"`
	NameLocal      string             `json:"name_local"`
	ParameterCount int                `json:"parameter_count"`
	Parameters     []FunctionParamRef `json:"parameters"`
}

// MachineProfile holds controller profile from machine_profile.json.
type MachineProfile struct {
	MachineNo      string  `json:"machine_no"`
	FolderName     string  `json:"folder_name"`
	ControllerType string  `json:"controller_type"`
	IPAddress      string  `json:"ip_address"`
	AssetID        string  `json:"asset_id"`
	MaxTempC       float64 `json:"max_temp_c"`
}

// MachineConfigBundle holds the complete loaded configuration for a machine.
type MachineConfigBundle struct {
	MachineID  string
	AssetID    string
	Profile    *MachineProfile
	IWMap      map[int]*RegisterMapping
	Parameters map[int]*ParameterConfig
	Functions  map[int]*FunctionConfig
}

// TypeconfFunctionsFile represents the root of typeconf_functions.json.
type TypeconfFunctionsFile struct {
	Functions  map[string]*FunctionConfig  `json:"functions"`
	Parameters map[string]*ParameterConfig `json:"parameters"`
}

// LoadMachineConfig loads all JSON configuration files for a machine from config_base_dir.
func LoadMachineConfig(baseDir, machineID string) (*MachineConfigBundle, error) {
	bundle := &MachineConfigBundle{
		MachineID:  machineID,
		IWMap:      make(map[int]*RegisterMapping),
		Parameters: make(map[int]*ParameterConfig),
		Functions:  make(map[int]*FunctionConfig),
	}

	// Try resolving machine folder (e.g. WORKSPACE_PROGRAM_MESIN/MESIN_10B/02_CONFIG_SIAP_PAKAI)
	folderVariants := []string{
		filepath.Join(baseDir, fmt.Sprintf("MESIN_%s", machineID), "02_CONFIG_SIAP_PAKAI"),
		filepath.Join(baseDir, machineID, "02_CONFIG_SIAP_PAKAI"),
		filepath.Join("WORKSPACE_PROGRAM_MESIN", fmt.Sprintf("MESIN_%s", machineID), "02_CONFIG_SIAP_PAKAI"),
		filepath.Join("..", "..", "WORKSPACE_PROGRAM_MESIN", fmt.Sprintf("MESIN_%s", machineID), "02_CONFIG_SIAP_PAKAI"),
	}

	var targetDir string
	for _, f := range folderVariants {
		if fi, err := os.Stat(f); err == nil && fi.IsDir() {
			targetDir = f
			break
		}
	}

	if targetDir == "" {
		return nil, fmt.Errorf("config directory not found for machine %s in base %s", machineID, baseDir)
	}

	// 1. Load machine_profile.json
	profilePath := filepath.Join(targetDir, "machine_profile.json")
	if bytes, err := os.ReadFile(profilePath); err == nil {
		var prof MachineProfile
		if err := json.Unmarshal(bytes, &prof); err == nil {
			bundle.Profile = &prof
			if prof.AssetID != "" {
				bundle.AssetID = prof.AssetID
			}
		}
	}

	// 2. Load typeconf_iw_map.json (Object 1025)
	iwPath := filepath.Join(targetDir, "typeconf_iw_map.json")
	if bytes, err := os.ReadFile(iwPath); err == nil {
		var rawMap map[string]*RegisterMapping
		if err := json.Unmarshal(bytes, &rawMap); err == nil {
			for k, v := range rawMap {
				idx, err := strconv.Atoi(k)
				if err != nil || idx <= 0 {
					continue
				}
				v.Index = idx
				v.IWNumber = idx
				bundle.IWMap[idx] = v
			}
		}
	}

	// 3. Load typeconf_functions.json (Object 1009 Parameters & Object 6 Functions)
	fnPath := filepath.Join(targetDir, "typeconf_functions.json")
	if bytes, err := os.ReadFile(fnPath); err == nil {
		var fnFile TypeconfFunctionsFile
		if err := json.Unmarshal(bytes, &fnFile); err == nil {
			for k, v := range fnFile.Parameters {
				pID, err := strconv.Atoi(k)
				if err != nil || pID <= 0 {
					continue
				}
				v.ID = pID
				bundle.Parameters[pID] = v
			}
			for k, v := range fnFile.Functions {
				fID, err := strconv.Atoi(k)
				if err != nil || fID <= 0 {
					continue
				}
				v.ID = fID
				bundle.Functions[fID] = v
			}
		}
	}

	return bundle, nil
}
