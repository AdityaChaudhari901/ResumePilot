import { createHmac, timingSafeEqual } from "node:crypto";

export interface TrustedHeaderIdentity {
  displayName: string | null;
  email: string | null;
  externalId: string;
  timestamp: string;
}

interface VerifyTrustedHeaderIdentityInput {
  identity: TrustedHeaderIdentity;
  maxAgeSeconds: number;
  nowSeconds?: number;
  secret: string;
  signature: string | null;
}

export function createTrustedHeaderIdentitySignature(
  secret: string,
  identity: TrustedHeaderIdentity
): string {
  return createHmac("sha256", secret)
    .update(identityPayload(identity), "utf8")
    .digest("hex");
}

export function verifyTrustedHeaderIdentitySignature({
  identity,
  maxAgeSeconds,
  nowSeconds = Math.floor(Date.now() / 1000),
  secret,
  signature
}: VerifyTrustedHeaderIdentityInput): boolean {
  if (!secret || !signature || !/^[a-f0-9]{64}$/.test(signature)) {
    return false;
  }

  const issuedAt = parseUnixTimestamp(identity.timestamp);
  if (issuedAt === null || Math.abs(nowSeconds - issuedAt) > maxAgeSeconds) {
    return false;
  }

  const expectedSignature = createTrustedHeaderIdentitySignature(secret, identity);
  const expected = Buffer.from(expectedSignature, "utf8");
  const received = Buffer.from(signature, "utf8");
  return expected.length === received.length && timingSafeEqual(expected, received);
}

function identityPayload({ displayName, email, externalId, timestamp }: TrustedHeaderIdentity): string {
  return [externalId, email ?? "", displayName ?? "", timestamp].join("\n");
}

function parseUnixTimestamp(value: string): number | null {
  if (!/^\d+$/.test(value)) {
    return null;
  }

  const timestamp = Number(value);
  return Number.isSafeInteger(timestamp) ? timestamp : null;
}
