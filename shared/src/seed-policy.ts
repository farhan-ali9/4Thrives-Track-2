import seedPolicyJson from "./seed-policy.json";
import { parsePolicyDocument } from "./policy";

export const seedPolicy = parsePolicyDocument(seedPolicyJson);
