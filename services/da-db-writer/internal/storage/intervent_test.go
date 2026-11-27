package storage

import (
	"encoding/json"
	"testing"
)

func sampleProgramJSON() json.RawMessage {
	return json.RawMessage(`[
		{
			"no": 28,
			"sv": 60,
			"min": 25,
			"step": "Temperature Control",
			"func_id": 141,
			"slots": [
				{
					"slot": 1,
					"main": true,
					"func": "Temperature Control",
					"func_id": 141,
					"resource": "main tank",
					"params": [
						{"name": "Temperature MA", "value": "60 °C"},
						{"name": "Gradient MA", "value": "0 °C/min"},
						{"name": "Time MA", "value": "25 min"}
					]
				}
			]
		}
	]`)
}

func TestMergeAndPreserveInterventions(t *testing.T) {
	prog := sampleProgramJSON()

	// 1. First operator change: Temperature MA 60 -> 65
	ev1 := []ActInterventionEvent{
		{
			Type:          "PARAM_CHANGED",
			DetectedAt:    "2026-11-27T12:12:05+07:00",
			StepNo:        28,
			Slot:          1,
			FuncID:        141,
			Func:          "Temperature Control",
			ParamIndex:    0,
			ParameterName: "Temperature MA",
			Unit:          "°C",
			Before:        60,
			After:         65,
			Delta:         5,
			AlarmCode:     0,
		},
	}
	prog1, cnt1, ch1 := mergeInterventionsIntoProgram(prog, ev1)
	if !ch1 || cnt1 != 1 {
		t.Fatalf("expected changed=true count=1, got changed=%v count=%d", ch1, cnt1)
	}

	// 2. Duplicate poll with same event -> must NOT duplicate
	progDup, cntDup, chDup := mergeInterventionsIntoProgram(prog1, ev1)
	if chDup || cntDup != 1 {
		t.Fatalf("expected duplicate ignored (changed=false, count=1), got changed=%v count=%d", chDup, cntDup)
	}

	// 3. Second change on same param (65 -> 70) + Time MA (25 -> 30) + Step Jump Back (28 -> 25)
	ev2 := []ActInterventionEvent{
		{
			Type:          "PARAM_CHANGED",
			DetectedAt:    "2026-11-27T12:18:10+07:00",
			StepNo:        28,
			Slot:          1,
			FuncID:        141,
			ParamIndex:    0,
			ParameterName: "Temperature MA",
			Unit:          "°C",
			Before:        65,
			After:         70,
			Delta:         5,
			AlarmCode:     438,
		},
		{
			Type:          "PARAM_CHANGED",
			DetectedAt:    "2026-11-27T12:18:10+07:00",
			StepNo:        28,
			Slot:          1,
			FuncID:        141,
			ParamIndex:    2,
			ParameterName: "Time MA",
			Unit:          "min",
			Before:        25,
			After:         30,
			Delta:         5,
			AlarmCode:     0,
		},
		{
			Type:       "STEP_JUMP_BACK",
			DetectedAt: "2026-11-27T12:22:00+07:00",
			StepNo:     28,
			FromStep:   28,
			ToStep:     25,
			AlarmCode:  0,
		},
	}
	prog2, cnt2, ch2 := mergeInterventionsIntoProgram(progDup, ev2)
	if !ch2 || cnt2 != 4 {
		t.Fatalf("expected changed=true count=4, got changed=%v count=%d", ch2, cnt2)
	}

	// Verify structure inside program[0]
	var steps []map[string]interface{}
	if err := json.Unmarshal(prog2, &steps); err != nil {
		t.Fatalf("unmarshal updated program: %v", err)
	}
	if steps[0]["has_intervention"] != true {
		t.Fatalf("expected has_intervention=true on step 28")
	}
	slots := steps[0]["slots"].([]interface{})
	params := slots[0].(map[string]interface{})["params"].([]interface{})
	tempParam := params[0].(map[string]interface{})
	gradParam := params[1].(map[string]interface{})
	timeParam := params[2].(map[string]interface{})

	if tempParam["changed"] != true || tempParam["actual_value"] != "70 °C" {
		t.Fatalf("unexpected tempParam: %+v", tempParam)
	}
	if len(tempParam["interventions"].([]interface{})) != 2 {
		t.Fatalf("expected 2 interventions on Temperature MA, got %d", len(tempParam["interventions"].([]interface{})))
	}
	if _, hasChanged := gradParam["changed"]; hasChanged {
		t.Fatalf("expected Gradient MA untouched, got %+v", gradParam)
	}
	if timeParam["actual_value"] != "30 min" {
		t.Fatalf("expected Time MA actual_value='30 min', got %v", timeParam["actual_value"])
	}

	// 4. Preserve interventions when IngestBatchProgram sends fresh program JSON
	fresh := sampleProgramJSON()
	preserved, preservedCnt := preserveProgramInterventions(prog2, fresh)
	if preservedCnt != 4 {
		t.Fatalf("expected preserved count=4, got %d", preservedCnt)
	}
	var pSteps []map[string]interface{}
	_ = json.Unmarshal(preserved, &pSteps)
	if pSteps[0]["has_intervention"] != true {
		t.Fatalf("expected preserved has_intervention=true")
	}
}
