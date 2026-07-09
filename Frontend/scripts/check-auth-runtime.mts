import assert from "node:assert/strict";

import {
  resolveAuthRuntimeConfig,
  shouldUseClerkProvider,
  type RuntimeEnv
} from "../src/lib/auth-runtime.ts";

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
  RESUMEPILOT_AUTH_PROVIDER: "trusted_headers"
});
assert.equal(trustedHeadersWithoutSecret.isUsable, false);
assert.match(trustedHeadersWithoutSecret.reason ?? "", /AUTH_TRUSTED_PROXY_SECRET/);

const trustedHeadersReady = resolve({
  RESUMEPILOT_AUTH_PROVIDER: "trusted-headers",
  AUTH_TRUSTED_PROXY_SECRET: "proxy-secret"
});
assert.equal(trustedHeadersReady.provider, "trusted_headers");
assert.equal(trustedHeadersReady.isUsable, true);

console.log("Auth runtime config checks passed.");
