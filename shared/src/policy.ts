import { z } from "zod";
import type { CoachPlacement } from "./contracts.js";

export const coachEventSchema = z.enum([
  "long_dwell",
  "back_nav",
  "repeated_change",
  "cancel_intent",
  "price_fixation",
  "oos_tariff",
  "oos_path",
  "price_gap_shock",
  "none",
]);

export type CoachPolicyEvent = z.infer<typeof coachEventSchema>;

export const coachPlacementSchema: z.ZodType<CoachPlacement> = z.enum([
  "inline-top-of-step",
  "near-primary-cta",
  "bottom-toast",
]);

export const policyMetadataSchema = z
  .object({
    name: z.string(),
    version: z.string(),
    configType: z.string(),
    decisionModel: z.string(),
    usesMockData: z.boolean(),
    dataSource: z.string(),
    owner: z.string(),
    purpose: z.string(),
    importantNote: z.string(),
    scope: z
      .object({
        inScope: z.array(z.string()),
        outOfScope: z.array(z.string()),
        outOfScopeHandling: z.string(),
      })
      .passthrough(),
    runtimeNotes: z.array(z.string()),
  })
  .passthrough();

export const policySettingsSchema = z
  .object({
    description: z.string().optional(),
    maxInterventionsPerJourney: z.number().int().min(0),
    maxInterventionsReason: z.string().optional(),
    hesitationEvents: z.array(coachEventSchema).min(1),
    hesitationEventsReason: z.string().optional(),
    priceGapShockThresholdEur: z.number().min(0),
    priceGapShockThresholdReason: z.string().optional(),
  })
  .passthrough();

export const actionDefaultsSchema = z
  .object({
    description: z.string().optional(),
    cooldownMs: z.number().int().min(0),
    dismissible: z.boolean(),
    placement: coachPlacementSchema,
  })
  .passthrough();

export const interventionSchema = z
  .object({
    label: z.string(),
    category: z.string(),
    intent: z.string(),
    title: z.string(),
    body: z.string(),
    ctaLabel: z.string().nullable(),
    shownWhen: z.array(z.string()).optional(),
    rationale: z.string(),
    cooldownMs: z.number().int().min(0).optional(),
    dismissible: z.boolean().optional(),
    placement: coachPlacementSchema.optional(),
    bypassBudget: z.boolean().optional(),
  })
  .passthrough();

export const ruleSchema = z
  .object({
    priority: z.number().int(),
    id: z.string().min(1),
    name: z.string(),
    stepId: z.string().nullable(),
    anyEvents: z.array(coachEventSchema),
    anyEventsGroup: z.string().nullable(),
    interventions: z.array(z.string()).min(1),
    bypassBudget: z.boolean().default(false),
    enabled: z.boolean().default(true),
    userSituation: z.string().optional(),
    businessReason: z.string().optional(),
    expectedOutcome: z.string().optional(),
    implementationNote: z.string().optional(),
  })
  .passthrough();

export const policyDocumentSchema = z
  .object({
    metadata: policyMetadataSchema,
    signalDictionary: z.record(z.string(), z.unknown()),
    funnelStepDictionary: z.record(z.string(), z.unknown()),
    policy: policySettingsSchema,
    actionDefaults: actionDefaultsSchema,
    placementByStep: z
      .object({
        description: z.string().optional(),
      })
      .catchall(coachPlacementSchema),
    interventions: z.record(z.string(), interventionSchema),
    rules: z.array(ruleSchema),
  })
  .passthrough();

export type CoachPolicyMetadata = z.infer<typeof policyMetadataSchema>;
export type CoachPolicySettings = z.infer<typeof policySettingsSchema>;
export type CoachPolicyActionDefaults = z.infer<typeof actionDefaultsSchema>;
export type CoachPolicyIntervention = z.infer<typeof interventionSchema>;
export type CoachPolicyRule = z.infer<typeof ruleSchema>;
export type CoachPolicyDocument = z.infer<typeof policyDocumentSchema>;

export function parsePolicyDocument(input: unknown): CoachPolicyDocument {
  const parsed = policyDocumentSchema.parse(input);
  return {
    ...parsed,
    rules: parsed.rules.map((rule) => ({
      ...rule,
      bypassBudget: rule.bypassBudget ?? false,
      enabled: rule.enabled ?? true,
    })),
  };
}
