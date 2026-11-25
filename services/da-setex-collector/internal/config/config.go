package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Collector    CollectorConfig    `yaml:"collector"`
	EMQX         EMQXConfig         `yaml:"emqx"`
	Database     DatabaseConfig     `yaml:"database"`
	PilotMachine PilotMachineConfig `yaml:"pilot_machine"`
}

type CollectorConfig struct {
	Name         string `yaml:"name"`
	LogLevel     string `yaml:"log_level"`
	MultiMachine bool   `yaml:"multi_machine"`
	MaxWorkers   int    `yaml:"max_workers"`
}

type DatabaseConfig struct {
	URL string `yaml:"url"`
}

type EMQXConfig struct {
	BrokerURL            string `yaml:"broker_url"`
	ClientID             string `yaml:"client_id"`
	Username             string `yaml:"username"`
	Password             string `yaml:"password"`
	TopicTelemetryPrefix string `yaml:"topic_telemetry_prefix"`
	TopicStatusPrefix    string `yaml:"topic_status_prefix"`
}

type ObjectsConfig struct {
	EnableIW1025    bool `yaml:"enable_iw_1025"`
	EnableSET1009   bool `yaml:"enable_set_1009"`
	EnableACT1010   bool `yaml:"enable_act_1010"`
	EnableBATCH1035 bool `yaml:"enable_batch_1035"`
	EnableFunction6 bool `yaml:"enable_function_6"`
	EnableStatusAct bool `yaml:"enable_status_act"` // If false, do NOT poll STATUS.ACT
}

type PilotMachineConfig struct {
	MachineID            string        `yaml:"machine_id"`
	AssetID              string        `yaml:"asset_id"`
	ControllerIP         string        `yaml:"controller_ip"`
	TCPPort              int           `yaml:"tcp_port"`
	FTPPort              int           `yaml:"ftp_port"`
	FTPUser              string        `yaml:"ftp_user"`
	FTPPassword          string        `yaml:"ftp_password"`
	ConfigBaseDir        string        `yaml:"config_base_dir"`
	TypeconfJSONPath     string        `yaml:"typeconf_json_path"`
	Objects              ObjectsConfig `yaml:"objects"`
	TelemetryIntervalSec int           `yaml:"telemetry_interval_sec"`
	StatusActIntervalSec int           `yaml:"status_act_interval_sec"`
	BatchLogIntervalSec  int           `yaml:"batch_log_interval_sec"`
}

func LoadConfig(path string) (*Config, error) {
	bytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config file: %w", err)
	}

	var cfg Config
	if err := yaml.Unmarshal(bytes, &cfg); err != nil {
		return nil, fmt.Errorf("parse yaml config: %w", err)
	}

	if envDB := os.Getenv("DATABASE_URL"); envDB != "" {
		cfg.Database.URL = envDB
	}
	if cfg.Collector.MaxWorkers <= 0 {
		cfg.Collector.MaxWorkers = 12
	}
	if cfg.PilotMachine.TelemetryIntervalSec <= 0 {
		cfg.PilotMachine.TelemetryIntervalSec = 3
	}
	if cfg.PilotMachine.ConfigBaseDir == "" {
		cfg.PilotMachine.ConfigBaseDir = "WORKSPACE_PROGRAM_MESIN"
	}

	return &cfg, nil
}
