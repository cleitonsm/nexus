-- Esquema minimo e dados ficticios para ensaiar backup.sh e restore.sh
-- (scripts/validation/backup-scripts-check.sh). Nao e o esquema real: so as
-- tabelas que os scripts leem.
CREATE TABLE app_settings (key_name varchar(64) primary key, value json not null, updated_by varchar(128), updated_at timestamptz not null);
CREATE TABLE ingestion_jobs (id text primary key, status varchar(16), reserved_at timestamptz);
CREATE TABLE reindex_jobs (id text primary key, status varchar(16), lease_expires_at timestamptz);
CREATE TABLE assistants (id text primary key, name text);
CREATE TABLE documents (id text primary key, assistant_id text);
CREATE TABLE conversations (id text primary key);
CREATE TABLE messages (id text primary key, conversation_id text);
CREATE TABLE assistant_groups (assistant_id text, group_name text);
CREATE TABLE document_groups (document_id text, group_name text);
CREATE TABLE audit_events (id text primary key);
CREATE TABLE usage_records (id text primary key);
CREATE TABLE message_feedback (id text primary key);
INSERT INTO assistants VALUES ('a1','RH'),('a2','Financeiro');
INSERT INTO documents VALUES ('d1','a1'),('d2','a1'),('d3','a2');
INSERT INTO conversations VALUES ('c1');
INSERT INTO messages VALUES ('m1','c1'),('m2','c1');
INSERT INTO assistant_groups VALUES ('a1','rh');
INSERT INTO audit_events SELECT 'e'||g FROM generate_series(1,7) g;
INSERT INTO usage_records VALUES ('u1');
