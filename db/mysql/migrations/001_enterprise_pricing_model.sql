USE boq_pricing;

DROP PROCEDURE IF EXISTS add_column_if_missing;

DELIMITER $$
CREATE PROCEDURE add_column_if_missing(
  IN p_table_name VARCHAR(128),
  IN p_column_name VARCHAR(128),
  IN p_column_definition TEXT
)
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = p_table_name
      AND column_name = p_column_name
  ) THEN
    SET @ddl = CONCAT('ALTER TABLE ', p_table_name, ' ADD COLUMN ', p_column_definition);
    PREPARE stmt FROM @ddl;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
  END IF;
END$$
DELIMITER ;

CALL add_column_if_missing('price_rule', 'tenant_code', 'tenant_code VARCHAR(64) NOT NULL DEFAULT ''default'' AFTER id');
CALL add_column_if_missing('price_rule', 'status', 'status VARCHAR(32) NOT NULL DEFAULT ''active'' AFTER version');
CALL add_column_if_missing('price_rule', 'project_type', 'project_type VARCHAR(64) NULL AFTER status');
CALL add_column_if_missing('price_rule', 'region_code', 'region_code VARCHAR(64) NULL AFTER project_type');
CALL add_column_if_missing('price_rule', 'specialty', 'specialty VARCHAR(64) NULL AFTER region_code');
CALL add_column_if_missing('price_rule', 'cost_category', 'cost_category VARCHAR(64) NULL AFTER specialty');
CALL add_column_if_missing('price_rule', 'pricing_method', 'pricing_method VARCHAR(32) NOT NULL DEFAULT ''fixed_unit_price'' AFTER unit_price');
CALL add_column_if_missing('price_rule', 'match_priority', 'match_priority INT NOT NULL DEFAULT 100 AFTER pricing_method');

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

CALL add_column_if_missing('pricing_run', 'tenant_code', 'tenant_code VARCHAR(64) NOT NULL DEFAULT ''default'' AFTER id');
CALL add_column_if_missing('pricing_run', 'project_name', 'project_name VARCHAR(255) NULL AFTER workbook_name');
CALL add_column_if_missing('pricing_run', 'region_code', 'region_code VARCHAR(64) NULL AFTER project_name');

INSERT IGNORE INTO feature_dictionary (canonical_key, alias_key, data_type, unit)
VALUES
  ('桩型', '桩型', 'text', NULL),
  ('桩长度', '桩长度', 'range', 'm'),
  ('混凝土强度等级', '混凝土种类与强度等级', 'text', NULL),
  ('组件型号', '组件型号', 'text', NULL),
  ('支架类型', '支架类型', 'text', NULL),
  ('路面类型', '路面类型', 'text', NULL);

DROP PROCEDURE IF EXISTS add_column_if_missing;
