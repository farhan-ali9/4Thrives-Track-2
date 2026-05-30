import seedPolicyJson from "./seed-policy.json" with { type: "json" };
import { parsePolicyDocument } from "./policy.js";

export const seedPolicy = parsePolicyDocument(seedPolicyJson);
