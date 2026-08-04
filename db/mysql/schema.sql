CREATE DATABASE IF NOT EXISTS boq_pricing
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE boq_pricing;

CREATE TABLE IF NOT EXISTS price_rule (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_code VARCHAR(64) NOT NULL DEFAULT 'default',
  rule_code VARCHAR(128) NOT NULL,
  version VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  project_type VARCHAR(64) NULL,
  region_code VARCHAR(64) NULL,
  specialty VARCHAR(64) NULL,
  cost_category VARCHAR(64) NULL,
  item_name_contains VARCHAR(255) NOT NULL,
  unit VARCHAR(32) NULL,
  feature_conditions_json JSON NOT NULL,
  unit_price DECIMAL(18, 4) NOT NULL,
  pricing_method VARCHAR(32) NOT NULL DEFAULT 'fixed_unit_price',
  match_priority INT NOT NULL DEFAULT 100,
  source VARCHAR(255) NOT NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  effective_from DATE NULL,
  effective_to DATE NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_price_rule_tenant_code_version (tenant_code, rule_code, version),
  KEY idx_price_rule_active_name_unit (tenant_code, active, item_name_contains, unit),
  KEY idx_price_rule_scope (tenant_code, active, region_code, specialty, cost_category),
  KEY idx_price_rule_version (version),
  CONSTRAINT chk_price_rule_unit_price_non_negative CHECK (unit_price >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS price_rule_condition (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  price_rule_id BIGINT UNSIGNED NOT NULL,
  feature_key VARCHAR(128) NOT NULL,
  operator VARCHAR(32) NOT NULL DEFAULT 'contains',
  expected_value VARCHAR(512) NOT NULL,
  weight DECIMAL(8, 4) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_rule_condition (price_rule_id, feature_key, operator, expected_value),
  KEY idx_condition_feature_key (feature_key),
  KEY idx_condition_expected_value (expected_value),
  CONSTRAINT fk_condition_price_rule
    FOREIGN KEY (price_rule_id) REFERENCES price_rule(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS price_rule_component (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  price_rule_id BIGINT UNSIGNED NOT NULL,
  component_type VARCHAR(64) NOT NULL,
  component_name VARCHAR(255) NOT NULL,
  unit VARCHAR(32) NULL,
  quantity DECIMAL(18, 6) NOT NULL DEFAULT 1,
  unit_price DECIMAL(18, 4) NOT NULL DEFAULT 0,
  amount DECIMAL(18, 4) GENERATED ALWAYS AS (quantity * unit_price) STORED,
  source VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_component_rule (price_rule_id),
  KEY idx_component_type (component_type),
  CONSTRAINT fk_component_price_rule
    FOREIGN KEY (price_rule_id) REFERENCES price_rule(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feature_dictionary (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  canonical_key VARCHAR(128) NOT NULL,
  alias_key VARCHAR(128) NOT NULL,
  data_type VARCHAR(32) NOT NULL DEFAULT 'text',
  unit VARCHAR(32) NULL,
  active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_feature_alias (alias_key),
  KEY idx_feature_canonical_key (canonical_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS material_price (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_code VARCHAR(64) NOT NULL DEFAULT 'default',
  material_code VARCHAR(128) NULL,
  material_name VARCHAR(255) NOT NULL,
  specification VARCHAR(255) NULL,
  region_code VARCHAR(64) NULL,
  unit VARCHAR(32) NOT NULL,
  unit_price DECIMAL(18, 4) NOT NULL,
  price_month CHAR(7) NOT NULL,
  source VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_material_lookup (tenant_code, material_name, specification, region_code, price_month),
  KEY idx_material_code (tenant_code, material_code),
  CONSTRAINT chk_material_price_non_negative CHECK (unit_price >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pricing_run (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_code VARCHAR(64) NOT NULL DEFAULT 'default',
  run_code VARCHAR(64) NOT NULL,
  workbook_name VARCHAR(255) NOT NULL,
  project_name VARCHAR(255) NULL,
  region_code VARCHAR(64) NULL,
  rule_source VARCHAR(32) NOT NULL,
  rule_version VARCHAR(64) NULL,
  item_count INT NOT NULL DEFAULT 0,
  priced_count INT NOT NULL DEFAULT 0,
  unpriced_count INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_pricing_run_code (tenant_code, run_code),
  KEY idx_pricing_run_created_at (tenant_code, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pricing_result (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id BIGINT UNSIGNED NOT NULL,
  source_sheet VARCHAR(255) NOT NULL,
  source_row_number INT NOT NULL,
  sequence_no VARCHAR(64) NULL,
  item_code VARCHAR(64) NULL,
  item_name VARCHAR(255) NOT NULL,
  unit VARCHAR(32) NULL,
  quantity DECIMAL(18, 4) NULL,
  unit_price DECIMAL(18, 4) NULL,
  total_price DECIMAL(18, 2) NULL,
  rule_code VARCHAR(128) NULL,
  rule_version VARCHAR(64) NULL,
  price_source VARCHAR(255) NULL,
  confidence DECIMAL(6, 4) NOT NULL DEFAULT 0,
  features_json JSON NOT NULL,
  issues_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_pricing_result_run_id (run_id),
  KEY idx_pricing_result_item_name (item_name),
  KEY idx_pricing_result_rule_code (rule_code),
  CONSTRAINT fk_pricing_result_run
    FOREIGN KEY (run_id) REFERENCES pricing_run(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;
