package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Writer   WriterConfig   `yaml:"writer"`
	EMQX     EMQXConfig     `yaml:"emqx"`
	Database DatabaseConfig `yaml:"database"`
}

type WriterConfig struct {
	Name                 string `yaml:"name"`
	LogLevel             string `yaml:"log_level"`
	BatchFlushIntervalMs int    `yaml:"batch_flush_interval_ms"`
	BatchMaxSize         int    `yaml:"batch_max_size"`
	WorkerCount          int    `yaml:"worker_count"`
	QueueSize            int    `yaml:"queue_size"`
}

type EMQXConfig struct {
	BrokerURL   string `yaml:"broker_url"`
	ClientID    string `yaml:"client_id"`
	Username    string `yaml:"username"`
	Password    string `yaml:"password"`
	SharedGroup string `yaml:"shared_group"`
	TopicFilter string `yaml:"topic_filter"`
}

type DatabaseConfig struct {
	JetflowURL string `yaml:"jetflow_url"`
	ScadaURL   string `yaml:"scada_url"`
	MaxConns   int32  `yaml:"max_conns"`
	MinConns   int32  `yaml:"min_conns"`
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

	if cfg.Writer.BatchFlushIntervalMs <= 0 {
		cfg.Writer.BatchFlushIntervalMs = 500
	}
	if cfg.Writer.BatchMaxSize <= 0 {
		cfg.Writer.BatchMaxSize = 500
	}
	if cfg.Writer.WorkerCount <= 0 {
		cfg.Writer.WorkerCount = 8
	}
	if cfg.Writer.QueueSize <= 0 {
		cfg.Writer.QueueSize = 50000
	}
	if cfg.EMQX.SharedGroup == "" {
		cfg.EMQX.SharedGroup = "db_writers"
	}
	if cfg.EMQX.TopicFilter == "" {
		cfg.EMQX.TopicFilter = "smm/jetflow/#"
	}

	return &cfg, nil
}
