import { useEffect, useMemo, useState } from "react";
import type {
  CoachPolicyDocument,
  CoachPolicyEvent,
  CoachPolicyRule,
} from "@uniqa-conversion-coach/shared";
import type { CoachCta, CoachCtaType, CoachPlacement } from "@uniqa-conversion-coach/shared/contracts";

type TabKey = "overview" | "interventions" | "rules" | "versions";

interface AdminUser {
  id: string;
  email: string;
  name: string | null;
}

interface PolicyRecord {
  id: string;
  version: number;
  isActive: boolean;
  policy: CoachPolicyDocument;
  createdAt: string;
  updatedAt: string;
  restoredFromPolicyVersionId: string | null;
}

interface PolicySummary {
  id: string;
  version: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  restoredFromPolicyVersionId: string | null;
}

const POLICY_EVENTS: CoachPolicyEvent[] = [
  "long_dwell",
  "back_nav",
  "repeated_change",
  "cancel_intent",
  "price_fixation",
  "oos_tariff",
  "oos_path",
  "price_gap_shock",
  "none",
];

const PLACEMENTS: CoachPlacement[] = [
  "inline-top-of-step",
  "near-primary-cta",
  "bottom-toast",
];

const CTA_TYPES: CoachCtaType[] = [
  "select_tariff",
  "continue",
  "focus_field",
  "open_chat",
  "advisor_handoff",
  "save_progress",
];

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [email, setEmail] = useState("admin@uniqa.local");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState("change-me-now");
  const [policyRecord, setPolicyRecord] = useState<PolicyRecord | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedInterventionId, setSelectedInterventionId] = useState<string | null>(null);
  const [selectedRuleIndex, setSelectedRuleIndex] = useState(0);
  const [user, setUser] = useState<AdminUser | null>(null);
  const [versions, setVersions] = useState<PolicySummary[]>([]);

  useEffect(() => {
    void loadInitialState();
  }, []);

  useEffect(() => {
    if (!policyRecord) {
      return;
    }

    const interventionIds = Object.keys(policyRecord.policy.interventions);
    if (!selectedInterventionId || !(selectedInterventionId in policyRecord.policy.interventions)) {
      setSelectedInterventionId(interventionIds[0] ?? null);
    }
    if (selectedRuleIndex > policyRecord.policy.rules.length - 1) {
      setSelectedRuleIndex(Math.max(0, policyRecord.policy.rules.length - 1));
    }
  }, [policyRecord, selectedInterventionId, selectedRuleIndex]);

  const selectedIntervention = useMemo(() => {
    if (!policyRecord || !selectedInterventionId) {
      return null;
    }
    return policyRecord.policy.interventions[selectedInterventionId] ?? null;
  }, [policyRecord, selectedInterventionId]);

  const selectedRule = policyRecord?.policy.rules[selectedRuleIndex] ?? null;

  async function loadInitialState(): Promise<void> {
    setLoading(true);
    try {
      const me = await apiGet<{ user: AdminUser }>("/api/v1/admin/me");
      setUser(me.user);
      await loadWorkspaceState();
    } catch {
      setUser(null);
      setPolicyRecord(null);
      setVersions([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadWorkspaceState(): Promise<void> {
    const [policy, policyVersions] = await Promise.all([
      apiGet<PolicyRecord>("/api/v1/admin/policy"),
      apiGet<{ policies: PolicySummary[] }>("/api/v1/admin/policies"),
    ]);
    setPolicyRecord(policy);
    setVersions(policyVersions.policies);
  }

  async function handleLogin(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setLoading(true);
    try {
      const result = await apiPost<{ user: AdminUser }>("/api/v1/admin/login", {
        email,
        password,
      });
      setUser(result.user);
      await loadWorkspaceState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout(): Promise<void> {
    await apiPost("/api/v1/admin/logout", {});
    setUser(null);
    setPolicyRecord(null);
    setVersions([]);
  }

  async function handleSavePolicy(): Promise<void> {
    if (!policyRecord) {
      return;
    }

    setSaving(true);
    setErrorMessage(null);
    try {
      const result = await apiPut<PolicyRecord>("/api/v1/admin/policy", policyRecord.policy);
      setPolicyRecord(result);
      await loadWorkspaceState();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleRestoreVersion(id: string): Promise<void> {
    setSaving(true);
    setErrorMessage(null);
    try {
      const result = await apiPost<PolicyRecord>(`/api/v1/admin/policies/${id}/restore`, {});
      setPolicyRecord(result);
      await loadWorkspaceState();
      setActiveTab("overview");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Restore failed");
    } finally {
      setSaving(false);
    }
  }

  function updatePolicy(mutator: (current: CoachPolicyDocument) => CoachPolicyDocument): void {
    setPolicyRecord((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        policy: mutator(current.policy),
      };
    });
  }

  function updateRuleAt(index: number, updater: (rule: CoachPolicyRule) => CoachPolicyRule): void {
    updatePolicy((current) => ({
      ...current,
      rules: current.rules.map((rule, ruleIndex) => (ruleIndex === index ? updater(rule) : rule)),
    }));
  }

  function buildCta(
    intervention: CoachPolicyDocument["interventions"][string],
    interventionId: string,
    overrides: Partial<CoachCta> = {},
  ): CoachCta {
    return {
      label: overrides.label ?? intervention.cta?.label ?? intervention.ctaLabel ?? "Open coach",
      prompt: overrides.prompt !== undefined ? overrides.prompt : intervention.cta?.prompt ?? null,
      target: overrides.target !== undefined ? overrides.target : intervention.cta?.target ?? null,
      telemetryKey:
        overrides.telemetryKey !== undefined
          ? overrides.telemetryKey
          : intervention.cta?.telemetryKey ?? interventionId,
      type: overrides.type ?? intervention.cta?.type ?? "open_chat",
    };
  }

  function addIntervention(): void {
    const nextId = window.prompt("New intervention id");
    if (!nextId || !policyRecord) {
      return;
    }

    updatePolicy((current) => ({
      ...current,
      interventions: {
        ...current.interventions,
        [nextId]: {
          body: "",
          category: "custom",
          cta: null,
          ctaLabel: null,
          intent: "",
          label: nextId,
          rationale: "",
          title: "",
        },
      },
    }));
    setSelectedInterventionId(nextId);
  }

  function addRule(): void {
    updatePolicy((current) => ({
      ...current,
      rules: [
        ...current.rules,
        {
          anyEvents: [],
          anyEventsGroup: null,
          bypassBudget: false,
          enabled: true,
          id: `rule_${current.rules.length + 1}`,
          interventions: [],
          name: "New rule",
          priority: (current.rules.at(-1)?.priority ?? 0) + 10,
          stepId: null,
        },
      ],
    }));
    setSelectedRuleIndex(policyRecord?.policy.rules.length ?? 0);
  }

  function moveRule(index: number, direction: -1 | 1): void {
    updatePolicy((current) => {
      const nextRules = [...current.rules];
      const swapIndex = index + direction;
      if (swapIndex < 0 || swapIndex >= nextRules.length) {
        return current;
      }
      [nextRules[index], nextRules[swapIndex]] = [nextRules[swapIndex], nextRules[index]];
      return {
        ...current,
        rules: nextRules,
      };
    });
    setSelectedRuleIndex((current) => Math.max(0, current + direction));
  }

  if (loading) {
    return <div className="loading-shell">Loading coach admin...</div>;
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <section className="auth-card">
          <div className="hero-mark">Conversion Coach</div>
          <h1>Admin portal</h1>
          <p>Manage live coach rules, intervention copy, and policy versions.</p>
          <form className="auth-form" onSubmit={handleLogin}>
            <label>
              Email
              <input value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {errorMessage ? <div className="error-banner">{errorMessage}</div> : null}
            <button type="submit">Sign in</button>
          </form>
        </section>
      </main>
    );
  }

  if (!policyRecord) {
    return <div className="loading-shell">No active policy found.</div>;
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="hero-mark">Conversion Coach</div>
          <h1>Rules control plane</h1>
          <p>
            Active version <strong>v{policyRecord.version}</strong> last saved{" "}
            {new Date(policyRecord.updatedAt).toLocaleString()}.
          </p>
        </div>
        <div className="topbar-actions">
          <span className="user-chip">{user.email}</span>
          <button className="ghost-button" onClick={() => void handleLogout()} type="button">
            Logout
          </button>
          <button onClick={() => void handleSavePolicy()} type="button" disabled={saving}>
            {saving ? "Saving..." : "Save active policy"}
          </button>
        </div>
      </header>

      {errorMessage ? <div className="error-banner full-width">{errorMessage}</div> : null}

      <nav className="tabbar">
        {[
          ["overview", "Overview"],
          ["interventions", "Interventions"],
          ["rules", "Rules"],
          ["versions", "Versions"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={activeTab === key ? "tab active" : "tab"}
            onClick={() => setActiveTab(key as TabKey)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      {activeTab === "overview" ? (
        <section className="grid two-col">
          <article className="panel">
            <h2>Policy guardrails</h2>
            <label>
              Max interventions per journey
              <input
                type="number"
                value={policyRecord.policy.policy.maxInterventionsPerJourney}
                onChange={(event) =>
                  updatePolicy((current) => ({
                    ...current,
                    policy: {
                      ...current.policy,
                      maxInterventionsPerJourney: Number(event.target.value),
                    },
                  }))
                }
              />
            </label>
            <label>
              Price gap shock threshold (EUR)
              <input
                type="number"
                step="0.1"
                value={policyRecord.policy.policy.priceGapShockThresholdEur}
                onChange={(event) =>
                  updatePolicy((current) => ({
                    ...current,
                    policy: {
                      ...current.policy,
                      priceGapShockThresholdEur: Number(event.target.value),
                    },
                  }))
                }
              />
            </label>
            <div className="check-grid">
              {POLICY_EVENTS.map((eventKey) => (
                <label className="check-pill" key={eventKey}>
                  <input
                    type="checkbox"
                    checked={policyRecord.policy.policy.hesitationEvents.includes(eventKey)}
                    onChange={(event) =>
                      updatePolicy((current) => ({
                        ...current,
                        policy: {
                          ...current.policy,
                          hesitationEvents: event.target.checked
                            ? [...current.policy.hesitationEvents, eventKey]
                            : current.policy.hesitationEvents.filter((entry) => entry !== eventKey),
                        },
                      }))
                    }
                  />
                  {eventKey}
                </label>
              ))}
            </div>
          </article>

          <article className="panel">
            <h2>Default action behavior</h2>
            <label>
              Cooldown (ms)
              <input
                type="number"
                value={policyRecord.policy.actionDefaults.cooldownMs}
                onChange={(event) =>
                  updatePolicy((current) => ({
                    ...current,
                    actionDefaults: {
                      ...current.actionDefaults,
                      cooldownMs: Number(event.target.value),
                    },
                  }))
                }
              />
            </label>
            <label>
              Placement
              <select
                value={policyRecord.policy.actionDefaults.placement}
                onChange={(event) =>
                  updatePolicy((current) => ({
                    ...current,
                    actionDefaults: {
                      ...current.actionDefaults,
                      placement: event.target.value as CoachPlacement,
                    },
                  }))
                }
              >
                {PLACEMENTS.map((placement) => (
                  <option key={placement} value={placement}>
                    {placement}
                  </option>
                ))}
              </select>
            </label>
            <label className="inline-toggle">
              <input
                type="checkbox"
                checked={policyRecord.policy.actionDefaults.dismissible}
                onChange={(event) =>
                  updatePolicy((current) => ({
                    ...current,
                    actionDefaults: {
                      ...current.actionDefaults,
                      dismissible: event.target.checked,
                    },
                  }))
                }
              />
              Dismissible by default
            </label>
          </article>
        </section>
      ) : null}

      {activeTab === "interventions" ? (
        <section className="grid split-layout">
          <aside className="panel list-panel">
            <div className="panel-header">
              <h2>Intervention catalog</h2>
              <button className="ghost-button" onClick={addIntervention} type="button">
                Add
              </button>
            </div>
            <div className="list-stack">
              {Object.keys(policyRecord.policy.interventions).map((interventionId) => (
                <button
                  key={interventionId}
                  className={
                    selectedInterventionId === interventionId ? "list-item active" : "list-item"
                  }
                  onClick={() => setSelectedInterventionId(interventionId)}
                  type="button"
                >
                  <strong>{interventionId}</strong>
                  <span>{policyRecord.policy.interventions[interventionId].label}</span>
                </button>
              ))}
            </div>
          </aside>

          <article className="panel editor-panel">
            {selectedIntervention ? (
              <>
                <h2>{selectedInterventionId}</h2>
                <div className="editor-grid">
                  <label>
                    Label
                    <input
                      value={selectedIntervention.label}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              label: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    Category
                    <input
                      value={selectedIntervention.category}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              category: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    Intent
                    <input
                      value={selectedIntervention.intent}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              intent: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    CTA label
                    <input
                      value={selectedIntervention.ctaLabel ?? ""}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              cta: current.interventions[selectedInterventionId!].cta
                                ? buildCta(current.interventions[selectedInterventionId!], selectedInterventionId!, {
                                    label: event.target.value || "Open coach",
                                  })
                                : null,
                              ctaLabel: event.target.value || null,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    CTA action
                    <select
                      value={selectedIntervention.cta?.type ?? "open_chat"}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              cta: buildCta(current.interventions[selectedInterventionId!], selectedInterventionId!, {
                                type: event.target.value as CoachCtaType,
                              }),
                            },
                          },
                        }))
                      }
                    >
                      {CTA_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    CTA target
                    <input
                      value={selectedIntervention.cta?.target ?? ""}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              cta: buildCta(current.interventions[selectedInterventionId!], selectedInterventionId!, {
                                target: event.target.value || null,
                              }),
                            },
                          },
                        }))
                      }
                      placeholder="primary_cta, optimal, step_anchor, CSS selector"
                    />
                  </label>
                  <label className="full-span">
                    CTA chat prompt
                    <textarea
                      rows={3}
                      value={selectedIntervention.cta?.prompt ?? ""}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              cta: buildCta(current.interventions[selectedInterventionId!], selectedInterventionId!, {
                                prompt: event.target.value || null,
                              }),
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Title
                    <input
                      value={selectedIntervention.title}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              title: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Body
                    <textarea
                      rows={5}
                      value={selectedIntervention.body}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              body: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Rationale
                    <textarea
                      rows={4}
                      value={selectedIntervention.rationale}
                      onChange={(event) =>
                        updatePolicy((current) => ({
                          ...current,
                          interventions: {
                            ...current.interventions,
                            [selectedInterventionId!]: {
                              ...current.interventions[selectedInterventionId!],
                              rationale: event.target.value,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                </div>
              </>
            ) : (
              <p>Select an intervention.</p>
            )}
          </article>
        </section>
      ) : null}

      {activeTab === "rules" ? (
        <section className="grid split-layout">
          <aside className="panel list-panel">
            <div className="panel-header">
              <h2>Rules</h2>
              <button className="ghost-button" onClick={addRule} type="button">
                Add
              </button>
            </div>
            <div className="list-stack">
              {policyRecord.policy.rules.map((rule, index) => (
                <button
                  key={`${rule.id}-${index}`}
                  className={selectedRuleIndex === index ? "list-item active" : "list-item"}
                  onClick={() => setSelectedRuleIndex(index)}
                  type="button"
                >
                  <strong>{rule.id}</strong>
                  <span>{rule.name}</span>
                </button>
              ))}
            </div>
          </aside>

          <article className="panel editor-panel">
            {selectedRule ? (
              <>
                <div className="panel-header">
                  <h2>{selectedRule.id}</h2>
                  <div className="stack-inline">
                    <button
                      className="ghost-button"
                      onClick={() => moveRule(selectedRuleIndex, -1)}
                      type="button"
                    >
                      Move up
                    </button>
                    <button
                      className="ghost-button"
                      onClick={() => moveRule(selectedRuleIndex, 1)}
                      type="button"
                    >
                      Move down
                    </button>
                  </div>
                </div>
                <div className="editor-grid">
                  <label>
                    Rule id
                    <input
                      value={selectedRule.id}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          id: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Priority
                    <input
                      type="number"
                      value={selectedRule.priority}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          priority: Number(event.target.value),
                        }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Name
                    <input
                      value={selectedRule.name}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Step id
                    <input
                      value={selectedRule.stepId ?? ""}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          stepId: event.target.value || null,
                        }))
                      }
                    />
                  </label>
                  <label>
                    Event group
                    <input
                      value={selectedRule.anyEventsGroup ?? ""}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          anyEventsGroup: event.target.value || null,
                        }))
                      }
                    />
                  </label>
                  <label className="full-span">
                    Matching events
                    <div className="check-grid">
                      {POLICY_EVENTS.map((eventKey) => (
                        <label className="check-pill" key={eventKey}>
                          <input
                            type="checkbox"
                            checked={selectedRule.anyEvents.includes(eventKey)}
                            onChange={(event) =>
                              updateRuleAt(selectedRuleIndex, (rule) => ({
                                ...rule,
                                anyEvents: event.target.checked
                                  ? [...rule.anyEvents, eventKey]
                                  : rule.anyEvents.filter((entry) => entry !== eventKey),
                              }))
                            }
                          />
                          {eventKey}
                        </label>
                      ))}
                    </div>
                  </label>
                  <label className="full-span">
                    Intervention sequence
                    <input
                      value={selectedRule.interventions.join(", ")}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          interventions: event.target.value
                            .split(",")
                            .map((entry) => entry.trim())
                            .filter(Boolean),
                        }))
                      }
                    />
                  </label>
                  <label className="inline-toggle">
                    <input
                      type="checkbox"
                      checked={selectedRule.enabled !== false}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          enabled: event.target.checked,
                        }))
                      }
                    />
                    Enabled
                  </label>
                  <label className="inline-toggle">
                    <input
                      type="checkbox"
                      checked={selectedRule.bypassBudget}
                      onChange={(event) =>
                        updateRuleAt(selectedRuleIndex, (rule) => ({
                          ...rule,
                          bypassBudget: event.target.checked,
                        }))
                      }
                    />
                    Bypass budget
                  </label>
                </div>
              </>
            ) : (
              <p>Select a rule.</p>
            )}
          </article>
        </section>
      ) : null}

      {activeTab === "versions" ? (
        <section className="panel">
          <div className="panel-header">
            <h2>Version history</h2>
            <p>Restore an older rule set by cloning it into a new active version.</p>
          </div>
          <div className="version-list">
            {versions.map((version) => (
              <div className="version-row" key={version.id}>
                <div>
                  <strong>v{version.version}</strong>
                  <p>
                    Saved {new Date(version.updatedAt).toLocaleString()}
                    {version.isActive ? " • active" : ""}
                    {version.restoredFromPolicyVersionId
                      ? ` • restored from ${version.restoredFromPolicyVersionId}`
                      : ""}
                  </p>
                </div>
                <button
                  className="ghost-button"
                  disabled={version.isActive || saving}
                  onClick={() => void handleRestoreVersion(version.id)}
                  type="button"
                >
                  Restore
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

async function apiGet<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    credentials: "include",
  });
  return parseResponse<T>(response);
}

async function apiPost<T = { ok: boolean }>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    body: JSON.stringify(body),
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
  });
  return parseResponse<T>(response);
}

async function apiPut<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    body: JSON.stringify(body),
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    method: "PUT",
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = (await response.json()) as { message?: string; error?: string };
      message = payload.message ?? payload.error ?? message;
    } catch {
      // Ignore JSON parse failures on errors.
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}
