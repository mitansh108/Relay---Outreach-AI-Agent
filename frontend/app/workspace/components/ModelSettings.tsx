"use client";

import { useCallback, useEffect, useState } from "react";
import { request } from "@/lib/api";

type ModelStatus = {
  provider: string;
  configured: boolean;
  model_id: string;
  status: "unconfigured" | "configured" | "connected" | "error";
  source: "environment" | "workspace" | null;
  credential_source?: "encrypted_workspace" | "environment" | null;
  last_error: string | null;
  can_save_credentials: boolean;
};

export default function ModelSettings() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const refresh = useCallback(async () => {
    const result = await request<ModelStatus>("/model");
    setStatus(result);
    setModel(result.model_id || "");
    return result;
  }, []);
  useEffect(() => { void refresh().catch(err => setError(err instanceof Error ? err.message : "Could not load model settings.")); }, [refresh]);
  const run = async (action: "save" | "test" | "clear") => {
    setBusy(true); setError(""); setNotice("");
    try {
      if (action === "save") {
        await request("/model", { method: "PUT", body: JSON.stringify({ model_id: model.trim(), ...(key.trim() ? { api_key: key.trim() } : {}) }) });
        setKey("");
      } else if (action === "test") await request("/model/test", { method: "POST" });
      else await request("/model", { method: "DELETE" });
      const latest = await refresh();
      setNotice(action === "test" ? "Model connection verified." : action === "save" ? "Model configuration saved." : latest.configured ? "Workspace configuration removed. The server environment still supplies a model." : "Model configuration removed. Recommendations will use the template fallback.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update model configuration."); }
    finally { setBusy(false); }
  };
  return <section className="panel model-settings" aria-labelledby="model-settings-title">
    <div className="model-settings-heading"><div><h3 id="model-settings-title">AI model</h3><p>Connect Groq to generate outreach from the contact’s source context. Every email still pauses for your approval.</p></div><span className={`pill ${status?.configured ? "green" : "subtle"}`}>{status?.status || "Loading"}</span></div>
    {error && <p className="model-settings-error" role="alert">{error}</p>}{notice && <p className="model-settings-notice" role="status">{notice}</p>}
    {status && <><div className="model-settings-fields"><label htmlFor="groq-model-id">Model ID<input id="groq-model-id" value={model} onChange={event => setModel(event.target.value)} disabled={busy} autoComplete="off" spellCheck={false} /></label><label htmlFor="groq-api-key">Groq API key<input id="groq-api-key" type="password" value={key} onChange={event => setKey(event.target.value)} disabled={busy || !status.can_save_credentials} autoComplete="off" placeholder={status.configured ? "Leave blank to keep the current key" : "Enter your Groq API key"} /></label></div>
    <p className="model-settings-help">{status.can_save_credentials ? "Keys are encrypted on the server and never returned to the browser." : "To save a key here, configure COPILOT_ENCRYPTION_KEY on the server. You can also configure GROQ_API_KEY and GROQ_MODEL_ID in the server environment."}</p>
    {status.source && <p className="model-settings-help">Configuration source: {status.credential_source === "environment" ? "server environment" : "encrypted workspace settings"}.</p>}
    {status.last_error && <p className="model-settings-error">{status.last_error}</p>}
    <div className="model-settings-actions"><button type="button" className="button primary" disabled={busy || !model.trim() || !status.can_save_credentials || (!status.configured && !key.trim())} onClick={() => void run("save")}>{busy ? "Working…" : "Save model settings"}</button><button type="button" className="button secondary" disabled={busy || !status.configured} onClick={() => void run("test")}>Test connection</button>{status.source === "workspace" && <button type="button" className="text-button" disabled={busy} onClick={() => void run("clear")}>Remove workspace model</button>}</div>
    {!status.configured && <p className="model-settings-help">No model connected. The credential-free sample remains available with rule-based recommendations and template drafts.</p>}</>}
  </section>;
}
