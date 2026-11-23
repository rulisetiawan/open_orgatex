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
	Name     string `yaml:"name"`
	LogLevel string `yaml:"log_level"`
}

type EMQXConfig struct {
	BrokerURL            string `yaml:"broker_url"`
	ClientID             string `yaml:"client_id"`
	Username             string `yaml:"username"`
	Password             string `yaml:"password"`
	TopicTelemetryPrefix string `yaml:"topic_telemetry_prefix"`
	TopicStatusPrefix    string `yaml:"topic_status_prefix"`
}

type DatabaseConfig struct {
	JetflowURL string `yaml:"jetflow_url"`
	ScadaURL   string `yaml:"scada_url"`
	MaxConns   int32  `yaml:"max_conns"`
	MinConns   int32  `yaml:"min_conns"`
}

type PilotMachineConfig struct {
	MachineID            string `yaml:"machine_id"`
	AssetID              string `yaml:"asset_id"`
	ControllerIP         string `yaml:"controller_ip"`
	TCPPort              int    `yaml:"tcp_port"`
	FTPPort              int    `yaml:"ftp_port"`
	FTPUser              string `yaml:"ftp_user"`
	FTPPassword          string `yaml:"ftp_password"`
	TypeconfJSONPath     string `yaml:"typeconf_json_path"`
	TelemetryIntervalSec int    `yaml:"telemetry_interval_sec"`
	StatusActIntervalSec int    `yaml:"status_act_interval_sec"`
	BatchLogIntervalSec  int    `yaml:"batch_log_interval_sec"`
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

	if cfg.PilotMachine.TelemetryIntervalSec <= 0 {
		cfg.PilotMachine.TelemetryIntervalSec = 2
	}
	if cfg.PilotMachine.StatusActIntervalSec <= 0 {
		cfg.PilotMachine.StatusActIntervalSec = 5
	}
	if cfg.PilotMachine.BatchLogIntervalSec <= 0 {
		cfg.PilotMachine.BatchLogIntervalSec = 60
	}

	return &cfg, nil
}
