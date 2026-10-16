CREATE TABLE IF NOT EXISTS bgl_logs (
  event_id VARCHAR PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL,
  dataset VARCHAR NOT NULL DEFAULT 'bgl',
  component VARCHAR NOT NULL,
  severity VARCHAR,
  node_id VARCHAR,
  request_id VARCHAR,
  event_template VARCHAR,
  message VARCHAR NOT NULL,
  anomaly_label VARCHAR,
  raw_line VARCHAR
);

CREATE TABLE IF NOT EXISTS openstack_logs (
  event_id VARCHAR PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL,
  dataset VARCHAR NOT NULL DEFAULT 'openstack',
  component VARCHAR NOT NULL,
  severity VARCHAR,
  node_id VARCHAR,
  request_id VARCHAR,
  event_template VARCHAR,
  message VARCHAR NOT NULL,
  anomaly_label VARCHAR,
  latency_ms DOUBLE,
  tenant_id VARCHAR,
  raw_line VARCHAR
);

CREATE TABLE IF NOT EXISTS component_ownership (
  dataset VARCHAR NOT NULL,
  component VARCHAR NOT NULL,
  team VARCHAR NOT NULL,
  PRIMARY KEY (dataset, component)
);

CREATE TEXT SEARCH DICTIONARY IF NOT EXISTS log_english AS
  split_text(case := 'lower') WITH (frequency, position, offset);

CREATE INDEX IF NOT EXISTS bgl_logs_idx ON bgl_logs
  USING inverted(event_id, timestamp, component, severity, node_id, request_id,
                 event_template log_english, message log_english);

CREATE INDEX IF NOT EXISTS openstack_logs_idx ON openstack_logs
  USING inverted(event_id, timestamp, component, severity, node_id, request_id,
                 event_template log_english, message log_english);

VACUUM (REFRESH_TABLE) bgl_logs;
VACUUM (REFRESH_TABLE) openstack_logs;

