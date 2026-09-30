-- Fresh Supabase install. Preserve the legacy SQLite database separately.
-- Run with the database owner through Supabase SQL Editor or the CLI.
BEGIN;
CREATE SCHEMA IF NOT EXISTS relay;
REVOKE ALL ON SCHEMA relay FROM PUBLIC, anon, authenticated;
SET LOCAL search_path = relay;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'relay_app') THEN
    CREATE ROLE relay_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  END IF;
END $$;
GRANT USAGE ON SCHEMA relay TO relay_app;



CREATE TABLE connections (
	sender_email VARCHAR,
	workspace_id VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	last_sync_at TIMESTAMP WITH TIME ZONE,
	last_error TEXT,
	sync_count INTEGER NOT NULL,
	PRIMARY KEY (workspace_id, provider)
)

;


CREATE TABLE contacts (
	id VARCHAR NOT NULL,
	source VARCHAR NOT NULL,
	source_id VARCHAR,
	name VARCHAR NOT NULL,
	contact VARCHAR NOT NULL,
	company VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	interest_level VARCHAR NOT NULL,
	notes TEXT NOT NULL,
	deal_context TEXT NOT NULL,
	last_interaction VARCHAR,
	next_followup VARCHAR,
	do_not_contact BOOLEAN NOT NULL,
	replied BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, source_id)
)

;

CREATE INDEX ix_contacts_workspace_id ON contacts (workspace_id);


CREATE TABLE experiments (
	id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	config TEXT NOT NULL,
	status VARCHAR NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_experiments_workspace_id ON experiments (workspace_id);


CREATE TABLE model_configuration (
	workspace_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	model_id VARCHAR NOT NULL,
	encrypted_key TEXT,
	status VARCHAR NOT NULL,
	last_error TEXT,
	PRIMARY KEY (workspace_id, id)
)

;


CREATE TABLE oauth_credentials (
	workspace_id VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	encrypted_token TEXT NOT NULL,
	encrypted_refresh_token TEXT,
	expires_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (workspace_id, provider)
)

;


CREATE TABLE oauth_pending (
	user_id VARCHAR,
	state VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	code_verifier VARCHAR,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (state)
)

;

CREATE INDEX ix_oauth_pending_workspace_id ON oauth_pending (workspace_id);


CREATE TABLE workspaces (
	owner_user_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
)

;


CREATE TABLE experiment_assignments (
	id VARCHAR NOT NULL,
	experiment_id VARCHAR NOT NULL,
	contact_id VARCHAR NOT NULL,
	variant_id VARCHAR NOT NULL,
	exposed_at TIMESTAMP WITH TIME ZONE,
	replied_at TIMESTAMP WITH TIME ZONE,
	converted_at TIMESTAMP WITH TIME ZONE,
	opted_out_at TIMESTAMP WITH TIME ZONE,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, experiment_id, contact_id),
	FOREIGN KEY(experiment_id) REFERENCES experiments (id),
	FOREIGN KEY(contact_id) REFERENCES contacts (id)
)

;

CREATE INDEX ix_experiment_assignments_workspace_id ON experiment_assignments (workspace_id);


CREATE TABLE recommendations (
	id VARCHAR NOT NULL,
	contact_id VARCHAR NOT NULL,
	action VARCHAR NOT NULL,
	reason TEXT NOT NULL,
	sources TEXT NOT NULL,
	status VARCHAR NOT NULL,
	subject VARCHAR,
	body TEXT,
	version INTEGER NOT NULL,
	approved_version INTEGER,
	approved_recipient VARCHAR,
	model_id VARCHAR NOT NULL,
	experiment_id VARCHAR,
	variant_id VARCHAR,
	prompt_version VARCHAR NOT NULL,
	audit TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(contact_id) REFERENCES contacts (id)
)

;

CREATE INDEX ix_recommendations_workspace_id ON recommendations (workspace_id);

CREATE INDEX ix_recommendations_contact_id ON recommendations (contact_id);


CREATE TABLE workspace_memberships (
	workspace_id VARCHAR NOT NULL,
	user_id VARCHAR NOT NULL,
	role VARCHAR NOT NULL,
	PRIMARY KEY (workspace_id, user_id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
)

;


CREATE TABLE activities (
	id VARCHAR NOT NULL,
	contact_id VARCHAR,
	recommendation_id VARCHAR,
	kind VARCHAR NOT NULL,
	detail TEXT NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(contact_id) REFERENCES contacts (id),
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id)
)

;

CREATE INDEX ix_activities_contact_id ON activities (contact_id);

CREATE INDEX ix_activities_workspace_id ON activities (workspace_id);


CREATE TABLE send_attempts (
	id VARCHAR NOT NULL,
	recommendation_id VARCHAR NOT NULL,
	recipient VARCHAR NOT NULL,
	draft_version INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	provider_id VARCHAR,
	error TEXT,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	workspace_id VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (recommendation_id),
	FOREIGN KEY(recommendation_id) REFERENCES recommendations (id)
)

;

CREATE INDEX ix_send_attempts_workspace_id ON send_attempts (workspace_id);


CREATE FUNCTION relay.is_workspace_member(target text) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = relay
AS $$ SELECT EXISTS (SELECT 1 FROM workspace_memberships
  WHERE workspace_id = target AND user_id = current_setting('app.user_id', true)) $$;
GRANT EXECUTE ON FUNCTION relay.is_workspace_member(text) TO relay_app;
REVOKE EXECUTE ON FUNCTION relay.is_workspace_member(text) FROM PUBLIC;

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_read ON workspaces FOR SELECT TO relay_app USING
 (owner_user_id = current_setting('app.user_id', true) OR relay.is_workspace_member(id));
CREATE POLICY workspace_create ON workspaces FOR INSERT TO relay_app WITH CHECK
 (owner_user_id = current_setting('app.user_id', true) AND owner_user_id <> '');
ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_read ON workspace_memberships FOR SELECT TO relay_app USING
 (user_id = current_setting('app.user_id', true));
CREATE POLICY membership_create ON workspace_memberships FOR INSERT TO relay_app WITH CHECK
 (user_id = current_setting('app.user_id', true) AND role = 'owner'
  AND EXISTS (SELECT 1 FROM workspaces WHERE id = workspace_id AND owner_user_id = current_setting('app.user_id', true)));


ALTER TABLE connections ENABLE ROW LEVEL SECURITY;

ALTER TABLE connections FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON connections TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE connections ADD CONSTRAINT connections_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;

ALTER TABLE recommendations FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON recommendations TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE recommendations ADD CONSTRAINT recommendations_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE recommendations ADD CONSTRAINT recommendations_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE send_attempts ENABLE ROW LEVEL SECURITY;

ALTER TABLE send_attempts FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON send_attempts TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE send_attempts ADD CONSTRAINT send_attempts_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE send_attempts ADD CONSTRAINT send_attempts_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE model_configuration ENABLE ROW LEVEL SECURITY;

ALTER TABLE model_configuration FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON model_configuration TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE model_configuration ADD CONSTRAINT model_configuration_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;

ALTER TABLE experiments FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON experiments TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE experiments ADD CONSTRAINT experiments_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE experiments ADD CONSTRAINT experiments_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE activities ENABLE ROW LEVEL SECURITY;

ALTER TABLE activities FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON activities TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE activities ADD CONSTRAINT activities_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE activities ADD CONSTRAINT activities_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE experiment_assignments ENABLE ROW LEVEL SECURITY;

ALTER TABLE experiment_assignments FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON experiment_assignments TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE experiment_assignments ADD CONSTRAINT experiment_assignments_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE experiment_assignments ADD CONSTRAINT experiment_assignments_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

ALTER TABLE contacts FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON contacts TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE contacts ADD CONSTRAINT contacts_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE contacts ADD CONSTRAINT contacts_workspace_id_unique UNIQUE (workspace_id, id);

ALTER TABLE oauth_credentials ENABLE ROW LEVEL SECURITY;

ALTER TABLE oauth_credentials FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON oauth_credentials TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

ALTER TABLE oauth_credentials ADD CONSTRAINT oauth_credentials_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE oauth_pending ENABLE ROW LEVEL SECURITY;

ALTER TABLE oauth_pending FORCE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON oauth_pending TO relay_app
 USING (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id))
 WITH CHECK (workspace_id = current_setting('app.workspace_id', true) AND relay.is_workspace_member(workspace_id));

CREATE POLICY oauth_callback_lookup ON oauth_pending FOR SELECT TO relay_app
 USING (state = current_setting('app.oauth_state', true) AND expires_at > now());

ALTER TABLE oauth_pending ADD CONSTRAINT oauth_pending_workspace_fk FOREIGN KEY (workspace_id) REFERENCES workspaces(id);

ALTER TABLE recommendations ADD CONSTRAINT recommendations_contact_id_workspace_fk FOREIGN KEY (workspace_id, contact_id) REFERENCES contacts(workspace_id, id);

ALTER TABLE send_attempts ADD CONSTRAINT send_attempts_recommendation_id_workspace_fk FOREIGN KEY (workspace_id, recommendation_id) REFERENCES recommendations(workspace_id, id);

ALTER TABLE activities ADD CONSTRAINT activities_contact_id_workspace_fk FOREIGN KEY (workspace_id, contact_id) REFERENCES contacts(workspace_id, id);

ALTER TABLE activities ADD CONSTRAINT activities_recommendation_id_workspace_fk FOREIGN KEY (workspace_id, recommendation_id) REFERENCES recommendations(workspace_id, id);

ALTER TABLE experiment_assignments ADD CONSTRAINT experiment_assignments_experiment_id_workspace_fk FOREIGN KEY (workspace_id, experiment_id) REFERENCES experiments(workspace_id, id);

ALTER TABLE experiment_assignments ADD CONSTRAINT experiment_assignments_contact_id_workspace_fk FOREIGN KEY (workspace_id, contact_id) REFERENCES contacts(workspace_id, id);


REVOKE ALL ON ALL TABLES IN SCHEMA relay FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA relay TO relay_app;
REVOKE UPDATE, DELETE ON workspaces, workspace_memberships FROM relay_app;
COMMIT;
-- Configure LOGIN and a strong password for relay_app separately. Never use
-- postgres/service-role credentials for the running API. See SUPABASE.md.
