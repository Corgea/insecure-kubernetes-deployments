// Helpers for the share dialog.

// session is null for anonymous visitors. A signed-in session always has a user.
export function ownerLabel(session) {
  return session?.user.displayName ?? "Anonymous";
}

export function shareUrl(baseUrl, code) {
  const url = new URL("/share", baseUrl);
  url.searchParams.set("code", code);
  return url.toString();
}

export function remainingLabel(used, limit) {
  const remaining = Math.max(0, limit - used);
  return remaining === 1 ? "1 share left" : `${remaining} shares left`;
}
