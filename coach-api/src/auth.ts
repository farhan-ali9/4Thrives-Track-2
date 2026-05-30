import { promisify } from "node:util";
import { randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import type { FastifyReply, FastifyRequest } from "fastify";
import type { AdminUserRecord, CoachRepository } from "./repository";

const scryptAsync = promisify(scrypt);
export const SESSION_COOKIE_NAME = "conversion_coach_admin";

export interface SessionPayload {
  userId: string;
  email: string;
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16).toString("hex");
  const hash = (await scryptAsync(password, salt, 64)) as Buffer;
  return `${salt}:${hash.toString("hex")}`;
}

export async function verifyPassword(password: string, storedHash: string): Promise<boolean> {
  const [salt, expected] = storedHash.split(":");
  if (!salt || !expected) {
    return false;
  }

  const actual = (await scryptAsync(password, salt, 64)) as Buffer;
  const expectedBuffer = Buffer.from(expected, "hex");
  if (expectedBuffer.length !== actual.length) {
    return false;
  }

  return timingSafeEqual(expectedBuffer, actual);
}

export function setSessionCookie(
  reply: FastifyReply,
  payload: SessionPayload,
  secure: boolean,
): void {
  reply.setCookie(SESSION_COOKIE_NAME, encodeSessionPayload(payload), {
    httpOnly: true,
    path: "/",
    sameSite: "lax",
    secure,
    signed: true,
  });
}

export function clearSessionCookie(reply: FastifyReply, secure: boolean): void {
  reply.clearCookie(SESSION_COOKIE_NAME, {
    httpOnly: true,
    path: "/",
    sameSite: "lax",
    secure,
  });
}

export async function readAuthenticatedUser(
  request: FastifyRequest,
  repository: CoachRepository,
): Promise<AdminUserRecord | null> {
  const rawCookie = request.cookies[SESSION_COOKIE_NAME];
  if (!rawCookie) {
    return null;
  }

  const decoded = request.unsignCookie(rawCookie);
  if (!decoded.valid || !decoded.value) {
    return null;
  }

  const session = decodeSessionPayload(decoded.value);
  if (!session) {
    return null;
  }

  return repository.findAdminById(session.userId);
}

function encodeSessionPayload(payload: SessionPayload): string {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

function decodeSessionPayload(value: string): SessionPayload | null {
  try {
    const parsed = JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as SessionPayload;
    if (!parsed.userId || !parsed.email) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}
