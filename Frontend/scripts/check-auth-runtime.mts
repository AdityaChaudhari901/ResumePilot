import assert from "node:assert/strict";

import {
  resolveAuthRuntimeConfig,
  shouldUseClerkProvider,
  type RuntimeEnv
} from "../src/lib/auth-runtime.ts";
import {
  createTrustedHeaderIdentitySignature,
  verifyTrustedHeaderIdentitySignature
} from "../src/lib/trusted-header-auth.ts";

function resolve(overrides: RuntimeEnv) {
  return resolveAuthRuntimeConfig({
    NODE_ENV: "development",
    RESUMEPILOT_AUTH_PROVIDER: "local",
    ...overrides
  });
}

assert.equal(resolve({}).isUsable, true, "local auth should work in development");

const blockedProductionLocal = resolve({
  NODE_ENV: "production",
  RESUMEPILOT_AUTH_PROVIDER: "local",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret"
});
assert.equal(blockedProductionLocal.isUsable, false);
assert.match(blockedProductionLocal.reason ?? "", /Local auth is disabled/);

const allowedProductionLocal = resolve({
  NODE_ENV: "production",
  RESUMEPILOT_AUTH_PROVIDER: "local",
  RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION: "true",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret"
});
assert.equal(allowedProductionLocal.isUsable, true, "explicit private-stack local auth should work");

const productionLocalWithoutSecret = resolve({
  NODE_ENV: "production",
  RESUMEPILOT_AUTH_PROVIDER: "local",
  RESUMEPILOT_ALLOW_LOCAL_AUTH_IN_PRODUCTION: "true"
});
assert.equal(productionLocalWithoutSecret.isUsable, false);
assert.match(productionLocalWithoutSecret.reason ?? "", /AUTH_TRUSTED_PROXY_SECRET/);

const invalidProvider = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "magic"
});
assert.equal(invalidProvider.provider, "invalid");
assert.equal(invalidProvider.isUsable, false);

const clerkWithoutKeys = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "clerk",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret"
});
assert.equal(clerkWithoutKeys.isUsable, false);
assert.equal(shouldUseClerkProvider({ RESUMEPILOT_AUTH_PROVIDER: "clerk" }), false);

const clerkReadyEnv = {
  RESUMEPILOT_AUTH_PROVIDER: "clerk",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret",
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_example",
  CLERK_SECRET_KEY: "sk_test_example"
};
assert.equal(resolve(clerkReadyEnv).isUsable, true, "complete Clerk config should be usable");
assert.equal(shouldUseClerkProvider(clerkReadyEnv), true);

const trustedHeadersWithoutSecret = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "trusted_headers",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret"
});
assert.equal(trustedHeadersWithoutSecret.isUsable, false);
assert.match(trustedHeadersWithoutSecret.reason ?? "", /RESUMEPILOT_TRUSTED_HEADER_SECRET/);

const trustedHeadersWithoutBackendSigningSecret = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "trusted_headers",
  RESUMEPILOT_TRUSTED_HEADER_SECRET: "upstream-secret"
});
assert.equal(trustedHeadersWithoutBackendSigningSecret.isUsable, false);
assert.match(trustedHeadersWithoutBackendSigningSecret.reason ?? "", /AUTH_TRUSTED_PROXY_SECRET/);

const trustedHeadersReady = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "trusted-headers",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret",
  RESUMEPILOT_TRUSTED_HEADER_SECRET: "upstream-secret",
  RESUMEPILOT_TRUSTED_HEADER_TTL_SECONDS: "60"
});
assert.equal(trustedHeadersReady.provider, "trusted_headers");
assert.equal(trustedHeadersReady.isUsable, true);
assert.equal(trustedHeadersReady.trustedHeaderAuthTtlSeconds, 60);

const trustedHeadersWithInvalidTtl = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "trusted_headers",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret",
  RESUMEPILOT_TRUSTED_HEADER_SECRET: "upstream-secret",
  RESUMEPILOT_TRUSTED_HEADER_TTL_SECONDS: "5"
});
assert.equal(trustedHeadersWithInvalidTtl.isUsable, false);
assert.match(trustedHeadersWithInvalidTtl.reason ?? "", /TRUSTED_HEADER_TTL_SECONDS/);

const trustedIdentity = {
  externalId: "upstream-user",
  email: "upstream@example.test",
  displayName: "Upstream User",
  timestamp: "1725000000"
};
const trustedIdentitySignature = createTrustedHeaderIdentitySignature(
  "upstream-secret",
  trustedIdentity
);
assert.equal(
  verifyTrustedHeaderIdentitySignature({
    identity: trustedIdentity,
    maxAgeSeconds: 60,
    nowSeconds: 1725000030,
    secret: "upstream-secret",
    signature: trustedIdentitySignature
  }),
  true,
  "valid upstream signatures should authenticate"
);
assert.equal(
  verifyTrustedHeaderIdentitySignature({
    identity: { ...trustedIdentity, externalId: "spoofed-user" },
    maxAgeSeconds: 60,
    nowSeconds: 1725000030,
    secret: "upstream-secret",
    signature: trustedIdentitySignature
  }),
  false,
  "signatures must bind the external user ID"
);
assert.equal(
  verifyTrustedHeaderIdentitySignature({
    identity: trustedIdentity,
    maxAgeSeconds: 60,
    nowSeconds: 1725000061,
    secret: "upstream-secret",
    signature: trustedIdentitySignature
  }),
  false,
  "expired upstream signatures must be rejected"
);
assert.equal(
  verifyTrustedHeaderIdentitySignature({
    identity: trustedIdentity,
    maxAgeSeconds: 60,
    nowSeconds: 1725000030,
    secret: "upstream-secret",
    signature: null
  }),
  false,
  "unsigned trusted headers must be rejected"
);

console.log("Auth runtime config checks passed.");
